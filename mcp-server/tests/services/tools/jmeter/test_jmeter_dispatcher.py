"""JMeter dispatcher: lane isolation, assignment, and the heartbeat sweep.

Drives one poll tick at a time rather than starting the background threads, so
the assertions are deterministic and the suite stays fast.
"""

import unittest
from datetime import datetime, timedelta, timezone

from app.constants.batch import BatchType
from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase
from app.integrations.jmeter.pool import JMeterWorkerPoolManager
from app.integrations.jmeter.registry import JMeterWorkerRegistry
from app.integrations.jmeter.scheduler import RoundRobinJMeterWorkerScheduler
from app.services.tools.jmeter.execution.dispatcher import JMeterDispatcher

_NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)


def _queued(operation_id: str, batch_type: str, age: int = 0, metadata=None):
    return OperationRecord(
        operation_id=operation_id,
        status=OperationPhase.QUEUED,
        batch_type=batch_type,
        created_at=_NOW + timedelta(seconds=age),
        metadata=metadata
        if metadata is not None
        else {
            "request": {
                "target_url": "https://api.example.com/v1/orders",
                "method": "GET",
                "thread_count": 10,
                "ramp_up_seconds": 5,
                "hold_seconds": 60,
            }
        },
    )


class _LaneRecordingDAO:
    """Stand-in for the real DAO: same lane filter, same FIFO order.

    Mirrors ``BaseOperationDAO.get_queued_operations`` deliberately — filter to
    the caller's lane, then oldest-first by ``created_at`` — so a dispatcher
    test sees the same ordering production would hand it. It additionally
    records which lane was asked for, which is what the isolation tests assert.
    """

    def __init__(self, records):
        self._records = records
        self.requested_lanes = []

    def get_queued_operations(self, batch_types):
        self.requested_lanes.append(frozenset(batch_types))
        lane = frozenset(batch_types)
        matching = [
            r
            for r in self._records
            if r.status == OperationPhase.QUEUED and r.batch_type in lane
        ]
        return sorted(matching, key=lambda r: r.created_at)


class _RecordingOperationService:
    def __init__(self):
        self.failed = []

    def fail(self, operation_id, error):
        self.failed.append((operation_id, error))


class _RecordingRuntime:
    """Stands in for JMeterRuntime; records what it was handed."""

    def __init__(self, raises=None):
        self.runs = []
        self._raises = raises

    def run(self, operation_id, request, worker):
        self.runs.append((operation_id, request, worker))
        if self._raises is not None:
            raise self._raises


def _dispatcher(dao, *, workers=(), runtime=None, operations=None):
    registry = JMeterWorkerRegistry()
    for worker_id in workers:
        registry.register(
            worker_id=worker_id,
            hostname=worker_id,
            endpoint=f"http://{worker_id}:8090",
            port=8090,
        )
    pool = JMeterWorkerPoolManager(registry, RoundRobinJMeterWorkerScheduler())
    return JMeterDispatcher(
        operation_dao=dao,
        operation_service=operations or _RecordingOperationService(),
        pool_manager=pool,
        runtime=runtime or _RecordingRuntime(),
        queue_poll_interval_seconds=1.0,
        heartbeat_sweep_interval_seconds=1.0,
        heartbeat_timeout_seconds=120.0,
    )


class QueueIsolationRegressionTests(unittest.TestCase):
    """The dispatcher must never consume a non-JMeter operation."""

    def test_only_the_jmeter_lane_is_requested_from_the_dao(self):
        dao = _LaneRecordingDAO([])
        dispatcher = _dispatcher(dao)
        dispatcher._dispatch_queued_operations()

        self.assertEqual([BatchType.ALL_JMETER_TYPES], dao.requested_lanes)

    def test_zap_operations_are_never_dispatched(self):
        dao = _LaneRecordingDAO(
            [
                _queued("zap-1", BatchType.API_SCAN),
                _queued("zap-2", BatchType.SUITE_SCAN),
                _queued("zap-3", BatchType.INTERACTIVE_SCAN),
            ]
        )
        runtime = _RecordingRuntime()
        operations = _RecordingOperationService()
        dispatcher = _dispatcher(
            dao, workers=("jmeter-1",), runtime=runtime, operations=operations
        )

        dispatcher._dispatch_queued_operations()

        # Not run, and — critically — not failed either. Invisible, not consumed.
        self.assertEqual([], runtime.runs)
        self.assertEqual([], operations.failed)

    def test_the_lane_is_not_configurable_away(self):
        self.assertEqual(BatchType.ALL_JMETER_TYPES, JMeterDispatcher.LANE)
        self.assertFalse(JMeterDispatcher.LANE & BatchType.ALL_SCAN_TYPES)


