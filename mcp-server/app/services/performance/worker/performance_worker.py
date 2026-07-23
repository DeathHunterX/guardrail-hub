"""PerformanceWorker — the long-lived warm worker loop (ADR-0010 §4.2).

The worker is alive; the engine is not. This loop registers once, then heartbeats
forever. The heartbeat *response* is its only inbound channel:

- an ``assignment`` starts exactly one job (INV1) — pulled and run locally through
  the :class:`PerformanceRuntime` (which validates, executes, redacts, and reports
  via its persistence port);
- ``cancel_requested`` sets the in-flight job's cancel event, so the runner kills
  the engine's process group.

The job runs on a background thread so the heartbeat loop keeps ticking (and can
observe a cancel) while the engine runs. The worker holds no business state
between jobs (INV6): its only state is "am I currently running one".
"""

from __future__ import annotations

import base64
from threading import Event, Lock, Thread
from typing import Callable, Optional

from app.core.mcp_logger import MCPLogger
from app.integrations.performance.server_client import ServerClient
from app.schemas.performance.worker import (
    PerformanceWorkerHeartbeatRequest,
    PerformanceWorkerHeartbeatResponse,
    PerformanceWorkerRegisterRequest,
    PullAssignmentRequest,
    WorkerHealth,
)
from app.services.performance.runtime import PerformanceRuntime

HealthProvider = Callable[[], WorkerHealth]


class PerformanceWorker:
    """One warm worker: register, heartbeat, run one job at a time, report."""

    def __init__(
        self,
        *,
        server: ServerClient,
        runtime: PerformanceRuntime,
        worker_id: str,
        hostname: str,
        version: Optional[str] = None,
        health_provider: HealthProvider = WorkerHealth,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        self._server = server
        self._runtime = runtime
        self._worker_id = worker_id
        self._hostname = hostname
        self._version = version
        self._health = health_provider
        self._interval = heartbeat_interval_seconds

        self._logger = MCPLogger("PerformanceWorker")
        self._lock = Lock()
        self._current_op: Optional[str] = None
        self._current_cancel: Optional[Event] = None

    # ── Discrete steps (independently testable) ──────────────────────────

    def register(self) -> None:
        self._server.register(
            PerformanceWorkerRegisterRequest(
                worker_id=self._worker_id, hostname=self._hostname, version=self._version
            )
        )

    def heartbeat_once(self) -> PerformanceWorkerHeartbeatResponse:
        """Send one heartbeat; relay a cancel to the in-flight job if requested."""
        response = self._server.heartbeat(
            PerformanceWorkerHeartbeatRequest(worker_id=self._worker_id, health=self._health())
        )
        if response.cancel_requested:
            with self._lock:
                if self._current_cancel is not None:
                    self._current_cancel.set()
        return response

    def execute_assignment(self, operation_id: str, cancel: Event) -> None:
        """Pull the plan for *operation_id* and run it through the Runtime.

        The Runtime validates, executes, redacts, and reports the result via its
        persistence port; this method only transports the plan in and drives it.
        """
        assignment = self._server.pull(
            PullAssignmentRequest(worker_id=self._worker_id, operation_id=operation_id)
        )
        plan = base64.b64decode(assignment.plan_b64)
        self._runtime.execute(
            operation_id,
            plan,
            timeout_seconds=assignment.timeout_seconds,
            cancel=cancel,
        )

    # ── Long-lived loop ──────────────────────────────────────────────────

    def run(self, stop: Event) -> None:
        """Register, then heartbeat until *stop*; start one job per assignment."""
        self.register()
        self._logger.info("Worker '%s' registered; entering heartbeat loop", self._worker_id)
        while not stop.is_set():
            try:
                response = self.heartbeat_once()
                if response.assignment:
                    self._maybe_start_job(response.assignment)
            except Exception as exc:  # pylint: disable=broad-except
                # A loop failure must never kill the loop (mirrors the ZAP dispatcher).
                self._logger.error("Heartbeat/dispatch tick failed: %s", exc)
            stop.wait(self._interval)

    def _maybe_start_job(self, operation_id: str) -> None:
        """Start *operation_id* on a background thread — at most one at a time (INV1)."""
        cancel = Event()
        with self._lock:
            if self._current_op is not None:
                return  # already busy — one active job
            self._current_op = operation_id
            self._current_cancel = cancel
        Thread(
            target=self._run_job, args=(operation_id, cancel), name=f"perf-job-{operation_id}", daemon=True
        ).start()

    def _run_job(self, operation_id: str, cancel: Event) -> None:
        try:
            self.execute_assignment(operation_id, cancel)
        except Exception as exc:  # pylint: disable=broad-except
            # The Runtime raised (rejected plan / persist failure): it already
            # cleaned the workspace; the server marks the op FAILED on report or
            # via the heartbeat-timeout sweep. Log and free the worker.
            self._logger.error("Operation '%s' failed in worker: %s", operation_id, exc)
        finally:
            with self._lock:
                self._current_op = None
                self._current_cancel = None
