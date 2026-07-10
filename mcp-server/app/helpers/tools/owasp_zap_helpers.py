"""
Utility helpers for the OWASP ZAP API scanner service.

Covers three concerns kept separate from business logic:
  - Request preparation  : build headers, serialize body
  - Alert conversion     : raw ZAP dict → typed ZapAlert / ZapScanSummary
  - ZAP interaction      : send request through proxy, register auth replacer rules
"""

import json
import subprocess
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.mcp_logger import MCPLogger
from app.schemas.tools.owasp_zap.api_scan import ZapApiScanRequest
from app.schemas.tools.owasp_zap.common import ZapApiTarget, ZapTokenType
from app.schemas.tools.owasp_zap.scan_result import (
    ZapAlert,
    ZapAlertInstance,
    ZapScanSummary,
    ZapTlsResult,
)

logger = MCPLogger("OwaspZapApiScanHelpers")


class ZapApiScanHelpers:
    """Static utility methods for the OWASP ZAP API scanner."""

    # ------------------------------------------------------------------
    # Request preparation
    # ------------------------------------------------------------------

    @staticmethod
    def build_request_headers(target: ZapApiTarget) -> dict[str, str]:
        """Build HTTP headers including the auth token and cookie."""
        headers: dict[str, str] = dict(target.headers or {})

        if target.token:
            if target.token_prefix:
                header_value = f"{target.token_prefix} {target.token}"
            elif target.token_type in (
                ZapTokenType.BEARER,
                ZapTokenType.JWT,
                ZapTokenType.ACCESS_TOKEN,
            ):
                header_value = f"Bearer {target.token}"
            else:
                header_value = target.token
            headers[target.token_header_name] = header_value

        if target.cookie:
            headers["Cookie"] = target.cookie

        return headers

    @staticmethod
    def serialize_body(target: ZapApiTarget) -> tuple[Optional[bytes], Optional[str]]:
        """Return ``(body_bytes, content_type)`` for the given target."""
        if target.body is None:
            return None, None

        if isinstance(target.body, (dict, list)):
            return json.dumps(target.body).encode(), "application/json"

        if isinstance(target.body, str):
            try:
                json.loads(target.body)
                return target.body.encode(), "application/json"
            except json.JSONDecodeError:
                return target.body.encode(), "text/plain"

        return None, None

    @staticmethod
    def scope_pattern(url: str) -> str:
        """Return a ZAP context regex that matches all paths under *url*'s origin."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}.*"

    # ------------------------------------------------------------------
    # Alert conversion
    # ------------------------------------------------------------------

    @staticmethod
    def convert_raw_alert(raw: dict) -> ZapAlert:
        """Map a raw ZAP alert dict to a typed :class:`ZapAlert`."""
        instances = [
            ZapAlertInstance(
                uri=inst.get("uri"),
                method=inst.get("method"),
                param=inst.get("param"),
                attack=inst.get("attack"),
                evidence=inst.get("evidence"),
                other_info=inst.get("otherinfo"),
            )
            for inst in raw.get("instances", [])
        ]
        cwe_raw = raw.get("cweid", "")
        wasc_raw = raw.get("wascid", "")
        return ZapAlert(
            alert_ref=str(raw.get("alertRef", raw.get("id", uuid.uuid4().hex))),
            name=raw.get("name", ""),
            risk=raw.get("risk", ""),
            confidence=raw.get("confidence", ""),
            description=raw.get("description", ""),
            url=raw.get("url", ""),
            solution=raw.get("solution", ""),
            reference=raw.get("reference", ""),
            cwe_id=int(cwe_raw) if cwe_raw and str(cwe_raw).isdigit() else None,
            wasc_id=int(wasc_raw) if wasc_raw and str(wasc_raw).isdigit() else None,
            instances=instances,
            tags=raw.get("tags", {}),
        )

    @staticmethod
    def build_summary(alerts: list[ZapAlert]) -> ZapScanSummary:
        """Aggregate alert counts by risk level into a :class:`ZapScanSummary`."""
        summary = ZapScanSummary(total=len(alerts))
        for alert in alerts:
            risk = alert.risk.lower()
            if risk == "high":
                summary.high += 1
            elif risk == "medium":
                summary.medium += 1
            elif risk == "low":
                summary.low += 1
            else:
                summary.informational += 1
        return summary

    # ------------------------------------------------------------------
    # ZAP interaction utilities
    # ------------------------------------------------------------------

    @staticmethod
    def send_through_proxy(
        proxy_url: str,
        request: ZapApiScanRequest,
        headers: dict[str, str],
    ) -> None:
        """
        Route *request* through the ZAP HTTP proxy so ZAP passively records it.

        Failures are logged as warnings rather than raised — a proxy failure does not
        prevent the subsequent active scan from running.
        """
        body_bytes, content_type = ZapApiScanHelpers.serialize_body(request)
        if content_type and "Content-Type" not in headers:
            headers["Content-Type"] = content_type

        try:
            with httpx.Client(
                proxy=proxy_url,
                verify=False,
                timeout=settings.zap_request_timeout_seconds,
            ) as http:
                http.request(
                    method=request.method.value,
                    url=request.url,
                    headers=headers,
                    content=body_bytes,
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Proxy request failed for %s: %s", request.url, exc)

    @staticmethod
    def check_tls(url: str) -> Optional[ZapTlsResult]:
        """
        Run ``sslscan`` against *url*'s hostname and return which TLS/SSL protocols
        are enabled or disabled.

        Returns ``None`` when ``sslscan`` is not installed or the command fails.
        """
        hostname = urlparse(url).netloc or url
        protocols = ["SSLv2", "SSLv3", "TLSv1.0", "TLSv1.1", "TLSv1.2", "TLSv1.3"]
        statuses: dict[str, str] = {p: "disabled" for p in protocols}

        try:
            logger.info("Starting TLS check for: %s", hostname)
            result = subprocess.run(
                ["sslscan", "--no-colour", "--get-ciphers", hostname],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                for proto in protocols:
                    if proto in line and any(kw in line for kw in ("Accepted", "Preferred")):
                        statuses[proto] = "enabled"
            logger.info("TLS check completed for: %s", hostname)

        except FileNotFoundError:
            logger.warning("sslscan not found — TLS check skipped for %s", hostname)
        except subprocess.CalledProcessError as exc:
            logger.error("sslscan failed for %s: %s", hostname, exc)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Unexpected error during TLS check for %s: %s", hostname, exc)

        # Always return a valid ZapTlsResult, even if the TLS check failed
        return ZapTlsResult.model_validate(statuses)

    @staticmethod
    def setup_auth_replacers(
        zap_api: Any,
        request: ZapApiScanRequest,
        headers: dict[str, str],
    ) -> None:
        """
        Register ZAP replacer rules so that every request made during an active scan
        automatically carries the correct auth token and/or cookie.
        """
        if request.token:
            auth_value = headers.get(request.token_header_name, "")
            zap_api.replacer.remove_rule("auth-token")
            zap_api.replacer.add_rule(
                description="auth-token",
                enabled="true",
                matchtype="REQ_HEADER",
                matchregex="false",
                matchstring=request.token_header_name,
                replacement=auth_value,
            )

        if request.cookie:
            zap_api.replacer.remove_rule("auth-cookie")
            zap_api.replacer.add_rule(
                description="auth-cookie",
                enabled="true",
                matchtype="REQ_HEADER",
                matchregex="false",
                matchstring="Cookie",
                replacement=request.cookie,
  
            )
