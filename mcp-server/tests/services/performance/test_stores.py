"""C3.2 — filesystem PlanStore / ReportStore (ADR-0010 §4.5/§4.6)."""

import base64
import json
import tempfile
import unittest
from pathlib import Path

from app.integrations.performance.registry import PerformanceWorkerRegistry
from app.schemas.performance.report import ArtifactPayload, OperationReport
from app.services.performance.stores import (
    FilesystemPlanStore,
    FilesystemReportStore,
    UnsafeOperationIdError,
)
from app.services.performance.worker_api import (
    PlanNotFoundError,
    StoredPlan,
    WorkerCoordinator,
)


class _FakeSink:
    def __init__(self):
        self.calls = []

    def complete(self, operation_id):
        self.calls.append(("complete", operation_id))

    def fail(self, operation_id, error):
        self.calls.append(("fail", operation_id, error))

    def cancel(self, operation_id):
        self.calls.append(("cancel", operation_id))


class FilesystemPlanStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = FilesystemPlanStore(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_put_get_round_trip(self):
        self.store.put("op-1", b"<jmeterTestPlan/>", 30.0)
        stored = self.store.get("op-1")
        self.assertEqual(stored, StoredPlan(plan=b"<jmeterTestPlan/>", timeout_seconds=30.0))

    def test_put_without_timeout(self):
        self.store.put("op-1", b"<plan/>")
        self.assertIsNone(self.store.get("op-1").timeout_seconds)

    def test_missing_plan_raises(self):
        with self.assertRaises(PlanNotFoundError):
            self.store.get("nope")

    def test_traversal_operation_id_rejected(self):
        for bad in ("../escape", "a/b", "a\\b", ".."):
            with self.assertRaises(UnsafeOperationIdError):
                self.store.put(bad, b"x")


class FilesystemReportStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.store = FilesystemReportStore(self.base)

    def tearDown(self):
        self._tmp.cleanup()

    def _report(self, op="op-1"):
        return OperationReport(
            operation_id=op,
            status="completed",
            exit_code=0,
            duration_seconds=1.5,
            artifacts=[
                ArtifactPayload(kind="results", name="results.jtl", content_b64=base64.b64encode(b"data").decode()),
                ArtifactPayload(kind="log", name="jmeter.log", content_b64=base64.b64encode(b"log").decode()),
            ],
        )

    def test_persists_artifacts_and_metadata(self):
        self.store.save(self._report())
        op_dir = self.base / "op-1"
        self.assertEqual((op_dir / "artifacts" / "results.jtl").read_bytes(), b"data")
        self.assertEqual((op_dir / "artifacts" / "jmeter.log").read_bytes(), b"log")
        meta = json.loads((op_dir / "report.json").read_text())
        self.assertEqual(meta["status"], "completed")
        self.assertEqual(meta["exit_code"], 0)
        self.assertEqual({a["name"] for a in meta["artifacts"]}, {"results.jtl", "jmeter.log"})

    def test_isolation_between_operations(self):
        self.store.save(self._report("op-a"))
        self.store.save(self._report("op-b"))
        self.assertTrue((self.base / "op-a" / "report.json").is_file())
        self.assertTrue((self.base / "op-b" / "report.json").is_file())
        self.assertNotEqual(self.base / "op-a", self.base / "op-b")

    def test_traversal_operation_id_rejected(self):
        with self.assertRaises(UnsafeOperationIdError):
            self.store.save(self._report("../escape"))


class PortConformanceViaCoordinatorTests(unittest.TestCase):
    """Prove both stores satisfy the ports the WorkerCoordinator consumes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.plans = FilesystemPlanStore(base / "data")
        self.reports = FilesystemReportStore(base / "reports")
        self.registry = PerformanceWorkerRegistry()
        self.sink = _FakeSink()
        self.coord = WorkerCoordinator(
            registry=self.registry, plans=self.plans, reports=self.reports, operations=self.sink
        )
        self._base = base

    def tearDown(self):
        self._tmp.cleanup()

    def test_pull_uses_plan_store_and_report_uses_report_store(self):
        self.registry.register(worker_id="w", hostname="w")
        self.registry.assign("w", "op-1")
        self.plans.put("op-1", b"<jmeterTestPlan/>", 30.0)

        # PlanStore.get via the coordinator's pull path.
        assignment = self.coord.pull_assignment("w", "op-1")
        self.assertEqual(base64.b64decode(assignment.plan_b64), b"<jmeterTestPlan/>")
        self.assertEqual(assignment.timeout_seconds, 30.0)

        # ReportStore.save via the coordinator's report path.
        self.coord.report(
            OperationReport(
                operation_id="op-1",
                status="completed",
                exit_code=0,
                artifacts=[ArtifactPayload(kind="log", name="jmeter.log", content_b64=base64.b64encode(b"log").decode())],
            )
        )
        self.assertIn(("complete", "op-1"), self.sink.calls)
        self.assertTrue((self._base / "reports" / "op-1" / "report.json").is_file())
        self.assertEqual(
            (self._base / "reports" / "op-1" / "artifacts" / "jmeter.log").read_bytes(), b"log"
        )


if __name__ == "__main__":
    unittest.main()
