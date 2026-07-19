"""Execution-time OpenAPI expansion for the suite orchestrator.

Thin re-export of the shared, pure parser in
``app.schemas.tools.owasp_zap.openapi_spec`` so there is a single source of truth
used by both the request validator (fail fast) and the orchestrator. Kept as a
stable import path for the orchestrator and its tests.
"""

from app.schemas.tools.owasp_zap.openapi_spec import (
    Endpoint,
    OpenApiSpecError,
    extract_endpoints,
    load_spec,
)

__all__ = ["Endpoint", "OpenApiSpecError", "extract_endpoints", "load_spec"]
