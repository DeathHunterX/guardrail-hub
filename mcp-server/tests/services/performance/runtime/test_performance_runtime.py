"""PerformanceRuntime tests — lifecycle order, cleanup guarantees, purity.

Proves the orchestrator sequences the stages in the mandated order and that
cleanup always runs *after* persistence — on success, on a definitive persist
failure, and on a rejected plan — never mid-execution.
"""

import ast
import tempfile
import unittest
from pathlib import Path
from threading import Event

import app.services.performance.runtime.performance_runtime as runtime_module
from app.services.performance.engine.dto import (
    Artifact,
    ArtifactKind,
    ArtifactSet,
    ExecutionResult,
    ExecutionStatus,
)
from app.services.performance.runtime import (
    PerformanceRuntime,
    PersistencePort,
    PlanValidator,
    WorkspaceManager,
)


class _Recorder:
    def __init__(self):
        self.events = []


class _FakeValidator:
    def __init__(self, recorder, *, fail=False):
        self._rec = recorder
        self._fail = fail

    def validate(self, plan):
        self._rec.events.append("validate")
        if self._fail:
            raise ValueError("invalid plan")


class _FakeRunner:
    """Writes a real artifact into the workspace and returns a chosen status."""

    def __init__(self, recorder, *, status=ExecutionStatus.COMPLETED, exit_code=0):
        self._rec = recorder
        self._status = status
        self._exit_code = exit_code
        self.plan_existed_at_run = None

    def run(self, request, cancel):
        self._rec.events.append("run")
        self.plan_existed_at_run = request.plan_path.exists()
        results = request.output_dir / "results.jtl"
        results.write_text("Cookie: secret\n")
        return ExecutionResult(
            status=self._status,
            exit_code=self._exit_code,
            duration_seconds=0.01,
            artifacts=ArtifactSet((Artifact(ArtifactKind.RESULTS, results),)),
        )


class _FakeRedactor:
    def __init__(self, recorder):
        self._rec = recorder

    def __call__(self, artifacts):
        self._rec.events.append("redact")


class _FakePersistence:
    def __init__(self, recorder, *, fail=False):
        self._rec = recorder
        self._fail = fail
        self.artifact_existed_at_persist = None

    def persist(self, operation_id, result):
        self._rec.events.append("persist")
        self.artifact_existed_at_persist = result.artifacts.artifacts[0].path.exists()
        if self._fail:
            raise RuntimeError("persist failed")


class PerformanceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.rec = _Recorder()

    def tearDown(self):
        self._tmp.cleanup()

    def _runtime(self, *, validator=None, runner=None, persistence=None, redactor=None):
        return PerformanceRuntime(
            workspaces=WorkspaceManager(self.base),
            validator=validator or _FakeValidator(self.rec),
            runner=runner or _FakeRunner(self.rec),
            persistence=persistence or _FakePersistence(self.rec),
            redactor=redactor or _FakeRedactor(self.rec),
        )

    def _op_root(self, op="op-1") -> Path:
        return self.base / "operations" / op

    def test_happy_path_orders_stages_and_cleans_up_after_persist(self):
        runner = _FakeRunner(self.rec)
        persistence = _FakePersistence(self.rec)
        runtime = self._runtime(runner=runner, persistence=persistence)

        result = runtime.execute("op-1", b"<jmeterTestPlan/>", timeout_seconds=30)

        self.assertEqual(self.rec.events, ["validate", "run", "redact", "persist"])
        self.assertEqual(result.status, ExecutionStatus.COMPLETED)
        self.assertTrue(runner.plan_existed_at_run)  # plan written before execute
        self.assertTrue(persistence.artifact_existed_at_persist)  # workspace alive at persist
        self.assertFalse(self._op_root().exists())  # cleaned up AFTER persist

    def test_validation_failure_short_circuits_and_cleans_up(self):
        runtime = self._runtime(validator=_FakeValidator(self.rec, fail=True))
        with self.assertRaises(ValueError):
            runtime.execute("op-1", b"<jmeterTestPlan/>")
        self.assertEqual(self.rec.events, ["validate"])  # never ran/redacted/persisted
        self.assertFalse(self._op_root().exists())

    def test_persistence_failure_still_cleans_up_after_redaction(self):
        runtime = self._runtime(persistence=_FakePersistence(self.rec, fail=True))
        with self.assertRaises(RuntimeError):
            runtime.execute("op-1", b"<jmeterTestPlan/>")
        # redact happened before the failing persist; cleanup still ran.
        self.assertEqual(self.rec.events, ["validate", "run", "redact", "persist"])
        self.assertFalse(self._op_root().exists())

    def test_engine_failure_is_still_redacted_persisted_and_returned(self):
        runner = _FakeRunner(self.rec, status=ExecutionStatus.FAILED, exit_code=1)
        runtime = self._runtime(runner=runner)
        result = runtime.execute("op-1", b"<jmeterTestPlan/>")
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertEqual(self.rec.events, ["validate", "run", "redact", "persist"])
        self.assertFalse(self._op_root().exists())


class RuntimePurityTests(unittest.TestCase):
    """Structural guards: the orchestrator invokes no subprocess and knows no engine."""

    def _imported_names(self):
        src = Path(runtime_module.__file__).read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name
            elif isinstance(node, ast.ImportFrom):
                yield node.module or ""

    def test_runtime_never_imports_subprocess(self):
        self.assertNotIn("subprocess", list(self._imported_names()))

    def test_runtime_has_no_jmeter_or_docker_dependency(self):
        for name in self._imported_names():
            self.assertNotIn("integrations.jmeter", name)
            self.assertNotIn("docker", name.lower())


class PortConformanceTests(unittest.TestCase):
    def test_fake_persistence_satisfies_port(self):
        self.assertIsInstance(_FakePersistence(_Recorder()), PersistencePort)

    def test_jmx_adapter_satisfies_validator_port(self):
        from app.integrations.jmeter.plan_validator import JmxPlanValidator

        self.assertIsInstance(JmxPlanValidator(), PlanValidator)


if __name__ == "__main__":
    unittest.main()
