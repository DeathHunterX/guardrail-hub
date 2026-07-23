"""PerformanceDispatcher — orchestrate assignment over the shared queue.

The server-side dispatcher for the pull model (ADR-0010 §4.4, §4.12). Its entire
job is: ``Queue → Scheduler → Registry → Assignment``. It assigns queued
Performance operations to fit workers and stops — the worker later pulls and
executes. It therefore:

- polls **only its supported operation types** (the scoped queue read, INV12) —
  it never sees, and so never fails, another engine's operations;
- selects a healthy, compatible worker **through the scheduler** (via the pool
  manager) and assigns the operation;
- transitions the operation ``QUEUED → RUNNING`` at assignment so it leaves the
  queue and is not dispatched twice; the worker pulls it on its next heartbeat;
- fails an operation orphaned by a worker that stopped heart-beating (the sweep),
  with no automatic retry.

It is **engine-neutral**: a future engine's dispatcher is this same class with a
different ``supported_operation_types`` set. It imports no engine implementation,
no ``PerformanceRuntime``, and no ``subprocess`` — the scheduler ends at
assignment; the worker begins at execution. An operation's engine identity is
never changed here (INV13).
"""

from __future__ import annotations

import threading
from typing import Collection, Optional

from app.core.mcp_logger import MCPLogger
from app.dao.base import BaseOperationDAO
from app.integrations.performance.pool import PerformancePoolManager
from app.services.operations.operation_service import OperationService


class PerformanceDispatcher:
    """Assigns queued Performance operations to workers; never executes them."""

    def __init__(
        self,
        *,
        operation_dao: BaseOperationDAO,
        operation_service: OperationService,
        pool_manager: PerformancePoolManager,
        supported_operation_types: Collection[str],
        queue_poll_interval_seconds: float,
        heartbeat_sweep_interval_seconds: float,
        heartbeat_timeout_seconds: float,
    ) -> None:
        self._operation_dao = operation_dao
        self._operation_service = operation_service
        self._pool_manager = pool_manager
        self._supported_operation_types = frozenset(supported_operation_types)
        self._queue_poll_interval = queue_poll_interval_seconds
        self._sweep_interval = heartbeat_sweep_interval_seconds
        self._heartbeat_timeout = heartbeat_timeout_seconds

        self._logger = MCPLogger("PerformanceDispatcher")
        self._stop_event = threading.Event()
        self._queue_thread: Optional[threading.Thread] = None
        self._sweep_thread: Optional[threading.Thread] = None

    # ── One deterministic pass (also the unit-test surface) ──────────────

    def dispatch_pending(self) -> None:
        """Assign every currently-queued supported operation that a worker can take.

        Polls the shared queue **scoped to this dispatcher's supported types**
        (INV12), then for each operation asks the pool for a fit worker. On
        assignment the operation is transitioned to RUNNING so it leaves the
        queue; if no worker is free it stays QUEUED and is retried next tick. This
        method assigns only — it never executes an operation.
        """
        for operation in self._operation_dao.get_queued_operations(
            types=self._supported_operation_types
        ):
            worker = self._pool_manager.try_assign(operation.operation_id)
            if worker is None:
                continue  # no fit worker right now — stays QUEUED, retried next tick
            # QUEUED → RUNNING: the operation is committed to a worker, which will
            # pull and execute it. The dispatcher's responsibility ends here.
            self._operation_service.start(operation.operation_id)

    def sweep_expired_workers(self) -> None:
        """Fail operations orphaned by workers that stopped heart-beating."""
        for worker_id, operation_id in self._pool_manager.sweep_expired(self._heartbeat_timeout):
            self._logger.warning(
                "Worker '%s' went Offline while holding '%s' — marking FAILED (no auto-retry).",
                worker_id,
                operation_id,
            )
            self._operation_service.fail(
                operation_id,
                f"Worker '{worker_id}' stopped sending heartbeats while this operation "
                "was assigned. Resubmit if you want to retry.",
            )

    # ── Background lifecycle (mirrors the ZAP dispatcher) ────────────────

    def start(self) -> None:
        """Start the queue and sweep loops. Idempotent."""
        if self._queue_thread is not None:
            return
        self._stop_event.clear()
        self._queue_thread = threading.Thread(
            target=self._run_loop,
            args=(self.dispatch_pending, self._queue_poll_interval),
            name="perf-queue-dispatcher",
            daemon=True,
        )
        self._sweep_thread = threading.Thread(
            target=self._run_loop,
            args=(self.sweep_expired_workers, self._sweep_interval),
            name="perf-heartbeat-sweeper",
            daemon=True,
        )
        self._queue_thread.start()
        self._sweep_thread.start()
        self._logger.info(
            "PerformanceDispatcher started (queue_poll=%ss, heartbeat_sweep=%ss, timeout=%ss, types=%s)",
            self._queue_poll_interval,
            self._sweep_interval,
            self._heartbeat_timeout,
            sorted(self._supported_operation_types),
        )

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Signal both loops to stop and wait briefly for them to exit."""
        self._stop_event.set()
        for thread in (self._queue_thread, self._sweep_thread):
            if thread is not None:
                thread.join(timeout=timeout_seconds)
        self._queue_thread = None
        self._sweep_thread = None
        self._logger.info("PerformanceDispatcher stopped")

    def _run_loop(self, tick, interval_seconds: float) -> None:
        while not self._stop_event.is_set():
            try:
                tick()
            except Exception as exc:  # pylint: disable=broad-except
                # A loop failure must never kill the loop (mirrors the ZAP dispatcher).
                self._logger.error("Dispatcher tick failed: %s", exc)
            self._stop_event.wait(interval_seconds)
