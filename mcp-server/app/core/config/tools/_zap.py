class ZapMixin:
    # =====================================================
    # OWASP ZAP
    # =====================================================
    zap_container_name_prefix: str = "owasp-zap"

    # Internal container port (same for every ZAP instance).
    zap_api_port: int = 8080

    zap_api_key: str = "change-this-zap-key"

    # Pool size — number of ZAP containers running in parallel.
    zap_amount_of_containers: int = 1

    # Health check: how many consecutive successes = ready.
    zap_ready_stable_success_count: int = 3

    # How long (seconds) to wait for each scan phase to complete.
    zap_scan_timeout_seconds: int = 600
    zap_spider_timeout_seconds: int = 300
    zap_passive_scan_timeout_seconds: int = 120

    # Timeout for a single proxied HTTP request sent through ZAP.
    zap_request_timeout_seconds: float = 30.0