class DispatchTests(unittest.TestCase):
    def test_a_queued_operation_is_assigned_and_handed_to_the_runtime(self):
        dao = _LaneRecordingDAO([_queued("op-1", BatchType.JMETER_TEST)])
        runtime = _RecordingRuntime()
        dispatcher = _dispatcher(dao, workers=("jmeter-1",), runtime=runtime)

        dispatcher._dispatch_queued_operations()

        self.assertEqual(1, len(runtime.runs))
        operation_id, request, worker = runtime.runs[0]
        self.assertEqual("op-1", operation_id)
        self.assertEqual("jmeter-1", worker.worker_id)
        # The persisted request was reconstructed from the row.
        self.assertEqual(10, request.thread_count)

    def test_operations_are_dispatched_oldest_first(self):
        dao = _LaneRecordingDAO(
            [
                _queued("newer", BatchType.JMETER_TEST, age=60),
                _queued("older", BatchType.JMETER_TEST, age=0),
            ]
        )
        runtime = _RecordingRuntime()
        dispatcher = _dispatcher(dao, workers=("jmeter-1", "jmeter-2"), runtime=runtime)

        dispatcher._dispatch_queued_operations()

        self.assertEqual(["older", "newer"], [run[0] for run in runtime.runs])

    def test_without_a_free_worker_the_operation_stays_queued(self):
        dao = _LaneRecordingDAO([_queued("op-1", BatchType.JMETER_TEST)])
        runtime = _RecordingRuntime()
        operations = _RecordingOperationService()
        dispatcher = _dispatcher(dao, runtime=runtime, operations=operations)

        dispatcher._dispatch_queued_operations()

        # Nothing ran and nothing failed — it is retried on the next tick.
        self.assertEqual([], runtime.runs)
        self.assertEqual([], operations.failed)

    def test_more_operations_than_workers_assigns_only_what_fits(self):
        dao = _LaneRecordingDAO(
            [
                _queued("op-1", BatchType.JMETER_TEST, age=0),
                _queued("op-2", BatchType.JMETER_TEST, age=1),
            ]
        )
        # The stub runtime returns without releasing, so the worker stays busy.
        runtime = _RecordingRuntime()
        dispatcher = _dispatcher(dao, workers=("jmeter-1",), runtime=runtime)

        dispatcher._dispatch_queued_operations()

        self.assertEqual(["op-1"], [run[0] for run in runtime.runs])

    def test_unusable_metadata_fails_the_operation_and_frees_the_worker(self):
        dao = _LaneRecordingDAO(
            [_queued("op-1", BatchType.JMETER_TEST, metadata={"request": {"bogus": 1}})]
        )
        operations = _RecordingOperationService()
        dispatcher = _dispatcher(dao, workers=("jmeter-1",), operations=operations)

        dispatcher._dispatch_queued_operations()

        self.assertEqual(1, len(operations.failed))
        self.assertIn("op-1", operations.failed[0][0])
        # The worker must not be stranded holding an operation that can never run.
        self.assertIsNone(dispatcher._pool_manager.registry.get("jmeter-1").op_id)

    def test_a_raising_runtime_fails_the_operation_and_frees_the_worker(self):
        dao = _LaneRecordingDAO([_queued("op-1", BatchType.JMETER_TEST)])
        operations = _RecordingOperationService()
        dispatcher = _dispatcher(
            dao,
            workers=("jmeter-1",),
            runtime=_RecordingRuntime(raises=RuntimeError("worker exploded")),
            operations=operations,
        )

        dispatcher._dispatch_queued_operations()

        self.assertEqual(1, len(operations.failed))
        self.assertIn("worker exploded", operations.failed[0][1])
        self.assertIsNone(dispatcher._pool_manager.registry.get("jmeter-1").op_id)

    def test_an_unimplemented_runtime_fails_with_an_explanatory_message(self):
        # Until Phase 3 this is the path every assignment takes; the operation
        # must reach a terminal state with a message that says why.
        dao = _LaneRecordingDAO([_queued("op-1", BatchType.JMETER_TEST)])
        operations = _RecordingOperationService()
        dispatcher = _dispatcher(
            dao,
            workers=("jmeter-1",),
            runtime=_RecordingRuntime(raises=NotImplementedError()),
            operations=operations,
        )

        dispatcher._dispatch_queued_operations()

        self.assertEqual(1, len(operations.failed))
        self.assertIn("not available yet", operations.failed[0][1])
        self.assertIsNone(dispatcher._pool_manager.registry.get("jmeter-1").op_id)


class HeartbeatSweepTests(unittest.TestCase):
    def test_a_dead_worker_fails_the_operation_it_was_running(self):
        dao = _LaneRecordingDAO([])
        operations = _RecordingOperationService()
        dispatcher = _dispatcher(dao, workers=("jmeter-1",), operations=operations)

        registry = dispatcher._pool_manager.registry
        registry.assign("jmeter-1", "op-1")
        with registry._lock:  # pylint: disable=protected-access
            info = registry._workers["jmeter-1"]  # pylint: disable=protected-access
            registry._workers["jmeter-1"] = info.model_copy(  # pylint: disable=protected-access
                update={"last_heartbeat": datetime.now(timezone.utc) - timedelta(seconds=999)}
            )

        dispatcher._sweep_expired_workers()

        self.assertEqual(1, len(operations.failed))
        operation_id, reason = operations.failed[0]
        self.assertEqual("op-1", operation_id)
        self.assertIn("heartbeat", reason.lower())

    def test_a_healthy_pool_sweeps_clean(self):
        dao = _LaneRecordingDAO([])
        operations = _RecordingOperationService()
        dispatcher = _dispatcher(dao, workers=("jmeter-1",), operations=operations)

        dispatcher._sweep_expired_workers()

        self.assertEqual([], operations.failed)


class DispatcherLifecycleTests(unittest.TestCase):
    def test_start_is_idempotent_and_stop_is_clean(self):
        dispatcher = _dispatcher(_LaneRecordingDAO([]))
        dispatcher.start()
        dispatcher.start()  # second call must be a no-op, not a second thread pair
        try:
            self.assertIsNotNone(dispatcher._queue_thread)
        finally:
            dispatcher.stop()
        self.assertIsNone(dispatcher._queue_thread)


if __name__ == "__main__":
    unittest.main()
