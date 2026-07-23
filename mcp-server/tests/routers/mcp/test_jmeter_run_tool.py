"""The ``run_jmeter_test`` public MCP tool — JMeter-first: run an existing .jmx.

Covers the contract: a tester passes a path to an existing ``.jmx`` file; the
tool validates it, stores the plan under a fresh operation id (before enqueueing),
creates a QUEUED operation stamped with the internal engine type, and returns the
operation id. Missing file → 404, invalid plan → 400, and re-running the same file
starts a new run (no once-only plan id). It enqueues; it never executes.
"""

import ast
import tempfile
import unittest
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.constants.batch import BatchType
from app.integrations.jmeter.jmx_validator import JmxValidationError
from app.integrations.jmeter.plan_validator import JmxPlanValidator
from app.schemas.performance.operation_type import PerformanceOperationType
from app.services.jmeter.run_service import JMeterTestService, JmxFileNotFoundError
from app.routers.mcp.jmeter_router import (
    get_jmeter_test_service,
    jmeter_router,
    run_jmeter_test,
)

_PERF_TYPE = PerformanceOperationType.PERFORMANCE_TEST.value
_VALID = "<jmeterTestPlan><hashTree/></jmeterTestPlan>"
_SCRIPTING = (
    '<jmeterTestPlan><hashTree>'
    '<BeanShellSampler testclass="BeanShellSampler"/>'
    '</hashTree></jmeterTestPlan>'
)


class _FakePlanStore:
    def __init__(self):
        self.puts = {}  # operation_id -> (bytes, timeout)

    def put(self, operation_id: str, plan: bytes, timeout_seconds: Optional[float] = None) -> None:
        self.puts[operation_id] = (plan, timeout_seconds)


class _FakeOps:
    def __init__(self):
        self.created = []  # (operation_id, batch_type, metadata)

    def create(self, batch_type, metadata=None, log_path=None, operation_id=None):
        self.created.append((operation_id, batch_type, metadata))
        return operation_id


def _write(dirpath, name, content):
    p = Path(dirpath) / name
    p.write_text(content)
    return str(p)


class RunServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = _FakePlanStore()
        self.ops = _FakeOps()
        self.service = JMeterTestService(JmxPlanValidator(), self.store, self.ops)
        self.tmp = tempfile.mkdtemp()

    def test_runs_existing_file_and_stores_plan_before_enqueue(self):
        jmx = _write(self.tmp, "load.jmx", _VALID)
        op_id = self.service.run(jmx, timeout_seconds=120.0)
        # Plan stored under the returned operation id (the worker's pull key) ...
        self.assertIn(op_id, self.store.puts)
        self.assertEqual(self.store.puts[op_id], (_VALID.encode(), 120.0))
        # ... and the operation was enqueued with the internal type + jmx path.
        oid, batch, meta = self.ops.created[0]
        self.assertEqual(oid, op_id)
        self.assertEqual(batch, BatchType.PERFORMANCE_TEST)
        self.assertEqual(meta["operation_type"], _PERF_TYPE)
        self.assertEqual(meta["jmx_file"], jmx)

    def test_rerunning_same_file_starts_a_new_run(self):
        jmx = _write(self.tmp, "load.jmx", _VALID)
        a = self.service.run(jmx)
        b = self.service.run(jmx)
        self.assertNotEqual(a, b)  # no once-only plan id
        self.assertEqual(len(self.ops.created), 2)

    def test_missing_file_raises_and_enqueues_nothing(self):
        with self.assertRaises(JmxFileNotFoundError):
            self.service.run("/does/not/exist.jmx")
        self.assertEqual(self.ops.created, [])
        self.assertEqual(self.store.puts, {})

    def test_scripting_plan_rejected_and_enqueues_nothing(self):
        jmx = _write(self.tmp, "bad.jmx", _SCRIPTING)
        with self.assertRaises(JmxValidationError):
            self.service.run(jmx)
        self.assertEqual(self.ops.created, [])
        self.assertEqual(self.store.puts, {})


class RunEndpointTests(unittest.TestCase):
    def setUp(self):
        self.store = _FakePlanStore()
        self.ops = _FakeOps()
        service = JMeterTestService(JmxPlanValidator(), self.store, self.ops)
        app = FastAPI()
        app.include_router(jmeter_router)
        app.dependency_overrides[get_jmeter_test_service] = lambda: service
        self.client = TestClient(app)
        self.tmp = tempfile.mkdtemp()

    def _post(self, jmx_file):
        return self.client.post("/jmeter/run_test", json={"jmx_file": jmx_file})

    def test_valid_file_returns_queued_operation_id(self):
        jmx = _write(self.tmp, "ok.jmx", _VALID)
        resp = self._post(jmx)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()["result"]
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["operation_id"], self.ops.created[0][0])

    def test_missing_file_is_404(self):
        self.assertEqual(self._post("/no/such/file.jmx").status_code, 404)

    def test_invalid_plan_is_400(self):
        jmx = _write(self.tmp, "bad.jmx", _SCRIPTING)
        resp = self._post(jmx)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("scripting", resp.json()["detail"].lower())

    def test_missing_jmx_file_field_is_422(self):
        self.assertEqual(self.client.post("/jmeter/run_test", json={}).status_code, 422)


class ScopeGuardTests(unittest.TestCase):
    """The public tool enqueues but never executes: no runtime/worker/dispatcher/
    pool imports, and it reads no Settings."""

    _FORBIDDEN_PREFIXES = (
        "app.services.performance.runtime",
        "app.services.performance.worker.",
        "app.services.performance.dispatcher",
        "app.integrations.performance.pool",
        "app.integrations.performance.scheduler",
        "app.integrations.performance.registry",
    )

    def _imports(self, rel_path):
        tree = ast.parse(Path(rel_path).read_text(encoding="utf-8"))
        mods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
        return mods

    def test_service_has_no_execution_or_settings_imports(self):
        mods = self._imports("app/services/jmeter/run_service.py")
        for mod in mods:
            for forbidden in self._FORBIDDEN_PREFIXES:
                self.assertFalse(
                    mod == forbidden.rstrip(".") or mod.startswith(forbidden),
                    msg=f"test_runner imports execution machinery: {mod}",
                )
            self.assertFalse(mod == "app.core.config" or mod.startswith("app.core.config."))


if __name__ == "__main__":
    unittest.main()
