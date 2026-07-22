"""Engine-neutral performance schemas (worker protocol, health, report, …)."""

from app.schemas.performance.report import ArtifactPayload, OperationReport
from app.schemas.performance.worker import (
    PerformanceWorkerHeartbeatRequest,
    PerformanceWorkerHeartbeatResponse,
    PerformanceWorkerInfo,
    PerformanceWorkerLifecycleState,
    PerformanceWorkerRegisterRequest,
    PerformanceWorkerRegisterResponse,
    WorkerHealth,
    generate_worker_id,
)

__all__ = [
    "ArtifactPayload",
    "OperationReport",
    "PerformanceWorkerHeartbeatRequest",
    "PerformanceWorkerHeartbeatResponse",
    "PerformanceWorkerInfo",
    "PerformanceWorkerLifecycleState",
    "PerformanceWorkerRegisterRequest",
    "PerformanceWorkerRegisterResponse",
    "WorkerHealth",
    "generate_worker_id",
]
