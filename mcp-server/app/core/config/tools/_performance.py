from typing import Optional


class PerformanceMixin:
    # =====================================================
    # Performance Engine (warm-worker pull model)
    # =====================================================
    # Deployment-wide settings for the Performance subsystem (ADR-0010). Like
    # the ZAP mixin, there is no worker prefix/count here — workers self-register
    # and the registry is the source of truth. These values are read only in the
    # composition root (wiring/bootstrap) and injected into the subsystem; no
    # subsystem module reads Settings itself (governance Gate E).

    # [REQUIRED IN PRODUCTION] Shared credential a worker presents on the
    # worker-facing API (register/heartbeat/pull/report). Must be changed from
    # the default below (§4.9 authentication boundary).
    performance_worker_token: str = "change-this-performance-worker-token"

    # How often the Performance dispatcher polls the Operations table (scoped to
    # Performance types) for QUEUED work to assign.
    performance_queue_poll_interval_seconds: float = 2.0

    # A worker that misses heartbeats for this long is marked Offline; any
    # operation it was assigned is failed (no auto-retry).
    performance_worker_heartbeat_timeout_seconds: int = 60

    # How often the dispatcher sweeps the registry for heartbeat-expired workers.
    performance_worker_heartbeat_sweep_interval_seconds: float = 10.0

    # How often a worker sends its heartbeat (worker-side cadence).
    performance_worker_heartbeat_interval_seconds: float = 5.0

    # Optional minimum compatible worker version; workers below it are registered
    # but never assigned (§4.8 / INV11). None disables the check.
    performance_min_compatible_version: Optional[str] = None
