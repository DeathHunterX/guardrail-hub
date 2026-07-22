"""Performance Worker Registry — the single source of truth for the pool.

Mirrors the ZAP worker registry's proven shape (self-registration + heartbeat,
busy/idle derived from ``op_id``, in-memory and rebuilt from workers' heartbeats
after a restart) but for the pull model (ADR-0010 §4.2):

- no endpoint is stored — the server never dials the worker;
- the heartbeat carries **health** (§2.3), retained for the scheduler;
- the server records a **cancel_requested** intent (§4.3) that the worker's next
  heartbeat response surfaces to it.

Thread-safe under a single lock (registration/heartbeat volume is low). Engine
neutral — nothing here names JMeter.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.core.mcp_logger import MCPLogger
from app.schemas.performance.worker import (
    PerformanceWorkerInfo,
    PerformanceWorkerLifecycleState,
    WorkerHealth,
    generate_worker_id,
)


class WorkerNotRegisteredError(KeyError):
    """Raised when an operation targets a worker_id the registry doesn't know."""


class PerformanceWorkerRegistry:
    """In-memory registry of self-registered performance workers."""

    def __init__(self) -> None:
        self._workers: Dict[str, PerformanceWorkerInfo] = {}
        self._lock = threading.Lock()
        self._logger = MCPLogger("PerformanceWorkerRegistry")

    # ── Registration / heartbeat ─────────────────────────────────────────

    def register(
        self,
        *,
        worker_id: Optional[str],
        hostname: str,
        version: Optional[str] = None,
    ) -> PerformanceWorkerInfo:
        """Register a new worker, or re-register an existing one (upsert).

        Re-registration refreshes hostname/version, resets the heartbeat, and
        returns the worker to ACTIVE. Any ``op_id`` it held is left intact (the
        sweep or the worker's own report resolves a genuinely orphaned one) — a
        bare register must never silently erase in-flight bookkeeping.
        """
        resolved_id = worker_id or hostname or generate_worker_id()
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._workers.get(resolved_id)
            info = PerformanceWorkerInfo(
                worker_id=resolved_id,
                hostname=hostname,
                version=version,
                state=PerformanceWorkerLifecycleState.ACTIVE,
                op_id=existing.op_id if existing else None,
                cancel_requested=existing.cancel_requested if existing else False,
                health=existing.health if existing else WorkerHealth(),
                last_heartbeat=now,
                registered_at=existing.registered_at if existing else now,
            )
            self._workers[resolved_id] = info
        self._logger.info(
            "Worker '%s' registered (hostname=%s%s)",
            resolved_id,
            hostname,
            ", re-registration" if existing else "",
        )
        return info

    def heartbeat(self, worker_id: str, health: Optional[WorkerHealth] = None) -> PerformanceWorkerInfo:
        """Record a heartbeat (and latest health). Self-heals OFFLINE -> ACTIVE.

        Raises:
            WorkerNotRegisteredError: unknown worker — the router tells it to
                re-register.
        """
        with self._lock:
            info = self._workers.get(worker_id)
            if info is None:
                raise WorkerNotRegisteredError(worker_id)
            updated = info.model_copy(
                update={
                    "last_heartbeat": datetime.now(timezone.utc),
                    "health": health if health is not None else info.health,
                    "state": (
                        PerformanceWorkerLifecycleState.ACTIVE
                        if info.state == PerformanceWorkerLifecycleState.OFFLINE
                        else info.state
                    ),
                }
            )
            self._workers[worker_id] = updated
            return updated

    # ── Assignment / cancellation ────────────────────────────────────────

    def assign(self, worker_id: str, operation_id: str) -> None:
        """Bind *operation_id* to *worker_id* (the worker becomes Busy)."""
        with self._lock:
            info = self._workers.get(worker_id)
            if info is None:
                raise WorkerNotRegisteredError(worker_id)
            self._workers[worker_id] = info.model_copy(
                update={"op_id": operation_id, "cancel_requested": False}
            )

    def request_cancel(self, worker_id: str, operation_id: str) -> bool:
        """Record cancel intent for *operation_id* on *worker_id* (§4.3).

        Applied only if the worker still holds that exact operation, so a stale
        cancel cannot target a since-reassigned worker. Returns whether it was
        applied. Enactment is the worker's, on its next heartbeat.
        """
        with self._lock:
            info = self._workers.get(worker_id)
            if info is None or info.op_id != operation_id:
                return False
            self._workers[worker_id] = info.model_copy(update={"cancel_requested": True})
            return True

    def release(self, worker_id: str, operation_id: Optional[str] = None) -> None:
        """Release *worker_id* back to Idle (clears op + cancel intent).

        With *operation_id*, releases only if the worker still holds that exact
        operation. A worker released while DRAINING transitions to OFFLINE.
        """
        with self._lock:
            info = self._workers.get(worker_id)
            if info is None:
                return
            if operation_id is not None and info.op_id != operation_id:
                return
            next_state = (
                PerformanceWorkerLifecycleState.OFFLINE
                if info.state == PerformanceWorkerLifecycleState.DRAINING
                else info.state
            )
            self._workers[worker_id] = info.model_copy(
                update={"op_id": None, "cancel_requested": False, "state": next_state}
            )

    # ── Maintenance lifecycle ────────────────────────────────────────────

    def mark_draining(self, worker_id: str) -> PerformanceWorkerInfo:
        """ACTIVE -> DRAINING: stop new assignments, let the current op finish."""
        with self._lock:
            info = self._workers.get(worker_id)
            if info is None:
                raise WorkerNotRegisteredError(worker_id)
            updated = info.model_copy(update={"state": PerformanceWorkerLifecycleState.DRAINING})
            self._workers[worker_id] = updated
            return updated

    def remove(self, worker_id: str) -> Optional[str]:
        """Hard-remove a worker; return the ``op_id`` it held, if any."""
        with self._lock:
            info = self._workers.pop(worker_id, None)
            return info.op_id if info else None

    # ── Heartbeat-timeout sweep ──────────────────────────────────────────

    def sweep_expired(self, timeout_seconds: float) -> List[Tuple[str, str]]:
        """Mark workers OFFLINE whose heartbeat is older than *timeout_seconds*.

        Returns ``(worker_id, operation_id)`` pairs for workers that *just* went
        Offline while holding an operation — the dispatcher fails those. Already
        -Offline workers are not re-reported.
        """
        now = datetime.now(timezone.utc)
        orphaned: List[Tuple[str, str]] = []
        with self._lock:
            for worker_id, info in list(self._workers.items()):
                if info.state == PerformanceWorkerLifecycleState.OFFLINE:
                    continue
                if (now - info.last_heartbeat).total_seconds() <= timeout_seconds:
                    continue
                self._logger.warning(
                    "Worker '%s' heartbeat timeout — marking Offline", worker_id
                )
                had_op = info.op_id
                self._workers[worker_id] = info.model_copy(
                    update={
                        "state": PerformanceWorkerLifecycleState.OFFLINE,
                        "op_id": None,
                        "cancel_requested": False,
                    }
                )
                if had_op is not None:
                    orphaned.append((worker_id, had_op))
        return orphaned

    # ── Read access ──────────────────────────────────────────────────────

    def get(self, worker_id: str) -> Optional[PerformanceWorkerInfo]:
        with self._lock:
            return self._workers.get(worker_id)

    def list_all(self) -> List[PerformanceWorkerInfo]:
        """Snapshot of every worker, sorted by worker_id (stable scheduler order)."""
        with self._lock:
            return sorted(self._workers.values(), key=lambda w: w.worker_id)
