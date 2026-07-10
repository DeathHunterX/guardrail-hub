"""
Interactive scanner service.

Two-step flow designed for AI-agent use:

Step 1 — ``start_session``
  • Creates a ZAP context scoped to the target app.
  • Returns the ZAP proxy address + a session token so the AI agent (or a
    human) can configure a browser to tunnel through ZAP.
  • Once the browser navigates the app, ZAP records every request.

Step 2 — ``run_scan``
  • Looks up the session by operation_id + session_token.
  • If ``selected_targets`` is provided, active-scans only those endpoints.
  • Otherwise, active-scans every URL ZAP recorded in that context.
  • Returns alerts.

Sessions are kept in-process memory. They survive server restarts poorly
but are sufficient for the typical short-lived MCP tool interaction.
"""
import time
import uuid
from typing import Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.schemas.tools.owasp_zap.common import ZapScanMode
from app.schemas.tools.owasp_zap.interactive_website_scan import (
    ZapInteractiveScanRequest,
    ZapInteractiveWebsiteStartRequest,
)
from app.schemas.tools.owasp_zap.scan_result import (
    ZapAlert,
    ZapAlertInstance,
    ZapInteractiveStartResult,
    ZapScanResult,
    ZapScanSummary,
)
from app.integrations.owasp_zap.client import ZapClient, ZapNotAvailableError
from app.core.mcp_logger import MCPLogger

logger = MCPLogger("OwaspZapInteractiveScanner")

# In-process session registry  {operation_id → session_dict}
_sessions: dict[str, dict] = {}


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


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ZapInteractiveScanService:
    def __init__(self) -> None:
        self._client = ZapClient()

    # ------------------------------------------------------------------
    # Step 1: start interactive session
    # ------------------------------------------------------------------

    def start_session(
        self, request: ZapInteractiveWebsiteStartRequest
    ) -> ZapInteractiveStartResult:
        self._client.require_healthy()

        operation_id = uuid.uuid4().hex
        session_token = uuid.uuid4().hex

        # Determine scope
        if request.include_in_context:
            scope_base = request.include_in_context
        else:
            parsed = urlparse(request.base_url)
            scope_base = f"{parsed.scheme}://{parsed.netloc}"

        context_name = f"interactive-{operation_id[:8]}"
        context_id = self._client.create_context(context_name)
        self._client.include_in_context(context_name, f"{scope_base}.*")

        # Persist session
        _sessions[operation_id] = {
            "context_id": context_id,
            "context_name": context_name,
            "project_name": request.base_url,  # used as project name fallback
            "base_url": request.base_url,
            "scope_base": scope_base,
            "session_token": session_token,
            "prompt": request.prompt,
            "created_at": time.time(),
        }

        proxy_host = self._client.proxy_host
        proxy_port = self._client.proxy_port
        viewer_url = (
            f"http://{proxy_host}:{proxy_port}/zap/index.html"
            f"?session_token={session_token}"
        )

        instructions = (
            f"1. Configure your browser HTTP/HTTPS proxy to: {proxy_host}:{proxy_port}. "
            f"2. Browse {request.base_url} — perform all the actions you want tested "
            f"(login, navigation, form submissions, API calls). "
            f"3. When finished, call zap_interactive_scan with: "
            f'operation_id="{operation_id}", session_token="{session_token}". '
            f"Optionally pass selected_targets to scan specific endpoints only."
        )

        return ZapInteractiveStartResult(
            operation_id=operation_id,
            proxy_host=proxy_host,
            proxy_port=proxy_port,
            session_token=session_token,
            viewer_url=viewer_url,
            instructions=instructions,
        )

    # ------------------------------------------------------------------
    # Step 2: run scan on recorded traffic
    # ------------------------------------------------------------------

    def run_scan(self, request: ZapInteractiveScanRequest) -> ZapScanResult:
        start_time = time.time()

        session = _sessions.get(request.operation_id)
        if not session:
            return ZapScanResult(
                operation_id=request.operation_id,
                project_name=request.operation_id,
                status="failed",
                target_url="N/A",
                duration_seconds=0,
                error=(
                    f"Session '{request.operation_id}' not found. "
                    "Call zap_interactive_start first."
                ),
            )

        if session["session_token"] != request.session_token:
            return ZapScanResult(
                operation_id=request.operation_id,
                project_name=session.get("project_name", request.operation_id),
                status="failed",
                target_url=session["base_url"],
                duration_seconds=0,
                error="Invalid session_token.",
            )

        base_url: str = session["base_url"]
        context_id: str = session["context_id"]
        context_name: str = session["context_name"]

        try:
            self._client.require_healthy()

            self._client.wait_for_passive_scan(
                timeout_seconds=settings.zap_passive_scan_timeout_seconds
            )

            # Determine targets to scan
            if request.selected_targets:
                targets_to_scan = [
                    (t.url, t.method.value, t.postdata)
                    for t in request.selected_targets
                ]
            else:
                recorded = self._client.get_recorded_urls(base_url=base_url)
                targets_to_scan = [(url, None, None) for url in recorded]

            if not targets_to_scan:
                logger.warning(
                    "No targets to scan for session %s. "
                    "Make sure you browsed the application through the proxy first.",
                    request.operation_id,
                )

            per_target_timeout = max(
                60,
                settings.zap_scan_timeout_seconds // max(1, len(targets_to_scan)),
            )

            for url, method, postdata in targets_to_scan:
                try:
                    if request.scan_mode == ZapScanMode.FULL:
                        ascan_id = self._client.run_active_scan(
                            url=url,
                            context_id=context_id,
                            method=method,
                            postdata=postdata,
                        )
                        self._client.wait_for_active_scan(
                            ascan_id, timeout_seconds=per_target_timeout
                        )
                    else:
                        # QUICK: passive scan already ran above
                        pass
                except Exception as exc:
                    logger.warning("Active scan failed for %s: %s", url, exc)

            # Collect alerts
            raw_alerts = self._client.get_alerts(base_url=base_url)
            alerts = [_convert_raw_alert(a) for a in raw_alerts]

            # Remove session after successful scan
            _sessions.pop(request.operation_id, None)
            self._client.remove_context(context_name)

            return ZapScanResult(
                operation_id=request.operation_id,
                project_name=session.get("project_name", request.operation_id),
                status="completed",
                target_url=base_url,
                duration_seconds=round(time.time() - start_time, 2),
                alerts=alerts,
                summary=_build_summary(alerts),
            )

        except ZapNotAvailableError as exc:
            return ZapScanResult(
                operation_id=request.operation_id,
                project_name=session.get("project_name", request.operation_id),
                status="failed",
                target_url=base_url,
                duration_seconds=round(time.time() - start_time, 2),
                error=str(exc),
            )
        except Exception as exc:
            logger.exception("Interactive scan failed: %s", exc)
            return ZapScanResult(
                operation_id=request.operation_id,
                project_name=session.get("project_name", request.operation_id),
                status="failed",
                target_url=base_url,
                duration_seconds=round(time.time() - start_time, 2),
                error=str(exc),
            )
