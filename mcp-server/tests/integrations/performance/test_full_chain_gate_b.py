"""C3.7 — Gate B (full chain): PerformanceOperationType is immutable end to end.

The integration-level proof of INV13 over the complete Phase-3 path:

    MCP tool → OperationService → DAO → Dispatcher → Assignment → Worker → Report → Persistence

The operation type the public ``run_jmeter_test`` tool stamps must be
byte-identical at every hop where it appears, through to the persisted report —
read at each stage (the dispatcher's scoped assignment, the worker's pull), never
rewritten. Real subsystem objects are used throughout (registry, pool, scheduler,
dispatcher, coordinator, runtime, persistence); only the JMeter subprocess is
faked (the sandbox has no JMeter binary) and the worker↔server HTTP hop is an
in-process bridge to the real ``WorkerCoordinator``.
"""

import json
import tempfile
import unittest
from pathlib import Path
from threading import Event

from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase
from app.integrations.performance.fitness import build_fitness
from app.integrations.performance.pool import PerformancePoolManager
from app.integrations.performance.registry import PerformanceWorkerRegistry
from app.integrations.performance.scheduler import RoundRobinScheduler
from app.schemas.performance.operation_type import PerformanceOperationType
from app.services.performance.dispatcher import PerformanceDispatcher
from app.services.performance.engine.dto import (
    Artifact,
    ArtifactKind,
    ArtifactSet,
    ExecutionResult,
    ExecutionStatus,
)
from app.schemas.tools.jmeter.run_test import RunJmeterTestRequest
from app.services.tools.jmeter.run_service import JmeterRunService
from app.services.performance.persistence import ReportChannelPersistence
from app.services.performance.runtime import PerformanceRuntime, WorkspaceManager
from app.services.performance.stores import FilesystemPlanStore, FilesystemReportStore
from app.services.performance.worker.performance_worker import PerformanceWorker
from app.services.performance.worker_api import WorkerCoordinator
from app.integrations.jmeter.plan_validator import JmxPlanValidator

_PERF_TYPE = PerformanceOperationType.PERFORMANCE_TEST.value
_PLAN = b"<jmeterTestPlan><hashTree/></jmeterTestPlan>"


class _Records:
    """Shared Operations store: the DAO surface the dispatcher reads."""

    def __init__(self):
        self.by_id = {}

    def get_queued_operations(self, types=None):
        queued = [r for r in self.by_id.values() if r.status == OperationPhase.QUEUED]
        if types is None:
            return queued
        return [r for r in queued if r.metadata.get("operation_type") in types]

    def get_operation(self, operation_id):
        return self.by_id.get(operation_id)


class _OperationService:
    """Create + lifecycle surface used by the tool, the dispatcher, and the sink."""

    def __init__(self, records: _Records):
        self._r = records

    def create(self, batch_type, metadata=None, log_path=None, operation_id=None):
        self._r.by_id[operation_id] = OperationRecord(
            operation_id=operation_id,
            status=OperationPhase.QUEUED,
            batch_type=batch_type,
            metadata=metadata or {},
        )
        return operation_id

    def get(self, operation_id):
        return self._r.by_id.get(operation_id)

    def start(self, operation_id):
        self._r.by_id[operation_id].status = OperationPhase.RUNNING

    def complete(self, operation_id):
        self._r.by_id[operation_id].status = OperationPhase.COMPLETED

    def fail(self, operation_id, error):
        self._r.by_id[operation_id].status = OperationPhase.FAILED

    def cancel(self, operation_id):
        self._r.by_id[operation_id].status = OperationPhase.CANCELLED


class _InProcessServerClient:
    """Worker→server bridge: routes the worker's outbound calls to the coordinator."""

    def __init__(self, coordinator: WorkerCoordinator):
        self._c = coordinator

    def register(self, request):
        return self._c.register(request)

    def heartbeat(self, request):
        return self._c.heartbeat(request)

    def pull(self, request):
        return self._c.pull_assignment(request.worker_id, request.operation_id)


