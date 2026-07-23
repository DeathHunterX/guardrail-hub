"""WorkerCoordinator — the server side of the worker-facing API (ADR-0010 §4.2).

The four worker-initiated calls, all handled here:

- **Register** / **Heartbeat** — delegate to the registry; the heartbeat response
  is the worker's only inbound channel, carrying its assignment and cancel flag
  (§4.2/§4.3).
- **Pull Assignment** — return the validated plan + policy for the operation the
  worker was assigned. Least-privilege (§4.9): a worker may only pull the
  operation it currently holds.
- **Report** — persist the redacted result durably, transition the operation, and
  release the worker.

The coordinator depends only on ports (a registry, a plan store, a report store,
an operation-status sink), so it is testable in isolation and coupled to no
concrete store or engine. Concrete stores are wired in the composition root.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Optional, Protocol

from app.integrations.performance.registry import (
    PerformanceWorkerRegistry,
    WorkerNotRegisteredError,
)
from app.schemas.performance.report import OperationReport
from app.schemas.performance.worker import (
    PerformanceAssignmentResponse,
    PerformanceWorkerHeartbeatRequest,
    PerformanceWorkerHeartbeatResponse,
    PerformanceWorkerRegisterRequest,
    PerformanceWorkerRegisterResponse,
)


class PlanNotFoundError(KeyError):
    """No stored plan for an operation_id."""


class AssignmentMismatchError(PermissionError):
    """A worker tried to pull an operation it does not currently hold."""


@dataclass(frozen=True)
class StoredPlan:
    """A validated plan plus its resolved execution bound, server-owned (§4.5)."""

    plan: bytes
    timeout_seconds: Optional[float] = None


class PlanStore(Protocol):
    """Server-owned store of validated plans, keyed by operation_id."""

    def get(self, operation_id: str) -> StoredPlan:
        """Return the stored plan, or raise :class:`PlanNotFoundError`."""
        ...


class ReportStore(Protocol):
    """Durable sink for a finished operation's redacted report (§4.6)."""

    def save(self, report: OperationReport) -> None:
        ...


class OperationStatusSink(Protocol):
    """Transitions an operation's lifecycle on a terminal report."""

    def complete(self, operation_id: str) -> None: ...
    def fail(self, operation_id: str, error: str) -> None: ...
    def cancel(self, operation_id: str) -> None: ...


class WorkerCoordinator:
    """Handles the four worker-facing calls over injected ports."""

    def __init__(
        self,
        *,
        registry: PerformanceWorkerRegistry,
        plans: PlanStore,
        reports: ReportStore,
        operations: OperationStatusSink,
        min_compatible_version: Optional[str] = None,
    ) -> None:
        self._registry = registry
        self._plans = plans
        self._reports = reports
        self._operations = operations
        self._min_compatible_version = min_compatible_version

    def register(
        self, request: PerformanceWorkerRegisterRequest
    ) -> PerformanceWorkerRegisterResponse:
        info = self._registry.register(
            worker_id=request.worker_id,
            hostname=request.hostname,
            version=request.version,
        )
        return PerformanceWorkerRegisterResponse(
            worker_id=info.worker_id,
            state=info.state,
            registered_at=info.registered_at,
            min_compatible_version=self._min_compatible_version,
        )

    def heartbeat(
        self, request: PerformanceWorkerHeartbeatRequest
    ) -> PerformanceWorkerHeartbeatResponse:
        info = self._registry.heartbeat(request.worker_id, request.health)
        return PerformanceWorkerHeartbeatResponse(
            worker_id=info.worker_id,
            state=info.state,
            last_heartbeat=info.last_heartbeat,
            assignment=info.op_id,          # what to pull (if anything)
            cancel_requested=info.cancel_requested,  # whether to cancel it (§4.3)
        )

    def pull_assignment(self, worker_id: str, operation_id: str) -> PerformanceAssignmentResponse:
        info = self._registry.get(worker_id)
        if info is None:
            raise WorkerNotRegisteredError(worker_id)
        if info.op_id != operation_id:
            # Least-privilege: only the operation this worker currently holds.
            raise AssignmentMismatchError(
                f"worker '{worker_id}' does not hold operation '{operation_id}'"
            )
        stored = self._plans.get(operation_id)
        return PerformanceAssignmentResponse(
            operation_id=operation_id,
            plan_b64=base64.b64encode(stored.plan).decode("ascii"),
            timeout_seconds=stored.timeout_seconds,
        )

    def report(self, report: OperationReport) -> None:
        # Persist durably first, then transition the operation, then release the
        # worker — the terminal step of the pull lifecycle.
        self._reports.save(report)
        if report.status == "completed":
            self._operations.complete(report.operation_id)
        elif report.status == "cancelled":
            self._operations.cancel(report.operation_id)
        else:  # failed / timed_out
            self._operations.fail(report.operation_id, report.error or f"operation {report.status}")
        self._release_worker_holding(report.operation_id)

    def _release_worker_holding(self, operation_id: str) -> None:
        for worker in self._registry.list_all():
            if worker.op_id == operation_id:
                self._registry.release(worker.worker_id, operation_id)
                return
