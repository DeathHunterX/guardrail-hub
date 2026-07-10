"""
Website scanner service.

Flow:
  1. Create a ZAP context and include all target URLs in scope.
  2. Configure form-based authentication with the provided credentials.
  3. Create a ZAP user and set it as the forced user.
  4. Set login/logout indicators for session detection.
  5. Run ZAP Spider (with authentication) over the provided URL list.
  6. For FULL mode: run Active Scan after spidering.
  7. Collect and return alerts.
"""
import time
import uuid
from urllib.parse import urlparse

from app.core.config import settings
from app.schemas.tools.owasp_zap.scan_result import (
    ZapAlert,
    ZapAlertInstance,
    ZapScanResult,
    ZapScanSummary,
)
from app.schemas.tools.owasp_zap.website_scan import (
    ZapWebsiteScanRequest,
    ZapWebsiteScanWithLLMRequest,
)
from app.schemas.tools.owasp_zap.common import ZapScanMode
from app.integrations.owasp_zap.client import ZapClient, ZapNotAvailableError
from app.core.mcp_logger import MCPLogger

logger = MCPLogger("OwaspZapWebScanner")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _convert_raw_alert(raw: dict) -> ZapAlert:
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


def _build_summary(alerts: list[ZapAlert]) -> ZapScanSummary:
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


def _base_scope(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}.*"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ZapWebScanService:
    def __init__(self) -> None:
        self._client = ZapClient()

    def scan(self, request: ZapWebsiteScanRequest) -> ZapScanResult:
        operation_id = uuid.uuid4().hex
        start_time = time.time()

        try:
            self._client.require_healthy()

            context_name = f"web-scan-{scan_id[:8]}"
            context_id = self._client.create_context(context_name)

            # Scope: include login URL + all target URLs
            all_urls = [request.login_url] + list(request.urls)
            scope_origins: set[str] = set()
            for url in all_urls:
                scope_origins.add(_base_scope(url))

            if request.include_in_context:
                # Quick mode: explicit prefix provided
                self._client.include_in_context(
                    context_name, f"{request.include_in_context}.*"
                )
            else:
                for pattern in scope_origins:
                    self._client.include_in_context(context_name, pattern)

            # Form-based authentication
            token_field = request.token_field
            self._client.setup_form_auth(
                context_id=context_id,
                login_url=request.login_url,
                username_param="username",
                password_param="password",
                extra_post_data=f"{token_field}={{%token%}}" if token_field else None,
            )

            if request.login_indicator:
                self._client.set_login_indicator(context_id, request.login_indicator)
            if request.logout_indicator:
                self._client.set_logout_indicator(context_id, request.logout_indicator)

            # Create authenticated user
            user_id = self._client.create_user(context_id, "scan-user")
            self._client.set_user_credentials(
                context_id, user_id, request.username, request.password
            )
            self._client.set_forced_user(context_id, user_id)

            # Spider each target URL
            spider_ids: list[str] = []
            for url in request.urls:
                try:
                    sid = self._client.run_spider_as_user(
                        context_id=context_id,
                        user_id=user_id,
                        url=url,
                        recurse=True,
                    )
                    spider_ids.append(sid)
                except Exception as exc:
                    logger.warning("Spider failed for %s: %s", url, exc)

            for sid in spider_ids:
                self._client.wait_for_spider(
                    sid, timeout_seconds=settings.zap_spider_timeout_seconds
                )

            self._client.wait_for_passive_scan(
                timeout_seconds=settings.zap_passive_scan_timeout_seconds
            )

            # Active scan (FULL mode only)
            if request.scan_mode == ZapScanMode.FULL:
                per_url_timeout = max(
                    60,
                    settings.zap_scan_timeout_seconds // max(1, len(request.urls)),
                )
                for url in request.urls:
                    try:
                        ascan_id = self._client.run_active_scan_as_user(
                            url=url,
                            context_id=context_id,
                            user_id=user_id,
                            recurse=True,
                        )
                        self._client.wait_for_active_scan(
                            ascan_id, timeout_seconds=per_url_timeout
                        )
                    except Exception as exc:
                        logger.warning("Active scan failed for %s: %s", url, exc)

            # Collect + deduplicate alerts
            seen: set[tuple[str, str]] = set()
            all_alerts: list[ZapAlert] = []
            for url in request.urls:
                for raw in self._client.get_alerts(base_url=url):
                    alert = _convert_raw_alert(raw)
                    key = (alert.alert_ref, alert.url)
                    if key not in seen:
                        seen.add(key)
                        all_alerts.append(alert)

            self._client.remove_context(context_name)

            return ZapScanResult(
                operation_id=operation_id,
                project_name=request.project_name,
                status="completed",
                target_url=request.login_url,
                duration_seconds=round(time.time() - start_time, 2),
                alerts=all_alerts,
                summary=_build_summary(all_alerts),
            )

        except ZapNotAvailableError as exc:
            return ZapScanResult(
                operation_id=operation_id,
                project_name=request.project_name,
                status="failed",
                target_url=request.login_url,
                duration_seconds=round(time.time() - start_time, 2),
                error=str(exc),
            )
        except Exception as exc:
            logger.exception("Website scan failed: %s", exc)
            return ZapScanResult(
                operation_id=operation_id,
                project_name=request.project_name,
                status="failed",
                target_url=request.login_url,
                duration_seconds=round(time.time() - start_time, 2),
                error=str(exc),
            )

    def scan_with_llm(self, request: ZapWebsiteScanWithLLMRequest) -> ZapScanResult:
        """Same as scan() but accepts an optional LLM prompt for future tuning."""
        if request.prompt:
            logger.info(
                "LLM prompt received (tuning not yet applied): %s", request.prompt
            )
        return self.scan(request)
