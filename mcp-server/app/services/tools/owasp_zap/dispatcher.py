"""
ZAP queue dispatcher.

Two independent background loops, both started/stopped together:

1. **Queue loop** — polls the Operations table for ``QUEUED`` rows (oldest
   first), tries to assign each to an idle, Active worker via the Pool
   Manager, and — only on a successful assignment — hands it to
   :meth:`ZapApiScanService.run_assigned_scan`. An operation that can't be
   assigned this tick simply stays ``QUEUED`` and is retried next tick; there
   is no in-memory queue to lose on restart, because the row itself *is* the
   queue entry.

2. **Heartbeat sweep loop** — periodically asks the Worker Registry to mark
   any worker whose heartbeat has expired as Offline. If that worker was
   executing an operation, this loop marks that operation FAILED. There is no
   automatic retry — resubmitting is left to the user.

Both loops run on plain daemon threads (matching the rest of this codebase's
synchronous, thread-pool style — see ``ThreadPoolExecutor`` in
``api_scanner.py``) rather than asyncio tasks, so they work the same whether
the ASGI server uses one worker process or several.
"""

import threading
from typing import Optional

from app.core.mcp_logger import MCPLogger
from app.dao.base import BaseOperationDAO
from app.integrations.owasp_zap.pool import OwaspZapPoolManager
from app.schemas.tools.owasp_zap.common import OperationStatus
from app.services.tools.owasp_zap.api_scanner import ZapApiScanService


class OwaspZapDispatcher:
    """Background dispatcher tying the Operations queue to the Pool Manager."""

    def __init__(
        self,
        *,
        operation_dao: BaseOperationDAO,
        pool_manager: OwaspZapPoolManager,
        scan_service: ZapApiScanService,
        queue_poll_interval_seconds: float,
        heartbeat_sweep_interval_seconds: float,
        heartbeat_timeout_seconds: float,
    ) -> None:
        self._operation_dao = operation_dao
        self._pool_manager = pool_manager
        self._scan_service = scan_service
        self._queue_poll_interval = queue_poll_interval_seconds
        self._sweep_interval = heartbeat_sweep_interval_seconds
        self._heartbeat_timeout = heartbeat_timeout_seconds

        self._logger = MCPLogger("OwaspZapDispatcher")
        self._stop_event = threading.Event()
        self._queue_thread: Optional[threading.Thread] = None
        self._sweep_thread: Optional[threading.Thread] = None

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start both background loops. Idempotent — a second call is a no-op."""
        if self._queue_thread is not None:
            return

        self._stop_event.clear()
        self._queue_thread = threading.Thread(
            target=self._run_queue_loop, name="zap-queue-dispatcher", daemon=True
        )
        self._sweep_thread = threading.Thread(
            target=self._run_sweep_loop, name="zap-heartbeat-sweeper", daemon=True
        )
        self._queue_thread.start()
        self._sweep_thread.start()
        self._logger.info(
            "Dispatcher started (queue_poll=%ss, heartbeat_sweep=%ss, heartbeat_timeout=%ss)",
            self._queue_poll_interval,
            self._sweep_interval,
            self._heartbeat_timeout,
        )

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Signal both loops to stop and wait (briefly) for them to exit."""
        self._stop_event.set()
        for thread in (self._queue_thread, self._sweep_thread):
            if thread is not None:
                thread.join(timeout=timeout_seconds)
        self._queue_thread = None
        self._sweep_thread = None
        self._logger.info("Dispatcher stopped")

    # ── Queue loop ───────────────────────────────────────────────────────

    def _run_queue_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._dispatch_queued_operations()
            except Exception as exc:  # pylint: disable=broad-except
                # A polling-loop failure must never kill the loop itself.
                self._logger.error("Queue dispatch tick failed: %s", exc)
            self._stop_event.wait(self._queue_poll_interval)

    def _dispatch_queued_operations(self) -> None:
        queued = self._operation_dao.get_queued_operations()
        if not queued:
            return

        for operation in queued:
            worker = self._pool_manager.try_assign(operation.operation_id)
            if worker is None:
                # No idle Active worker right now — stays QUEUED, retried next tick.
                continue

            try:
                request = ZapApiScanService.request_from_metadata(operation.metadata)
            except Exception as exc:  # pylint: disable=broad-except
                # Malformed/legacy metadata can never be resumed — fail loudly
                # rather than silently holding a worker slot forever.
                self._logger.error(
                    "Operation '%s' has unusable metadata, marking FAILED: %s",
                    operation.operation_id,
                    exc,
                )
                self._pool_manager.release_worker(worker.worker_id, operation.operation_id)
                self._operation_dao.update_operation_status(
                    operation_id=operation.operation_id,
                    status=OperationStatus.FAILED,
                    error=f"Could not reconstruct scan request from metadata: {exc}",
                )
                continue

            self._scan_service.run_assigned_scan(operation.operation_id, request, worker)

    # ── Heartbeat sweep loop ─────────────────────────────────────────────

    def _run_sweep_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._sweep_expired_workers()
            except Exception as exc:  # pylint: disable=broad-except
                self._logger.error("Heartbeat sweep tick failed: %s", exc)
            self._stop_event.wait(self._sweep_interval)

    def _sweep_expired_workers(self) -> None:
        orphaned = self._pool_manager.registry.sweep_expired(self._heartbeat_timeout)
        for worker_id, operation_id in orphaned:
            self._logger.warning(
                "Worker '%s' went Offline while executing '%s' — marking FAILED (no auto-retry)",
                worker_id,
                operation_id,
            )
            self._operation_dao.update_operation_status(
                operation_id=operation_id,
                status=OperationStatus.FAILED,
                error=(
                    f"Worker '{worker_id}' stopped sending heartbeats and was marked Offline "
                    "while this operation was running. Resubmit if you want to retry."
                ),
            )
