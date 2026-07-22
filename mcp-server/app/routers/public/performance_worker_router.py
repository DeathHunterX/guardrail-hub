"""Performance worker endpoints — Register, Heartbeat, Pull Assignment, Report.

Called by performance worker processes themselves (not LLM clients), so mounted
directly like ``zap_worker_router``. A thin HTTP adapter: it maps requests to
:class:`WorkerCoordinator` and domain errors to status codes, and touches no
registry/store directly.

Built via a factory (not a module singleton) because the coordinator depends on
stores wired at startup; the composition root constructs the coordinator and
mounts the returned router. Namespace is ``/performance/…`` — distinct from
ZAP's ``/workers`` (§4.9).
"""

from fastapi import APIRouter, HTTPException

from app.integrations.performance.registry import WorkerNotRegisteredError
from app.schemas.performance.report import OperationReport
from app.schemas.performance.worker import (
    PerformanceAssignmentResponse,
    PerformanceWorkerHeartbeatRequest,
    PerformanceWorkerHeartbeatResponse,
    PerformanceWorkerRegisterRequest,
    PerformanceWorkerRegisterResponse,
    PullAssignmentRequest,
)
from app.services.performance.worker_api import (
    AssignmentMismatchError,
    PlanNotFoundError,
    WorkerCoordinator,
)


def build_performance_worker_router(coordinator: WorkerCoordinator) -> APIRouter:
    """Return a router bound to *coordinator* (mounted by the composition root)."""
    router = APIRouter(prefix="/performance", tags=["Performance Workers"])

    @router.post("/workers/register", response_model=PerformanceWorkerRegisterResponse)
    def register(request: PerformanceWorkerRegisterRequest) -> PerformanceWorkerRegisterResponse:
        return coordinator.register(request)

    @router.post("/workers/heartbeat", response_model=PerformanceWorkerHeartbeatResponse)
    def heartbeat(request: PerformanceWorkerHeartbeatRequest) -> PerformanceWorkerHeartbeatResponse:
        try:
            return coordinator.heartbeat(request)
        except WorkerNotRegisteredError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"Worker '{request.worker_id}' is not registered — call register again.",
            ) from exc

    @router.post("/workers/pull", response_model=PerformanceAssignmentResponse)
    def pull_assignment(request: PullAssignmentRequest) -> PerformanceAssignmentResponse:
        try:
            return coordinator.pull_assignment(request.worker_id, request.operation_id)
        except WorkerNotRegisteredError as exc:
            raise HTTPException(status_code=404, detail=f"Worker '{request.worker_id}' not registered.") from exc
        except AssignmentMismatchError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PlanNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"No plan for operation '{request.operation_id}'.") from exc

    @router.post("/operations/report")
    def report(report: OperationReport) -> dict:
        coordinator.report(report)
        return {"operation_id": report.operation_id, "accepted": True}

    return router
