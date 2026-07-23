"""ZAP worker-bound execution context (tool-owned, per ADR-0009 H1).

This is the ZAP tool's concrete :class:`ExecutionContext`: the resource a
worker-bound ZAP operation is allocated at dispatch is exactly one assigned
worker. It is deliberately kept *out* of the neutral contract module
(:mod:`.handler` / :mod:`.execution_context`) so that ``ZapWorkerInfo`` — a
tool schema — never re-enters the generic execution contract. The Dispatcher
constructs one of these when it assigns a worker; the worker-bound handlers
read the worker back out of it.
"""

from dataclasses import dataclass

from app.schemas.tools.owasp_zap.worker import ZapWorkerInfo
from app.services.tools.owasp_zap.execution.execution_context import ExecutionContext


@dataclass(frozen=True)
class ZapWorkerContext(ExecutionContext):
    """Carries the ZAP worker a worker-bound operation was assigned."""

    worker: ZapWorkerInfo
