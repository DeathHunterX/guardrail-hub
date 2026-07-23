"""Worker authentication — an infrastructure concern at the router boundary only.

The performance worker-facing API (register/heartbeat/pull/report) authenticates
the calling worker with a deployment-provisioned bearer token (ADR-0010 §4.9).
This lives **only** here, as a FastAPI dependency applied to the router — the
`WorkerCoordinator`, Runtime, Dispatcher, Scheduler, and Registry stay entirely
unaware of authentication.

The expected token is **injected** by the composition root
(`build_worker_token_auth(settings.performance_worker_token)`); this module reads
no `Settings` itself (governance Gate E). Least-privilege on *which* operation a
worker may act upon is enforced separately in the coordinator (pull-mismatch →
409); this dependency only gates *access* to the endpoints.
"""

from __future__ import annotations

import secrets
from typing import Callable, Optional

from fastapi import Header, HTTPException, status


def build_worker_token_auth(expected_token: str) -> Callable[[Optional[str]], None]:
    """Return a FastAPI dependency that requires ``Authorization: Bearer <token>``.

    The token is captured by closure (injected), so the dependency reads no
    global config. Raises 401 on a missing/malformed header or a token mismatch.
    """

    def require_worker_token(authorization: Optional[str] = Header(default=None)) -> None:
        token = _bearer(authorization)
        if token is None or not secrets.compare_digest(token, expected_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing worker credential.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return require_worker_token


def _bearer(authorization: Optional[str]) -> Optional[str]:
    """Extract the bearer token, or None if absent/malformed."""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()