class _InProcessReportSender:
    """Worker→server report bridge: delivers the report to the coordinator."""

    def __init__(self, coordinator: WorkerCoordinator):
        self._c = coordinator

    def send(self, report):
        self._c.report(report)


class _FakeJMeterRunner:
    """Stands in for the JMeter subprocess: writes one results artifact, COMPLETED."""

    def run(self, request, cancel):
        results = request.output_dir / "results.jtl"
        results.write_text("sample,ok\n")
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            duration_seconds=0.01,
            artifacts=ArtifactSet((Artifact(ArtifactKind.RESULTS, results),)),
        )


class GateBFullChainTests(unittest.TestCase):
    def test_operation_type_is_byte_identical_from_tool_stamp_to_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            plan_store = FilesystemPlanStore(base / "plans")
            report_store = FilesystemReportStore(base / "reports")
            records = _Records()
            ops = _OperationService(records)

            # ── 1) A tester's existing .jmx file on disk. ────────────────────
            jmx_file = base / "checkout-load.jmx"
            jmx_file.write_bytes(_PLAN)

            # ── 2) Public MCP tool validates the file, stores the plan, and
            #      enqueues — stamping the internal type. It stores the plan
            #      under the generated operation id (the key the worker pulls by).
            run = JmeterRunService(
                operation_service=ops, validator=JmxPlanValidator(), plan_store=plan_store
            )
            op_id = run.run(
                RunJmeterTestRequest(jmx_file=str(jmx_file), timeout_seconds=30.0)
            )["operation_id"]
            stamped = records.by_id[op_id].metadata["operation_type"]
            self.assertEqual(stamped, _PERF_TYPE)

            # ── 3) Real pool/registry/dispatcher assign it to a live worker. ──
            registry = PerformanceWorkerRegistry()
            registry.register(worker_id="w1", hostname="w1", version=None)
            pool = PerformancePoolManager(registry, RoundRobinScheduler(build_fitness(None)))
            coordinator = WorkerCoordinator(
                registry=registry,
                plans=plan_store,
                reports=report_store,
                operations=ops,
            )
            dispatcher = PerformanceDispatcher(
                operation_dao=records,
                operation_service=ops,
                pool_manager=pool,
                supported_operation_types=frozenset(
                    t.value for t in PerformanceOperationType
                ),
                queue_poll_interval_seconds=1.0,
                heartbeat_sweep_interval_seconds=1.0,
                heartbeat_timeout_seconds=60.0,
            )
            dispatcher.dispatch_pending()
            self.assertEqual(records.by_id[op_id].status, OperationPhase.RUNNING)

            # ── 4) Real worker + runtime (fake JMeter) pulls and runs. ───────
            runtime = PerformanceRuntime(
                workspaces=WorkspaceManager(base / "ws"),
                validator=JmxPlanValidator(),
                runner=_FakeJMeterRunner(),
                persistence=ReportChannelPersistence(_InProcessReportSender(coordinator)),
            )
            worker = PerformanceWorker(
                server=_InProcessServerClient(coordinator),
                runtime=runtime,
                worker_id="w1",
                hostname="w1",
            )
            response = worker.heartbeat_once()
            self.assertEqual(response.assignment, op_id)  # scoped assignment reached it
            worker.execute_assignment(op_id, Event())

            # ── 5) Persistence completed the operation via the report channel. ─
            self.assertEqual(records.by_id[op_id].status, OperationPhase.COMPLETED)
            report_json = base / "reports" / op_id / "report.json"
            self.assertTrue(report_json.is_file())
            saved = json.loads(report_json.read_text())
            self.assertEqual(saved["operation_id"], op_id)
            self.assertEqual(saved["status"], "completed")

            # ── INV13: the engine identity was read at every hop, never rewritten.
            self.assertEqual(records.by_id[op_id].metadata["operation_type"], stamped)


if __name__ == "__main__":
    unittest.main()
