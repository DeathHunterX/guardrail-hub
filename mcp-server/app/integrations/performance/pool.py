"""Performance Pool Manager — turn a scheduler choice into an assignment.

Ties the registry (who exists / busy-idle) to the scheduler (who's next) for the
dispatcher: try to assign one operation to a fit worker, release when done,
relay a cancel intent. Thinner than the ZAP pool manager — the pull model means
there is **no client to hand back**; the worker pulls its own work. The pool's
job ends at ``registry.assign`` (the scheduler-ends-at-assignment invariant);
execution happens later, on the worker.
"""

from __future__ import annotations

from typing import Optional

from app.core.mcp_logger import MCPLogger
from app.integrations.performance.registry import PerformanceWorkerRegistry
from app.integrations.performance.scheduler import WorkerScheduler
from app.schemas.performance.worker import PerformanceWorkerInfo


class PerformancePoolManager:
    """Coordinates worker selection + assignment for the dispatcher."""

    def __init__(self, registry: PerformanceWorkerRegistry, scheduler: WorkerScheduler) -> None:
        self._registry = registry
        self._scheduler = scheduler
        self._logger = MCPLogger("PerformancePoolManager")

    def try_assign(self, operation_id: str) -> Optional[PerformanceWorkerInfo]:
        """Assign *operation_id* to one fit worker, or return None if none is.

        Returns the assigned worker (op_id bound) or None — in which case the
        operation stays QUEUED and the dispatcher retries next tick. This method
        does not execute anything; it ends at assignment.
        """
        candidate = self._scheduler.select(self._registry.list_all())
        if candidate is None:
            return None
        self._registry.assign(candidate.worker_id, operation_id)
        self._logger.info("Assigned operation '%s' -> worker '%s'", operation_id, candidate.worker_id)
        return self._registry.get(candidate.worker_id)

    def release_worker(self, worker_id: str, operation_id: str) -> None:
        self._registry.release(worker_id, operation_id)

    def request_cancel(self, worker_id: str, operation_id: str) -> bool:
        return self._registry.request_cancel(worker_id, operation_id)
