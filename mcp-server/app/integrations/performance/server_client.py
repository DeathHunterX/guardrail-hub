"""Server client — the worker's outbound calls to the server (register/heartbeat/pull).

The pull-model counterpart to the report channel: the worker only ever makes
outbound calls (no inbound channel). Split as a port so the worker loop is
testable against an in-process fake, with a urllib-based HTTP implementation for
real deployments.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Optional, Protocol, runtime_checkable

from app.schemas.performance.worker import (
    PerformanceAssignmentResponse,
    PerformanceWorkerHeartbeatRequest,
    PerformanceWorkerHeartbeatResponse,
    PerformanceWorkerRegisterRequest,
    PerformanceWorkerRegisterResponse,
    PullAssignmentRequest,
)


class ServerClientError(RuntimeError):
    """Raised when a call to the server fails."""


@runtime_checkable
class ServerClient(Protocol):
    """The worker→server calls. Every method raises on transport failure."""

    def register(
        self, request: PerformanceWorkerRegisterRequest
    ) -> PerformanceWorkerRegisterResponse: ...

    def heartbeat(
        self, request: PerformanceWorkerHeartbeatRequest
    ) -> PerformanceWorkerHeartbeatResponse: ...

    def pull(self, request: PullAssignmentRequest) -> PerformanceAssignmentResponse: ...


class HttpServerClient:
    """``ServerClient`` over HTTP (JSON), matching the worker-facing router paths."""

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._auth_token = auth_token
        self._timeout = timeout_seconds

    def register(self, request):
        return self._post("/performance/workers/register", request, PerformanceWorkerRegisterResponse)

    def heartbeat(self, request):
        return self._post("/performance/workers/heartbeat", request, PerformanceWorkerHeartbeatResponse)

    def pull(self, request):
        return self._post("/performance/workers/pull", request, PerformanceAssignmentResponse)

    def _post(self, path, request_model, response_model):
        body = request_model.model_dump_json().encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        req = urllib.request.Request(self._base + path, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status = getattr(resp, "status", resp.getcode())
                payload = resp.read()
        except urllib.error.URLError as exc:
            raise ServerClientError(f"{path} failed: {exc}") from exc
        if status // 100 != 2:
            raise ServerClientError(f"{path} returned HTTP {status}")
        return response_model.model_validate_json(payload)
