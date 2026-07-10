class ZapMixin:
    # =====================================================
    # OWASP ZAP
    # =====================================================
    # There is intentionally no worker-name / prefix / count configuration
    # here (no ZAP_WORKERS, no hostname array, no prefix+index generation).
    # Workers self-register at runtime via POST /workers/register and the
    # Worker Registry is the single source of truth for the pool — see
    # app/integrations/owasp_zap/registry.py. Only genuinely deployment-wide
    # settings live in this mixin.

    zap_api_key: str = "change-this-zap-key"

    # Health check: how many consecutive successes a worker's own startup probe
    # should require before it registers itself (enforced worker-side, by the
    # registration script — see docker/owasp_zap/register-worker.sh).
    zap_ready_stable_success_count: int = 3

    # How long (seconds) to wait for each scan phase to complete.
    zap_scan_timeout_seconds: int = 600
    zap_spider_timeout_seconds: int = 300
    zap_passive_scan_timeout_seconds: int = 120

    # Timeout for a single proxied HTTP request sent through ZAP.
    zap_request_timeout_seconds: float = 30.0

    # =====================================================
    # Worker Registry / Pool Manager
    # =====================================================
    # A worker that hasn't sent a heartbeat within this many seconds is
    # considered Offline: no new operations are assigned to it, and any
    # operation it was executing is marked FAILED (no automatic retry).
    zap_worker_heartbeat_timeout_seconds: int = 60

    # How often the background sweeper checks every registered worker's
    # last_heartbeat against the timeout above.
    zap_worker_heartbeat_sweep_interval_seconds: float = 10.0

    # How often the Pool Manager polls the Operations table for QUEUED
    # operations and tries to assign them to an idle worker.
    zap_queue_poll_interval_seconds: float = 2.0
