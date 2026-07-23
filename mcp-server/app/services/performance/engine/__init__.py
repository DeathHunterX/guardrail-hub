"""Replaceable-engine seam for the Performance capability.

Public contract: the neutral DTOs and the ``PerformanceRunner`` protocol. A new
engine implements ``PerformanceRunner`` against these DTOs and is wired in the
composition root — no orchestration change (ADR-0010 D5). This package imports
**nothing** engine-specific; that direction (engine → seam) is the whole point.
"""

from app.services.performance.engine.dto import (
    Artifact,
    ArtifactKind,
    ArtifactSet,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)
from app.services.performance.engine.runner import PerformanceRunner

__all__ = [
    "Artifact",
    "ArtifactKind",
    "ArtifactSet",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionStatus",
    "PerformanceRunner",
]
