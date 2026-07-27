"""C3.6 — the ``execute_performance_test`` MCP tool (ADR-0010 §4.12).

Covers the tool's contract: retrieve the stored plan, enforce preconditions,
create a QUEUED Performance operation stamped with the correct operation type,
return the operation id (== plan_id) — and prove it enqueues rather than
executes. The enqueue→dispatch test is the Gate-B server-side proof: the type the
tool stamps is byte-identical through the DAO, the dispatcher's scoped read, and
assignment, and the wired dispatcher assigns the operation to a worker (INV12/13).
"""

import ast
import unittest
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.constants.batch import BatchType
from app.domain.lifecycle import OperationPhase
from app.dao.operation_record import OperationRecord
from app.schemas.performance.operation_type import PerformanceOperationType
from app.services.performance.dispatcher import PerformanceDispatcher
from app.services.performance.execute_tool import (
    PerformanceExecuteService,
    PlanAlreadyExecutedError,
)
from app.services.performance.worker_api import PlanNotFoundError, StoredPlan
from app.routers.mcp.performance_router import (
    execute_performance_test,
    get_performance_execute_service,
    performance_router,
)

_PERF_TYPE = PerformanceOperationType.PERFORMANCE_TEST.value


class _FakePlanStore:
    """Read side keyed by operation_id; a plan exists only for known ids."""

    def __init__(self, present):
        self._present = set(present)

    def get(self, operation_id: str) -> StoredPlan:
        if operation_id not in self._present:
            raise PlanNotFoundError(operation_id)
        return StoredPlan(plan=b"<jmeterTestPlan/>", timeout_seconds=300.0)


class _FakeOperationService:
    """Minimal create/get surface backed by an in-memory queue of records."""

    def __init__(self):
        self.records = {}

    def create(self, batch_type, metadata=None, log_path=None, operation_id=None):
        self.records[operation_id] = OperationRecord(
            operation_id=operation_id,
            status=OperationPhase.QUEUED,
            batch_type=batch_type,
            metadata=metadata or {},
        )
        return operation_id

    def get(self, operation_id):
        return self.records.get(operation_id)


class ExecuteServiceTests(unittest.TestCase):
    def setUp(self):
        self.ops = _FakeOperationService()
        self.service = PerformanceExecuteService(_FakePlanStore({"P1"}), self.ops)

    def test_enqueues_queued_operation_with_identity_id_and_stamped_type(self):
        op_id = self.service.execute("P1")
        self.assertEqual(op_id, "P1")  # operation_id == plan_id (identity mapping)
        record = self.ops.records["P1"]
        self.assertEqual(record.status, OperationPhase.QUEUED)
        self.assertEqual(record.batch_type, BatchType.PERFORMANCE_TEST)
        self.assertEqual(record.metadata["operation_type"], _PERF_TYPE)
        self.assertEqual(record.metadata["plan_id"], "P1")

    def test_missing_plan_raises_and_enqueues_nothing(self):
        with self.assertRaises(PlanNotFoundError):
            self.service.execute("UNKNOWN")
        self.assertEqual(self.ops.records, {})

    def test_already_executed_plan_is_rejected(self):
        self.service.execute("P1")
        with self.assertRaises(PlanAlreadyExecutedError):
            self.service.execute("P1")
        self.assertEqual(len(self.ops.records), 1)  # not duplicated


class _SharedQueue:
    """In-memory Operations store with the type-scoped queued read (INV12)."""

    def __init__(self, service: _FakeOperationService):
        self._service = service

    def get_queued_operations(self, types=None):
        queued = [
            r for r in self._service.records.values() if r.status == OperationPhase.QUEUED
        ]
        if types is None:
            return queued
        return [r for r in queued if r.metadata.get("operation_type") in types]


class _FakePool:
    def __init__(self):
        self.assigned = []

    def try_assign(self, operation_id):
        self.assigned.append(operation_id)
        return type("W", (), {"worker_id": "w"})()


class _DispatchOps:
    """Records dispatcher-driven transitions without mutating engine identity."""

    def __init__(self, queue_service: _FakeOperationService):
        self._queue = queue_service
        self.started = []

    def start(self, operation_id):
        self.started.append(operation_id)
        self._queue.records[operation_id].status = OperationPhase.RUNNING

    def fail(self, operation_id, error):
        raise AssertionError(f"dispatcher failed a supported op: {operation_id}")


