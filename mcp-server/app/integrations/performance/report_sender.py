"""Report transport — how a finished operation report reaches the server.

Split out from the persistence adapter so the payload-building logic is testable
without a network, and so the HTTP specifics live in one small, replaceable
place. The worker only ever makes this outbound call (no inbound channel).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Optional, Protocol, runtime_checkable

from app.schemas.performance.report import OperationReport


class ReportSendError(RuntimeError):
    """Raised when a report could not be delivered to the server."""


@runtime_checkable
class ReportSender(Protocol):
    """Deliver one :class:`OperationReport` to the server; raise on failure."""

    def send(self, report: OperationReport) -> None:
        ...


class HttpReportSender:
    """Delivers a report by POSTing JSON to the server's report endpoint.

    Authentication is a bearer token supplied by the deployment (ADR-0010 §4.9);
    the concrete scheme is intentionally simple here and swappable.
    """

    def __init__(
        self,
        report_url: str,
        *,
        auth_token: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._url = report_url
        self._auth_token = auth_token
        self._timeout = timeout_seconds

    def send(self, report: OperationReport) -> None:
        body = report.model_dump_json().encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        request = urllib.request.Request(self._url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                status = getattr(response, "status", response.getcode())
                if status // 100 != 2:
                    raise ReportSendError(f"report endpoint returned HTTP {status}")
        except urllib.error.URLError as exc:
            raise ReportSendError(f"could not deliver report: {exc}") from exc
