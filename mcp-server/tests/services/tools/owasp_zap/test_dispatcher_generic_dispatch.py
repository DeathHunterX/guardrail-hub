"""Regression tests for the Dispatcher's generic, tool-agnostic routing.

Prove three properties of the refactored dispatcher:

1. Worker-bound operations are assigned a worker and executed on it.
2. Orchestration operations (fan-out/fan-in) are executed WITHOUT ever claiming
   a worker (the property the api_suite orchestrator relies on).
3. An unresolvable operation type is failed loudly and never strands a worker.

The dispatcher module imports the Pool Manager, which pulls the ZAP client (the
``zapv2`` module from the ``zaproxy`` distribution); skip cleanly where that
dependency is absent from the sandbox.
"""

import unittest

import pytest

pytest.importorskip("zapv2")

from pydantic import BaseModel  # noqa: E402

from app.schemas.internal.operation import OperationRecord  # noqa: E402
from app.schemas.tools.owasp_zap.common import OperationStatus  # noqa: E402
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
from app.services.tools.owasp_zap.worker.dispatcher import (  # noqa: E402
    OwaspZapDispatcher,
)


class _Req(BaseModel):
    value: str = "x"


class _RecordingHandler:
    def __init__(self):
        self.calls = []

    def execute(self, operation_id, request, worker):
        self.calls.append((operation_id, request, worker))


class _FakeWorker:
    worker_id = "worker-1"


class _FakePoolManager:
    def __init__(self, worker=None):
        self._worker = worker
        self.assign_calls = []
        self.release_calls = []

    def try_assign(self, operation_id):
        self.assign_calls.append(operation_id)
        return self._worker

    def release_worker(self, worker_id, operation_id):
        self.release_calls.append((worker_id, operation_id))


class _FakeOperationService:
    def __init__(self):
        self.failed = []
        self.started = []

    def fail(self, operation_id, error):
        self.failed.append((operation_id, error))

    def start(self, operation_id):
        self.started.append(operation_id)


class _InlineExecutor:
    """Runs submitted work synchronously so assertions are deterministic."""

    def __init__(self):
        self.submitted = 0

    def submit(self, fn, *args, **kwargs):
        self.submitted += 1
        fn(*args, **kwargs)

    def shutdown(self, wait=False):  # pragma: no cover - lifecycle only
        pass


def _record(op_type, metadata):
    return OperationRecord(
        operation_id="op-1",
        status=OperationStatus.QUEUED,
        batch_type="api_scan",
        metadata=metadata,
    )


def _dispatcher(registry, pool, op_service, executor):
    return OwaspZapDispatcher(
        operation_dao=object(),
        operation_service=op_service,
        pool_manager=pool,
        registry=registry,
        queue_poll_interval_seconds=1.0,
        heartbeat_sweep_interval_seconds=1.0,
        heartbeat_timeout_seconds=1.0,
        orchestration_executor=executor,
    )


def _operation(op_type, strategy, handler):
    return ZapOperation(
        operation_type=op_type,
        execution_strategy=strategy,
        request_model=_Req,
        handler=handler,
    )


class DispatcherGenericRoutingTests(unittest.TestCase):
    def test_worker_bound_operation_is_assigned_and_executed(self):
        handler = _RecordingHandler()
        registry = ZapOperationRegistry()
        registry.register(
            _operation(
                ZapOperationType.API_SCAN, ExecutionStrategy.SEQUENTIAL, handler
            )
        )
        worker = _FakeWorker()
        pool = _FakePoolManager(worker=worker)
        executor = _InlineExecutor()

        dispatcher = _dispatcher(registry, pool, _FakeOperationService(), executor)
        dispatcher._dispatch_one(
            _record(
                ZapOperationType.API_SCAN,
                {"operation_type": "api_scan", "request": {"value": "y"}},
            )
        )

        self.assertEqual(pool.assign_calls, ["op-1"])
        self.assertEqual(len(handler.calls), 1)
        _, request, passed_worker = handler.calls[0]
        self.assertIs(passed_worker, worker)
        self.assertEqual(request.value, "y")

    def test_orchestration_operation_runs_without_claiming_a_worker(self):
        handler = _RecordingHandler()
        registry = ZapOperationRegistry()
        registry.register(
            _operation(
                ZapOperationType.API_SUITE, ExecutionStrategy.FAN_OUT, handler
            )
        )
        pool = _FakePoolManager(worker=_FakeWorker())
        op_service = _FakeOperationService()
        executor = _InlineExecutor()

        dispatcher = _dispatcher(registry, pool, op_service, executor)
        dispatcher._dispatch_one(
            _record(
                ZapOperationType.API_SUITE,
                {"operation_type": "api_suite", "request": {"value": "z"}},
            )
        )

        # The worker pool was never consulted for an orchestration operation.
        self.assertEqual(pool.assign_calls, [])
        # It ran on the orchestration executor, with worker=None, marked RUNNING.
        self.assertEqual(executor.submitted, 1)
        self.assertEqual(op_service.started, ["op-1"])
        self.assertEqual(len(handler.calls), 1)
        self.assertIsNone(handler.calls[0][2])

    def test_unresolvable_type_fails_without_claiming_a_worker(self):
        registry = ZapOperationRegistry()  # nothing registered
        pool = _FakePoolManager(worker=_FakeWorker())
        op_service = _FakeOperationService()

        dispatcher = _dispatcher(registry, pool, op_service, _InlineExecutor())
        dispatcher._dispatch_one(
            _record(
                ZapOperationType.API_SUITE,
                {"operation_type": "api_suite", "request": {"value": "z"}},
            )
        )

        self.assertEqual(pool.assign_calls, [])
        self.assertEqual(len(op_service.failed), 1)


if __name__ == "__main__":
    unittest.main()