class EnqueueToDispatchIntegrationTests(unittest.TestCase):
    """Gate B (server-side): tool → OperationService → DAO → dispatcher → assignment."""

    def test_operation_type_is_byte_identical_through_to_assignment(self):
        ops = _FakeOperationService()
        service = PerformanceExecuteService(_FakePlanStore({"P1"}), ops)

        # 1) Tool stamps the type and enqueues.
        op_id = service.execute("P1")
        stamped = ops.records[op_id].metadata["operation_type"]
        self.assertEqual(stamped, _PERF_TYPE)

        # 2) A Performance-scoped dispatcher (real class) reads the shared queue
        #    and assigns via the pool. Its supported set derives from the enum —
        #    the same single source of truth the tool stamped from.
        queue = _SharedQueue(ops)
        pool = _FakePool()
        dispatch_ops = _DispatchOps(ops)
        dispatcher = PerformanceDispatcher(
            operation_dao=queue,
            operation_service=dispatch_ops,
            pool_manager=pool,
            supported_operation_types=frozenset(
                t.value for t in PerformanceOperationType
            ),
            queue_poll_interval_seconds=1.0,
            heartbeat_sweep_interval_seconds=1.0,
            heartbeat_timeout_seconds=1.0,
        )
        dispatcher.dispatch_pending()

        # 3) The operation was assigned (the scoped read matched the stamped type)
        #    and moved QUEUED → RUNNING — the dispatcher's job ends at assignment.
        self.assertEqual(pool.assigned, [op_id])
        self.assertEqual(dispatch_ops.started, [op_id])
        self.assertEqual(ops.records[op_id].status, OperationPhase.RUNNING)
        # INV13: the engine identity was read, never rewritten.
        self.assertEqual(ops.records[op_id].metadata["operation_type"], stamped)

    def test_foreign_typed_operation_is_ignored_by_the_performance_dispatcher(self):
        ops = _FakeOperationService()
        # A foreign (ZAP) operation sitting in the same queue.
        ops.create(batch_type="api_scan", operation_id="zap-1", metadata={"operation_type": "api_scan"})
        pool = _FakePool()
        dispatcher = PerformanceDispatcher(
            operation_dao=_SharedQueue(ops),
            operation_service=_DispatchOps(ops),
            pool_manager=pool,
            supported_operation_types=frozenset(t.value for t in PerformanceOperationType),
            queue_poll_interval_seconds=1.0,
            heartbeat_sweep_interval_seconds=1.0,
            heartbeat_timeout_seconds=1.0,
        )
        dispatcher.dispatch_pending()
        self.assertEqual(pool.assigned, [])  # foreign op never touched (INV12)


class ExecuteEndpointTests(unittest.TestCase):
    def setUp(self):
        self.ops = _FakeOperationService()
        service = PerformanceExecuteService(_FakePlanStore({"P1"}), self.ops)
        app = FastAPI()
        app.include_router(performance_router)
        app.dependency_overrides[get_performance_execute_service] = lambda: service
        self.client = TestClient(app)

    def _post(self, plan_id):
        return self.client.post("/performance/execute_test", json={"plan_id": plan_id})

    def test_valid_plan_returns_queued_operation_id(self):
        resp = self._post("P1")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()["result"]
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["operation_id"], "P1")

    def test_unknown_plan_is_404(self):
        resp = self._post("NOPE")
        self.assertEqual(resp.status_code, 404)

    def test_already_executed_plan_is_409(self):
        self.assertEqual(self._post("P1").status_code, 200)
        self.assertEqual(self._post("P1").status_code, 409)

    def test_missing_plan_id_is_422(self):
        self.assertEqual(self.client.post("/performance/execute_test", json={}).status_code, 422)


class ScopeGuardTests(unittest.TestCase):
    """Structural proof the tool enqueues but never executes: it imports no
    runtime / worker-execution / dispatcher / pool machinery."""

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

    def test_execute_service_has_no_execution_imports(self):
        for mod in self._imports("app/services/performance/execute_tool.py"):
            for forbidden in self._FORBIDDEN_PREFIXES:
                self.assertFalse(
                    mod == forbidden.rstrip(".") or mod.startswith(forbidden),
                    msg=f"execute_tool imports execution machinery: {mod}",
                )

    def test_execute_service_reads_no_settings(self):
        for mod in self._imports("app/services/performance/execute_tool.py"):
            self.assertFalse(mod == "app.core.config" or mod.startswith("app.core.config."))


if __name__ == "__main__":
    unittest.main()
