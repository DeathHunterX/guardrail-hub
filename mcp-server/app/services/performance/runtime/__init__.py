"""Worker-side execution-lifecycle management for the Performance capability.

The Runtime owns one operation's lifecycle end to end — workspace → validate →
execute → collect → redact → persist → cleanup (ADR-0010 §4.4). This package
grows one stage at a time; the first is workspace lifecycle.
"""

from app.services.performance.runtime.performance_runtime import PerformanceRuntime
from app.services.performance.runtime.ports import PersistencePort, PlanValidator
from app.services.performance.runtime.workspace import (
    InvalidOperationIdError,
    Workspace,
    WorkspaceManager,
)

__all__ = [
    "InvalidOperationIdError",
    "PerformanceRuntime",
    "PersistencePort",
    "PlanValidator",
    "Workspace",
    "WorkspaceManager",
]
