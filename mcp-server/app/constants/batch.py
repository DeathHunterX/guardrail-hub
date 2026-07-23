class BatchType:
    API_SCAN = "api_scan"
    WEB_SCAN = "web_scan"
    INTERACTIVE_SCAN = "interactive_scan"
    BATCH_SCAN = "batch_scan"
    SUITE_SCAN = "suite_scan"
    # Performance-engine operation category (not a security scan; deliberately
    # excluded from ALL_SCAN_TYPES below).
    PERFORMANCE_TEST = "performance_test"
    UNKNOWN = "unknown"

    ALL_SCAN_TYPES: frozenset[str] = frozenset(
        {API_SCAN, WEB_SCAN, INTERACTIVE_SCAN, BATCH_SCAN, SUITE_SCAN}
    )
