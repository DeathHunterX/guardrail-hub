"""Performance worker-pool infrastructure (engine-neutral).

Parallel to ``app/integrations/owasp_zap`` but for the pull-model warm worker:
the registry today; pool manager, scheduler, and dispatcher as Phase 2 lands.
Kept separate from ZAP per ADR-0010 D4 (parallel infra, not a premature shared
extraction; consolidation trigger recorded in §8).
"""

from app.integrations.performance.registry import (
    PerformanceWorkerRegistry,
    WorkerNotRegisteredError,
)
from app.integrations.performance.report_sender import (
    HttpReportSender,
    ReportSender,
    ReportSendError,
)

__all__ = [
    "HttpReportSender",
    "PerformanceWorkerRegistry",
    "ReportSender",
    "ReportSendError",
    "WorkerNotRegisteredError",
]
