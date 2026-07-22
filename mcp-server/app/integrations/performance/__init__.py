"""Performance worker-pool infrastructure (engine-neutral).

Parallel to ``app/integrations/owasp_zap`` but for the pull-model warm worker:
the registry today; pool manager, scheduler, and dispatcher as Phase 2 lands.
Kept separate from ZAP per ADR-0010 D4 (parallel infra, not a premature shared
extraction; consolidation trigger recorded in §8).
"""

from app.integrations.performance.fitness import (
    WorkerFitness,
    build_fitness,
    health_ok,
    version_compatible,
)
from app.integrations.performance.pool import PerformancePoolManager
from app.integrations.performance.registry import (
    PerformanceWorkerRegistry,
    WorkerNotRegisteredError,
)
from app.integrations.performance.report_sender import (
    HttpReportSender,
    ReportSender,
    ReportSendError,
)
from app.integrations.performance.scheduler import RoundRobinScheduler, WorkerScheduler

__all__ = [
    "HttpReportSender",
    "PerformancePoolManager",
    "PerformanceWorkerRegistry",
    "ReportSender",
    "ReportSendError",
    "RoundRobinScheduler",
    "WorkerFitness",
    "WorkerNotRegisteredError",
    "WorkerScheduler",
    "build_fitness",
    "health_ok",
    "version_compatible",
]
