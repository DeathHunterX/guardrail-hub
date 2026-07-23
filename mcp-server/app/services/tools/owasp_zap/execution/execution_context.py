"""Neutral execution context — the resources an operation was allocated at dispatch.

Introduced by [ADR-0009](../../../../../../.ai/decisions/0009-execution-capability.md)
H1 to replace the former ``worker: Optional[ZapWorkerInfo]`` parameter in the
generic handler contract (:mod:`.handler`). The point is subtraction: the
generic contract must say "the handler is given the resources this operation was
allocated" **without** naming a worker-pool type. For a worker-bound tool that
resource is a worker; for an orchestration operation it is nothing.

Accordingly this base carries *no* fields and *no* tool imports — an empty
:class:`ExecutionContext` is exactly the orchestration case (no resource
allocated). A worker-bound tool passes a tool-owned subclass that adds its
allocated resource (see ``zap_worker_context.ZapWorkerContext``). The generic
contract references only this neutral base, so a future ephemeral or
non-pooled tool can satisfy the same contract without importing a worker type.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionContext:
    """Dispatch-allocated resources handed to a handler.

    The empty base *is* the orchestration case: no worker, no resource. Tool
    packages that allocate a resource (e.g. a pooled worker) define a frozen
    subclass carrying it, keeping the neutral contract free of tool types.
    """
