"""Performance worker schemas — the pull-model registration/heartbeat protocol.

A performance worker is a long-lived process that self-registers and heartbeats,
but — unlike a ZAP worker — exposes **no inbound endpoint** (ADR-0010 §4.2). So
these models differ from the ZAP worker schemas in two deliberate ways:

- there is no ``endpoint``/``port`` (the server never calls the worker);
- the heartbeat carries **health** (§2.3) and its response is the worker's only
  inbound channel, conveying an assignment and a cancel flag (§4.2/§4.3).

Kept engine-neutral: nothing here names JMeter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class PerformanceWorkerLifecycleState(str, Enum):
    """Whether a worker may receive new work. Busy/idle is derived from ``op_id``.

        ACTIVE   -> may receive new operations (subject to being idle + healthy).
        DRAINING -> finishing its current operation, then goes OFFLINE.
        OFFLINE  -> heartbeat-expired or drained; never assigned.
    """

    ACTIVE = "active"
    DRAINING = "draining"
    OFFLINE = "offline"


class WorkerHealth(BaseModel):
    """Worker fitness reported on every heartbeat (ADR-0010 §2.3).

    The dispatcher uses this — not just idleness — to decide schedulability: a
    worker can be idle yet unfit (low memory, disk pressure, leaked orphans).
    All fields optional so a worker may report a subset.
    """

    cpu_percent: Optional[float] = Field(None, description="Recent CPU utilisation, 0-100.")
    memory_percent: Optional[float] = Field(None, description="Memory utilisation, 0-100.")
    disk_percent: Optional[float] = Field(None, description="Workspace-filesystem utilisation, 0-100.")
    workspace_bytes: Optional[int] = Field(None, description="Total bytes under the workspace root.")
    orphan_process_count: Optional[int] = Field(
        None, description="Engine child processes still alive with no active job (leak signal)."
    )
    last_cleanup_at: Optional[datetime] = Field(
        None, description="When the worker last destroyed a workspace."
    )


class PerformanceWorkerRegisterRequest(BaseModel):
    """Body a worker POSTs to register on startup."""

    worker_id: Optional[str] = Field(
        None, description="Stable id; defaults to HOSTNAME, else a generated UUID."
    )
    hostname: str = Field(..., description="Worker hostname (observability / default id).")
    version: Optional[str] = Field(None, description="Worker image/version, for compatibility gating.")


class PerformanceWorkerRegisterResponse(BaseModel):
    worker_id: str
    state: PerformanceWorkerLifecycleState
    registered_at: datetime
    min_compatible_version: Optional[str] = Field(
        None, description="Server's minimum compatible worker version (§4.8), for the worker's own awareness."
    )


class PerformanceWorkerHeartbeatRequest(BaseModel):
    """Body a worker POSTs periodically — liveness plus health."""

    worker_id: str
    health: WorkerHealth = Field(default_factory=WorkerHealth)


class PerformanceWorkerHeartbeatResponse(BaseModel):
    """The worker's only inbound channel (ADR-0010 §4.2/§4.3).

    Carries the current control state: whether an operation has been assigned to
    pull, and whether cancellation of the current operation has been requested.
    """

    worker_id: str
    state: PerformanceWorkerLifecycleState
    last_heartbeat: datetime
    assignment: Optional[str] = Field(
        None, description="operation_id to pull and execute, if one was assigned."
    )
    cancel_requested: bool = Field(
        False, description="True if the worker should cancel its current operation."
    )


class PullAssignmentRequest(BaseModel):
    """Body a worker POSTs to pull the plan for the operation it was assigned."""

    worker_id: str
    operation_id: str


class PerformanceAssignmentResponse(BaseModel):
    """The plan + minimal policy the worker pulls for its assigned operation.

    The (already-validated) plan travels base64-encoded; ``timeout_seconds`` is
    the resolved execution bound. Richer execution policy (ADR-0010 §4.7) is
    additive to this response and does not change the contract shape.
    """

    operation_id: str
    plan_b64: str
    timeout_seconds: Optional[float] = None


class PerformanceWorkerInfo(BaseModel):
    """Scheduling-facing view of one registered worker.

    ``op_id`` is the single source of truth for busy/idle. ``health`` is the last
    reported fitness; ``cancel_requested`` is the server-set intent the next
    heartbeat surfaces to the worker.
    """

    worker_id: str
    hostname: str
    version: Optional[str] = None
    state: PerformanceWorkerLifecycleState = PerformanceWorkerLifecycleState.ACTIVE
    op_id: Optional[str] = None
    cancel_requested: bool = False
    health: WorkerHealth = Field(default_factory=WorkerHealth)
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_idle(self) -> bool:
        return self.op_id is None

    @property
    def is_schedulable(self) -> bool:
        """Idle and ACTIVE. Health/version fitness is applied by the scheduler."""
        return self.is_idle and self.state == PerformanceWorkerLifecycleState.ACTIVE


def generate_worker_id() -> str:
    """Fallback worker_id when a worker registers without one or a hostname."""
    return f"perf-worker-{uuid4().hex[:12]}"
