"""Unit tests for WorkerCoordinator — the worker-facing API logic (ADR-0010 §4.2)."""

import base64
import unittest

from app.integrations.performance.registry import (
    PerformanceWorkerRegistry,
    WorkerNotRegisteredError,
)
from app.schemas.performance.report import OperationReport
from app.schemas.performance.worker import (
    PerformanceWorkerHeartbeatRequest,
    PerformanceWorkerRegisterRequest,
    WorkerHealth,
)
from app.services.performance.worker_api import (
    AssignmentMismatchError,
    PlanNotFoundError,
    StoredPlan,
    WorkerCoordinator,
)


class _FakePlanStore:
    def __init__(self):
        self.plans = {}

    def get(self, operation_id):
        try:
            return self.plans[operation_id]
        except KeyError as exc:
            raise PlanNotFoundError(operation_id) from exc


class _FakeReportStore:
    def __init__(self):
        self.saved = []

    def save(self, report):
        self.saved.append(report)


class _FakeStatusSink:
    def __init__(self):
        self.calls = []

    def complete(self, operation_id):
        self.calls.append(("complete", operation_id))

    def fail(self, operation_id, error):
        self.calls.append(("fail", operation_id, error))

    def cancel(self, operation_id):
        self.calls.append(("cancel", operation_id))


class WorkerCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.registry = PerformanceWorkerRegistry()
        self.plans = _FakePlanStore()
        self.reports = _FakeReportStore()
        self.sink = _FakeStatusSink()
        self.coord = WorkerCoordinator(
            registry=self.registry,
            plans=self.plans,
            reports=self.reports,
            operations=self.sink,
            min_compatible_version="1.0",
        )

    def _register(self, worker_id="w", hostname="w", version="1.0"):
        return self.coord.register(
            PerformanceWorkerRegisterRequest(worker_id=worker_id, hostname=hostname, version=version)
        )

    def test_register_returns_min_compatible_version(self):
        resp = self._register()
        self.assertEqual(resp.worker_id, "w")
        self.assertEqual(resp.min_compatible_version, "1.0")

    def test_heartbeat_surfaces_assignment_and_cancel(self):
        self._register()
        self.registry.assign("w", "op-1")
        self.registry.request_cancel("w", "op-1")
        resp = self.coord.heartbeat(
            PerformanceWorkerHeartbeatRequest(worker_id="w", health=WorkerHealth(cpu_percent=10))
        )
        self.assertEqual(resp.assignment, "op-1")
        self.assertTrue(resp.cancel_requested)

    def test_heartbeat_unknown_worker_raises(self):
        with self.assertRaises(WorkerNotRegisteredError):
            self.coord.heartbeat(PerformanceWorkerHeartbeatRequest(worker_id="ghost"))

    def test_pull_returns_plan_for_held_operation(self):
        self._register()
        self.registry.assign("w", "op-1")
        self.plans.plans["op-1"] = StoredPlan(plan=b"<jmeterTestPlan/>", timeout_seconds=30.0)
        resp = self.coord.pull_assignment("w", "op-1")
        self.assertEqual(base64.b64decode(resp.plan_b64), b"<jmeterTestPlan/>")
        self.assertEqual(resp.timeout_seconds, 30.0)

    def test_pull_for_unheld_operation_is_rejected(self):
        self._register()
        self.registry.assign("w", "op-1")
        with self.assertRaises(AssignmentMismatchError):
            self.coord.pull_assignment("w", "op-OTHER")

    def test_pull_missing_plan_raises(self):
        self._register()
        self.registry.assign("w", "op-1")
        with self.assertRaises(PlanNotFoundError):
            self.coord.pull_assignment("w", "op-1")

    def test_report_completed_persists_transitions_and_releases(self):
        self._register()
        self.registry.assign("w", "op-1")
        self.coord.report(OperationReport(operation_id="op-1", status="completed", exit_code=0))
        self.assertEqual(len(self.reports.saved), 1)          # persisted durably
        self.assertIn(("complete", "op-1"), self.sink.calls)  # transitioned
        self.assertTrue(self.registry.get("w").is_idle)       # worker released

    def test_report_failed_calls_fail_with_error(self):
        self._register()
        self.registry.assign("w", "op-1")
        self.coord.report(
            OperationReport(operation_id="op-1", status="failed", exit_code=1, error="boom")
        )
        self.assertIn(("fail", "op-1", "boom"), self.sink.calls)

    def test_report_cancelled_calls_cancel(self):
        self._register()
        self.registry.assign("w", "op-1")
        self.coord.report(OperationReport(operation_id="op-1", status="cancelled", exit_code=None))
        self.assertIn(("cancel", "op-1"), self.sink.calls)


class RouterBuildTests(unittest.TestCase):
    def test_router_exposes_the_four_worker_routes(self):
        from app.routers.public.performance_worker_router import (
            build_performance_worker_router,
        )

        coord = WorkerCoordinator(
            registry=PerformanceWorkerRegistry(),
            plans=_FakePlanStore(),
            reports=_FakeReportStore(),
            operations=_FakeStatusSink(),
        )
        router = build_performance_worker_router(coord)
        paths = {route.path for route in router.routes}
        self.assertEqual(
            paths,
            {
                "/performance/workers/register",
                "/performance/workers/heartbeat",
                "/performance/workers/pull",
                "/performance/operations/report",
            },
        )


if __name__ == "__main__":
    unittest.main()
