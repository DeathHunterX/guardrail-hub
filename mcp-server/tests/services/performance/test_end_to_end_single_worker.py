"""End-to-end single-worker lifecycle (ADR-0010) — the pull model, in process.

Wires the real collaborators (registry, coordinator, runtime, JMeter runner with
a fake engine, validator, redaction, report channel) with in-process transports
and drives one operation through the full lifecycle:

    register -> assign -> heartbeat(sees assignment) -> pull -> validate ->
    execute -> collect -> redact -> persist(report) -> complete -> release -> cleanup

It proves the security-critical ordering directly: the secret written by the
engine into the results file is **absent from the persisted report** (redaction
ran before persistence), and the workspace is gone afterwards (cleanup ran after
persistence). Assignment is done directly here — scheduling arrives in the
dispatcher component; this validates the lifecycle with exactly one worker.
"""

import base64
import stat
import tempfile
import unittest
from pathlib import Path
from threading import Event

from app.integrations.jmeter.jmeter_runner import JMeterRunner
from app.integrations.jmeter.jmx_validator import JmxValidationError
from app.integrations.jmeter.plan_validator import JmxPlanValidator
from app.integrations.performance.registry import PerformanceWorkerRegistry
from app.services.performance.persistence import ReportChannelPersistence
from app.services.performance.redaction import redact_artifacts
from app.services.performance.runtime import PerformanceRuntime, WorkspaceManager
from app.services.performance.worker import PerformanceWorker
from app.services.performance.worker_api import (
    PlanNotFoundError,
    StoredPlan,
    WorkerCoordinator,
)

_SECRET = "secretcookievalue-must-not-persist"
_SAFE_PLAN = (
    b'<jmeterTestPlan version="1.2"><hashTree>'
    b'<ThreadGroup testclass="ThreadGroup"/>'
    b"</hashTree></jmeterTestPlan>"
)
_SCRIPTING_PLAN = (
    b'<jmeterTestPlan version="1.2"><hashTree>'
    b'<JSR223Sampler testclass="JSR223Sampler"/>'
    b"</hashTree></jmeterTestPlan>"
)

# Fake engine: writes a results file containing a secret header (to be redacted),
# a log, and an HTML report; exits 0.
_FAKE_JMETER = """#!/usr/bin/env bash
L=""; J=""; O=""
while [[ $# -gt 0 ]]; do
  case "$1" in -l) shift; L="$1";; -j) shift; J="$1";; -o) shift; O="$1";; esac
  shift
done
[[ -n "$L" ]] && printf 'Cookie: %s\\n' "$SECRET" > "$L"
[[ -n "$J" ]] && echo "engine log" > "$J"
[[ -n "$O" ]] && mkdir -p "$O" && echo "<html></html>" > "$O/index.html"
exit 0
"""


class _InMemoryPlanStore:
    def __init__(self):
        self.plans = {}

    def get(self, operation_id):
        try:
            return self.plans[operation_id]
        except KeyError as exc:
            raise PlanNotFoundError(operation_id) from exc


class _InMemoryReportStore:
    def __init__(self):
        self.saved = []

    def save(self, report):
        self.saved.append(report)


class _StatusSink:
    def __init__(self):
        self.calls = []

    def complete(self, operation_id):
        self.calls.append(("complete", operation_id))

    def fail(self, operation_id, error):
        self.calls.append(("fail", operation_id, error))

    def cancel(self, operation_id):
        self.calls.append(("cancel", operation_id))


class _InProcessServer:
    """ServerClient over an in-process coordinator (no HTTP)."""

    def __init__(self, coordinator):
        self._c = coordinator

    def register(self, request):
        return self._c.register(request)

    def heartbeat(self, request):
        return self._c.heartbeat(request)

    def pull(self, request):
        return self._c.pull_assignment(request.worker_id, request.operation_id)


class _InProcessReportSender:
    def __init__(self, coordinator):
        self._c = coordinator

    def send(self, report):
        self._c.report(report)


class EndToEndSingleWorkerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

        self.registry = PerformanceWorkerRegistry()
        self.plans = _InMemoryPlanStore()
        self.reports = _InMemoryReportStore()
        self.sink = _StatusSink()
        self.coordinator = WorkerCoordinator(
            registry=self.registry,
            plans=self.plans,
            reports=self.reports,
            operations=self.sink,
        )

        runtime = PerformanceRuntime(
            workspaces=WorkspaceManager(self.base / "workspaces"),
            validator=JmxPlanValidator(),
            runner=JMeterRunner(binary=self._fake_jmeter(), grace_seconds=1.0, poll_seconds=0.02),
            persistence=ReportChannelPersistence(_InProcessReportSender(self.coordinator)),
            redactor=redact_artifacts,
        )
        self.worker = PerformanceWorker(
            server=_InProcessServer(self.coordinator),
            runtime=runtime,
            worker_id="w",
            hostname="w",
            version="1.0",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _fake_jmeter(self) -> str:
        import os

        os.environ["SECRET"] = _SECRET
        path = self.base / "fake-jmeter"
        path.write_text(_FAKE_JMETER)
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return str(path)

    def _op_root(self, op):
        return self.base / "workspaces" / "operations" / op

    def test_full_lifecycle_completes_and_never_persists_the_secret(self):
        self.worker.register()
        self.plans.plans["op-1"] = StoredPlan(plan=_SAFE_PLAN, timeout_seconds=30.0)
        self.registry.assign("w", "op-1")  # (dispatcher's job; direct here)

        seen = self.worker.heartbeat_once()
        self.assertEqual(seen.assignment, "op-1")

        self.worker.execute_assignment("op-1", Event())

        # Operation transitioned to complete and the worker was released.
        self.assertIn(("complete", "op-1"), self.sink.calls)
        self.assertTrue(self.registry.get("w").is_idle)

        # Exactly one report persisted, and the secret is NOT in it (redaction
        # ran before persistence — INV4/INV10, end to end).
        self.assertEqual(len(self.reports.saved), 1)
        report = self.reports.saved[0]
        results = next(a for a in report.artifacts if a.name == "results.jtl")
        decoded = base64.b64decode(results.content_b64).decode("utf-8")
        self.assertNotIn(_SECRET, decoded)
        self.assertIn("[REDACTED]", decoded)

        # Workspace destroyed after persistence (INV5).
        self.assertFalse(self._op_root("op-1").exists())

    def test_rejected_plan_never_persists_and_cleans_up(self):
        self.worker.register()
        self.plans.plans["op-2"] = StoredPlan(plan=_SCRIPTING_PLAN, timeout_seconds=30.0)
        self.registry.assign("w", "op-2")

        with self.assertRaises(JmxValidationError):
            self.worker.execute_assignment("op-2", Event())

        self.assertEqual(self.reports.saved, [])          # nothing persisted
        self.assertFalse(self._op_root("op-2").exists())  # workspace cleaned


if __name__ == "__main__":
    unittest.main()
