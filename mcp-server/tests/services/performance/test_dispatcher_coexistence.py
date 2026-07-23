"""Shared-queue coexistence regression guard (ADR-0010 §4.12, INV12 + INV13).

The permanent behavioural contract for multiple dispatchers over ONE shared
Operations queue. It is engine-neutral: each engine contributes a dispatcher and
a declared supported operation type set, and the same assertions apply. A future
engine (Burp, Trivy, Semgrep, Nuclei, MobSF, …) reuses this exact contract by
adding its dispatcher + supported set to the wiring below.

Active as of Component 5: the ZAP dispatcher ignores foreign operations (§4.12
scoping) and the Performance dispatcher exists, so this test now passes and
guards the invariant permanently. (It was authored xfail ahead of Component 5;
the marker was removed once both landed.)

Contract verified:
  ✓ each dispatcher processes only its supported type set (INV12)
  ✓ no operation is skipped                (union of assigned == all)
  ✓ no operation is dispatched twice       (assigned sets are disjoint)
  ✓ no foreign operation is failed
  ✓ every operation is assigned exactly once
  ✓ an operation's engine identity never changes (INV13)
"""

import unittest

import pytest

pytest.importorskip("zapv2")  # the ZAP dispatcher pulls the zap client chain

from pydantic import BaseModel  # noqa: E402

from app.dao.operation_record import OperationRecord  # noqa: E402
from app.domain.lifecycle import OperationPhase  # noqa: E402
from app.services.tools.owasp_zap.execution.execution_strategy import (  # noqa: E402
    ExecutionStrategy,
)
from app.services.tools.owasp_zap.execution.handler import ZapOperation  # noqa: E402
from app.services.tools.owasp_zap.execution.operation_type import (  # noqa: E402
    ZapOperationType,
)
from app.services.tools.owasp_zap.execution.registry import (  # noqa: E402
    ZapOperationRegistry,
)
from app.services.tools.owasp_zap.execution.dispatcher import (  # noqa: E402
    OwaspZapDispatcher,
)

_ZAP_TYPE = "api_scan"
_PERF_TYPE = "performance_test"


class _Req(BaseModel):
    value: str = "x"


class _RecordingHandler:
    def __init__(self):
        self.executed = []

    def execute(self, operation_id, request, context):
        self.executed.append(operation_id)


class _SharedQueue:
    """In-memory shared Operations store with the additive type-scoped read (Q1)."""

    def __init__(self, ops):
        self._ops = ops

    def get_queued_operations(self, types=None):
        queued = [o for o in self._ops if o.status == OperationPhase.QUEUED]
        if types is None:
            return queued
        return [o for o in queued if o.metadata.get("operation_type") in types]


class _FakeRegistry:
    def list_all(self):
        return []


class _FakePool:
    def __init__(self):
        self.assigned = []
        self.registry = _FakeRegistry()

    def try_assign(self, operation_id):
        self.assigned.append(operation_id)
        return type("W", (), {"worker_id": "w"})()

    def release_worker(self, *args):
        pass


class _FakeOperationService:
    def __init__(self):
        self.failed = []
        self.started = []

    def fail(self, operation_id, error):
        self.failed.append(operation_id)

    def start(self, operation_id):
        self.started.append(operation_id)


class _InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)

    def shutdown(self, wait=False):
        pass


def _op(operation_id, operation_type):
    return OperationRecord(
        operation_id=operation_id,
        status=OperationPhase.QUEUED,
        batch_type=operation_type,
        metadata={"operation_type": operation_type, "request": {"value": "x"}},
    )


def _run_zap(queue):
    registry = ZapOperationRegistry()
    registry.register(
        ZapOperation(
            operation_type=ZapOperationType.API_SCAN,
            execution_strategy=ExecutionStrategy.SEQUENTIAL,
            request_model=_Req,
            handler=_RecordingHandler(),
        )
    )
    pool = _FakePool()
    ops = _FakeOperationService()
    dispatcher = OwaspZapDispatcher(
        operation_dao=queue,
        operation_service=ops,
        pool_manager=pool,
        registry=registry,
        queue_poll_interval_seconds=1.0,
        heartbeat_sweep_interval_seconds=1.0,
        heartbeat_timeout_seconds=1.0,
        orchestration_executor=_InlineExecutor(),
    )
    dispatcher._dispatch_queued_operations()
    return set(pool.assigned), set(ops.failed)


def _run_performance(queue):
    """Run one Performance dispatch pass. Lands with Component 5 (ADR-0010 §4.12).

    Expected interface (contract-first): a dispatcher scoped to the Performance
    operation types that assigns Performance operations via a pool and fails
    none belonging to another engine. Until it exists this import fails, so the
    surrounding test xfails.
    """
    from app.services.performance.dispatcher import (  # noqa: PLC0415 - Component 5
        PerformanceDispatcher,
    )

    pool = _FakePool()
    ops = _FakeOperationService()
    dispatcher = PerformanceDispatcher(
        operation_dao=queue,
        operation_service=ops,
        pool_manager=pool,
        supported_operation_types=frozenset({_PERF_TYPE}),
        queue_poll_interval_seconds=1.0,
        heartbeat_sweep_interval_seconds=1.0,
        heartbeat_timeout_seconds=1.0,
    )
    dispatcher.dispatch_pending()
    return set(pool.assigned), set(ops.failed)


class SharedQueueCoexistenceTests(unittest.TestCase):
    def _assert_coexistence(self, outcomes, supported):
        """Engine-neutral contract over {engine: (assigned, failed)}."""
        all_ids = set().union(*supported.values())
        already_assigned = set()
        for engine, (assigned, failed) in outcomes.items():
            own = supported[engine]
            foreign = all_ids - own
            self.assertEqual(assigned, own, f"{engine}: must assign exactly its supported ops (INV12)")
            self.assertEqual(failed & foreign, set(), f"{engine}: must not fail a foreign op")
            self.assertEqual(already_assigned & assigned, set(), f"{engine}: no op dispatched twice")
            already_assigned |= assigned
        self.assertEqual(already_assigned, all_ids, "every op assigned exactly once; none skipped")

    def test_two_dispatchers_coexist_over_shared_queue(self):
        ops = [
            _op("zap-A", _ZAP_TYPE),
            _op("zap-B", _ZAP_TYPE),
            _op("perf-A", _PERF_TYPE),
            _op("perf-B", _PERF_TYPE),
        ]
        queue = _SharedQueue(ops)
        engine_before = {o.operation_id: o.metadata["operation_type"] for o in ops}

        outcomes = {
            "zap": _run_zap(queue),
            "performance": _run_performance(queue),
        }
        supported = {
            "zap": {"zap-A", "zap-B"},
            "performance": {"perf-A", "perf-B"},
        }
        self._assert_coexistence(outcomes, supported)

        # INV13: an operation's engine identity is immutable across dispatch.
        engine_after = {o.operation_id: o.metadata["operation_type"] for o in ops}
        self.assertEqual(engine_after, engine_before)


if __name__ == "__main__":
    unittest.main()
