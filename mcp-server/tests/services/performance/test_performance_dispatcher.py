"""Unit tests for the PerformanceDispatcher (ADR-0010 §4.4/§4.12).

Verifies it orchestrates assignment only — polls scoped, assigns via the pool,
transitions to RUNNING, sweeps orphans — and never reaches into execution.
"""

import ast
import unittest
from pathlib import Path

import app.services.performance.dispatcher as dispatcher_module
from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase
from app.services.performance.dispatcher import PerformanceDispatcher

_PERF_TYPE = "performance_test"


def _op(operation_id, operation_type=_PERF_TYPE):
    return OperationRecord(
        operation_id=operation_id,
        status=OperationPhase.QUEUED,
        batch_type=operation_type,
        metadata={"operation_type": operation_type},
    )


class _Queue:
    def __init__(self, ops):
        self._ops = ops
        self.scoped_with = None

    def get_queued_operations(self, types=None):
        self.scoped_with = types
        if types is None:
            return list(self._ops)
        return [o for o in self._ops if o.metadata.get("operation_type") in types]


class _Pool:
    def __init__(self, *, assign=True, orphans=()):
        self.assigned = []
        self._assign = assign
        self._orphans = list(orphans)

    def try_assign(self, operation_id):
        if not self._assign:
            return None
        self.assigned.append(operation_id)
        return type("W", (), {"worker_id": "w"})()

    def sweep_expired(self, timeout_seconds):
        return self._orphans


class _OpService:
    def __init__(self):
        self.started = []
        self.failed = []

    def start(self, operation_id):
        self.started.append(operation_id)

    def fail(self, operation_id, error):
        self.failed.append((operation_id, error))


def _dispatcher(queue, pool, ops):
    return PerformanceDispatcher(
        operation_dao=queue,
        operation_service=ops,
        pool_manager=pool,
        supported_operation_types=frozenset({_PERF_TYPE}),
        queue_poll_interval_seconds=1.0,
        heartbeat_sweep_interval_seconds=1.0,
        heartbeat_timeout_seconds=1.0,
    )


class DispatchPendingTests(unittest.TestCase):
    def test_polls_scoped_and_assigns_then_starts(self):
        queue = _Queue([_op("perf-1"), _op("perf-2")])
        pool = _Pool()
        ops = _OpService()
        _dispatcher(queue, pool, ops).dispatch_pending()

        self.assertEqual(queue.scoped_with, frozenset({_PERF_TYPE}))  # scoped read (INV12)
        self.assertEqual(pool.assigned, ["perf-1", "perf-2"])          # assigned via pool
        self.assertEqual(ops.started, ["perf-1", "perf-2"])           # QUEUED -> RUNNING
        self.assertEqual(ops.failed, [])                              # nothing failed

    def test_no_fit_worker_leaves_operation_queued(self):
        queue = _Queue([_op("perf-1")])
        pool = _Pool(assign=False)
        ops = _OpService()
        _dispatcher(queue, pool, ops).dispatch_pending()

        self.assertEqual(pool.assigned, [])
        self.assertEqual(ops.started, [])  # not started; stays QUEUED for next tick

    def test_never_fails_operations_it_does_not_see(self):
        # A foreign op in the shared store is filtered out by the scoped read.
        queue = _Queue([_op("perf-1"), _op("zap-1", operation_type="api_scan")])
        pool = _Pool()
        ops = _OpService()
        _dispatcher(queue, pool, ops).dispatch_pending()

        self.assertEqual(pool.assigned, ["perf-1"])
        self.assertEqual(ops.failed, [])


class SweepTests(unittest.TestCase):
    def test_sweep_fails_orphaned_operations(self):
        pool = _Pool(orphans=[("w-1", "perf-9")])
        ops = _OpService()
        _dispatcher(_Queue([]), pool, ops).sweep_expired_workers()
        self.assertEqual(len(ops.failed), 1)
        self.assertEqual(ops.failed[0][0], "perf-9")


class DispatcherPurityTests(unittest.TestCase):
    """The dispatcher orchestrates only — it never touches execution."""

    def test_imports_no_runtime_engine_or_subprocess(self):
        src = Path(dispatcher_module.__file__).read_text(encoding="utf-8")
        names = []
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                names += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
        joined = " ".join(names).lower()
        for forbidden in ("performance.runtime", "performance_runtime", "jmeter", "subprocess"):
            self.assertNotIn(forbidden, joined)


if __name__ == "__main__":
    unittest.main()
