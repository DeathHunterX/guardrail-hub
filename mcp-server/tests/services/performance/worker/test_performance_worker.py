"""Unit tests for the PerformanceWorker loop pieces (ADR-0010 §4.2/§4.3)."""

import base64
import unittest
from datetime import datetime, timezone
from threading import Event

from app.schemas.performance.worker import (
    PerformanceAssignmentResponse,
    PerformanceWorkerHeartbeatResponse,
    PerformanceWorkerLifecycleState,
    PerformanceWorkerRegisterResponse,
)
from app.services.performance.worker import PerformanceWorker


class _FakeServer:
    def __init__(self, *, heartbeat=None, assignment=None):
        self.registered = None
        self.heartbeats = []
        self.pulls = []
        self._heartbeat = heartbeat
        self._assignment = assignment

    def register(self, request):
        self.registered = request
        return PerformanceWorkerRegisterResponse(
            worker_id=request.worker_id,
            state=PerformanceWorkerLifecycleState.ACTIVE,
            registered_at=datetime.now(timezone.utc),
        )

    def heartbeat(self, request):
        self.heartbeats.append(request)
        return self._heartbeat

    def pull(self, request):
        self.pulls.append(request)
        return self._assignment


class _FakeRuntime:
    def __init__(self):
        self.calls = []

    def execute(self, operation_id, plan, *, timeout_seconds=None, cancel=None):
        self.calls.append((operation_id, plan, timeout_seconds, cancel))


def _hb(*, assignment=None, cancel_requested=False):
    return PerformanceWorkerHeartbeatResponse(
        worker_id="w",
        state=PerformanceWorkerLifecycleState.ACTIVE,
        last_heartbeat=datetime.now(timezone.utc),
        assignment=assignment,
        cancel_requested=cancel_requested,
    )


def _worker(server, runtime):
    return PerformanceWorker(
        server=server, runtime=runtime, worker_id="w", hostname="w", version="1.0"
    )


class WorkerStepTests(unittest.TestCase):
    def test_register_sends_identity(self):
        server = _FakeServer()
        _worker(server, _FakeRuntime()).register()
        self.assertEqual(server.registered.worker_id, "w")
        self.assertEqual(server.registered.version, "1.0")

    def test_heartbeat_relays_cancel_to_current_job(self):
        server = _FakeServer(heartbeat=_hb(cancel_requested=True))
        worker = _worker(server, _FakeRuntime())
        cancel = Event()
        worker._current_cancel = cancel  # simulate an in-flight job
        worker.heartbeat_once()
        self.assertTrue(cancel.is_set())

    def test_heartbeat_cancel_with_no_job_is_safe(self):
        server = _FakeServer(heartbeat=_hb(cancel_requested=True))
        worker = _worker(server, _FakeRuntime())
        worker.heartbeat_once()  # no current job — must not raise

    def test_execute_assignment_pulls_and_drives_runtime(self):
        assignment = PerformanceAssignmentResponse(
            operation_id="op-1",
            plan_b64=base64.b64encode(b"<plan/>").decode("ascii"),
            timeout_seconds=30.0,
        )
        server = _FakeServer(assignment=assignment)
        runtime = _FakeRuntime()
        cancel = Event()
        _worker(server, runtime).execute_assignment("op-1", cancel)

        self.assertEqual(server.pulls[0].operation_id, "op-1")
        op, plan, timeout, passed_cancel = runtime.calls[0]
        self.assertEqual((op, plan, timeout), ("op-1", b"<plan/>", 30.0))
        self.assertIs(passed_cancel, cancel)


if __name__ == "__main__":
    unittest.main()
