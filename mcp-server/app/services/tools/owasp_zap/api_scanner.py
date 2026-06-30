"""
API scanner service.

Flow for a single endpoint:
  1. Route the actual HTTP request through ZAP proxy → ZAP passively scans it.
  2. Wait for passive scan to finish.
  3. For QUICK mode: run spider scan then single-target active scan (URL params only).
  4. For FULL mode: run context-scoped active scan with full body fuzzing.
  5. Collect and return alerts.

The ``with_llm`` variants accept a ``prompt`` field for natural-language
scanner tuning. The LLM integration is stubbed here — in the future a
language model can map the prompt to ``ScannerThresholdOverride`` rules
that adjust scanner sensitivity before scanning.
"""

import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from fastapi import HTTPException

from app.constants.batch import BatchType
from app.constants.paths import ReportPaths
from app.core.config import settings
from app.core.mcp_logger import MCPLogger
from app.dao.operation_dao import get_operation_dao
from app.helpers.tools.owasp_zap_helpers import ZapApiScanHelpers
from app.integrations.owasp_zap.client import ZapClient
from app.integrations.owasp_zap.pool import OwaspZapPool
from app.schemas.tools.owasp_zap.api_scan import ZapApiScanRequest
from app.schemas.tools.owasp_zap.common import OperationStatus, ZapScanMode
from app.schemas.tools.owasp_zap.scan_result import ZapScanReports, ZapScanResult

zap_amount = int(max(1, settings.zap_amount_of_containers))
executor = ThreadPoolExecutor(max_workers=zap_amount)


class ZapApiScanService:
    """Singleton service that dispatches OWASP ZAP API scans to a thread-pool worker."""

    _instance: Optional["ZapApiScanService"] = None
    _instance_lock: Lock = Lock()

    def __new__(cls) -> "ZapApiScanService":
        # Double-checked locking: fast path (no lock) when instance already exists,
        # slow path (with lock) only on the very first call to avoid a race condition.
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self.app_logger = MCPLogger("OWASP ZAP")
        self.zap_pool = OwaspZapPool(zap_amount)
        self.zap_helpers = ZapApiScanHelpers()
        self.operation_dao = get_operation_dao()

        self._initialized = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_reports(
        self, zap_client: ZapClient, operation_id: str
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Fetch both HTML and JSON reports from ZAP and persist them to disk.

        Returns ``(html_report_url, json_report_url)``.  Either URL may be
        ``None`` when ZAP returns empty content or an error occurs — report
        failures never abort a completed scan.
        """
        base_url = settings.mcp_server_public_url.rstrip("/")
        report_dir = Path(ReportPaths.ZAP_DETAIL_DIR)

        html_url: Optional[str] = None
        json_url: Optional[str] = None

        try:
            report_dir.mkdir(parents=True, exist_ok=True)

            html_content = zap_client.html_report()
            if html_content:
                (report_dir / f"{operation_id}.html").write_text(html_content, encoding="utf-8")
                html_url = f"{base_url}/public/report/owasp-zap/detail-report/{operation_id}.html"
            else:
                self.app_logger.warning(f"ZAP returned empty HTML report for {operation_id}")

            json_content = zap_client.json_report()
            if json_content and json_content.strip() not in ("", "{}"):
                (report_dir / f"{operation_id}.json").write_text(json_content, encoding="utf-8")
                json_url = f"{base_url}/public/report/owasp-zap/detail-report/{operation_id}.json"
            else:
                self.app_logger.warning(f"ZAP returned empty JSON report for {operation_id}")

            self.app_logger.info(
                f"Reports saved for {operation_id} — html={html_url}  json={json_url}"
            )

        except Exception as exc:  # pylint: disable=broad-except
            self.app_logger.warning(f"Failed to save reports for {operation_id}: {exc}")

        return html_url, json_url

    # ------------------------------------------------------------------
    # Public: init scan (async dispatch)
    # ------------------------------------------------------------------

    def init_api_scan(self, request: ZapApiScanRequest) -> Dict:
        """
        Validate *request*, create a PENDING operation record, and dispatch
        the appropriate scan worker to the thread pool.

        Returns:
            Dict with ``operation_id``, ``status``, and a status-check message.
        """
        if not (request.project_name or "").strip():
            raise HTTPException(status_code=400, detail="Project name is required")

        try:
            op_id = str(uuid.uuid4())
            self.operation_dao.create_operation(
                op_id=op_id,
                status=OperationStatus.PENDING,
                batch_type=BatchType.API_SCAN,
                metadata={
                    "name": "Owasp Zap check",
                    "target_url": request.url,
                    "method": request.method,
                    "headers": request.headers,
                    "body": request.body,
                },
            )

            if request.scan_mode == ZapScanMode.QUICK:
                self.app_logger.info(f"Initialized QUICK API scan with operation_id: {op_id}")
                executor.submit(self.zap_scan_worker, op_id, request)
            else:
                self.app_logger.info(f"Initialized FULL API scan with operation_id: {op_id}")
                executor.submit(self.zap_full_scan_worker, op_id, request)

            return {
                "operation_id": op_id,
                "status": OperationStatus.PENDING,
                "message": (
                    f"Zap API scan initialized with operation_id: {op_id}. "
                    f"Check status at API api/history/get-result with param operation_id: {op_id}"
                ),
            }

        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Error initializing API scan:\n{str(e)}"
            ) from e

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def zap_scan_worker(self, operation_id: str, request: ZapApiScanRequest) -> None:
        """
        QUICK scan: passive scan → spider → single-target active scan.

        Active scan targets URL parameters only (injectable mask = 3).
        Body fuzzing is disabled to keep the scan fast.
        """
        zap_container = None
        start_time = time.time()

        try:
            zap_container, zap_client, zap_api = self.zap_pool.book_zap_slot(operation_id)
            self.app_logger.info(
                f"[{zap_container}] Start QUICK API scan {request.url}: {operation_id}"
            )

            zap_client.require_healthy()
            self.operation_dao.update_operation_status(operation_id=operation_id, status=OperationStatus.RUNNING)

            zap_client.new_session(f"api-quick-{operation_id[:8]}")

            context_name = f"api-scan-{operation_id[:8]}"
            context_id = zap_client.create_context(context_name)
            zap_client.include_in_context(context_name, self.zap_helpers.scope_pattern(request.url))

            # URL parameters only — no body fuzzing in quick mode
            zap_api.ascan.set_option_target_params_injectable(3)

            headers = self.zap_helpers.build_request_headers(request)
            self.zap_helpers.setup_auth_replacers(zap_api, request, headers)
            self.zap_helpers.send_through_proxy(zap_client.proxy_url, request, headers)

            zap_client.wait_for_passive_scan(timeout_seconds=settings.zap_passive_scan_timeout_seconds)

            # Spider scan
            self.app_logger.info(f"[{zap_container}] Starting spider scan: {operation_id}")
            spider_id = zap_client.run_spider(url=request.url, context_name=context_name)
            zap_client.wait_for_spider(spider_id, timeout_seconds=settings.zap_spider_timeout_seconds)
            self.app_logger.info(f"[{zap_container}] Spider scan done: {operation_id}")

            # Active scan — single URL, no recursion
            self.app_logger.info(f"[{zap_container}] Starting active scan: {operation_id}")
            body_bytes, _ = self.zap_helpers.serialize_body(request)
            postdata = body_bytes.decode() if body_bytes else None
            ascan_id = zap_client.run_active_scan(
                url=request.url,
                context_id=context_id,
                recurse=False,
                method=request.method.value,
                postdata=postdata,
            )
            self.operation_dao.update_operation_status(
                operation_id=operation_id,
                status=OperationStatus.RUNNING,
                result={"ascan_scan_id": ascan_id, "ascan_progress": "0%"},
            )
            zap_client.wait_for_active_scan(ascan_id, timeout_seconds=settings.zap_scan_timeout_seconds)
            self.app_logger.info(f"[{zap_container}] Active scan done: {operation_id}")

            raw_alerts = zap_client.get_alerts(base_url=request.url)
            alerts = [self.zap_helpers.convert_raw_alert(a) for a in raw_alerts]
            zap_client.remove_context(context_name)

            view_report, export_data = self._save_reports(zap_client, operation_id)

            self.operation_dao.update_operation_status(
                operation_id=operation_id,
                status=OperationStatus.COMPLETED,
                result=ZapScanResult(
                    operation_id=operation_id,
                    project_name=request.project_name,
                    status="completed",
                    target_url=request.url,
                    duration_seconds=round(time.time() - start_time, 2),
                    alerts=alerts,
                    summary=self.zap_helpers.build_summary(alerts),
                    tls_result=self.zap_helpers.check_tls(request.url),
                    reports=ZapScanReports(view_report=view_report, export_data=export_data),
                ).model_dump(by_alias=True),
            )

        except Exception as e:  # pylint: disable=broad-except
            self.app_logger.error(f"Error in zap_scan_worker for operation_id {operation_id}: {e}")
            self.operation_dao.update_operation_status(
                operation_id=operation_id,
                status=OperationStatus.FAILED,
                error=str(e),
            )

        finally:
            if zap_container:
                self.zap_pool.release_zap_slot(zap_container, operation_id)

    def zap_full_scan_worker(self, operation_id: str, request: ZapApiScanRequest) -> None:
        """
        FULL scan: passive scan → context-scoped active scan with body fuzzing.

        Active scan targets all injectable points including the request body
        (injectable mask = 31). No spider — the proxy-recorded request seeds the
        context directly so ZAP can fuzz the exact endpoint.
        """
        zap_container = None
        start_time = time.time()

        try:
            zap_container, zap_client, zap_api = self.zap_pool.book_zap_slot(operation_id)
            self.app_logger.info(f"[{zap_container}] Start FULL API scan {request.url}: {operation_id}")

            zap_client.require_healthy()
            self.operation_dao.update_operation_status(operation_id=operation_id, status=OperationStatus.RUNNING)

            zap_client.new_session(f"api-full-{operation_id[:8]}")

            # All params including body — full fuzzing
            zap_api.ascan.set_option_target_params_injectable(31)

            headers = self.zap_helpers.build_request_headers(request)
            self.zap_helpers.setup_auth_replacers(zap_api, request, headers)
            self.zap_helpers.send_through_proxy(zap_client.proxy_url, request, headers)

            zap_client.wait_for_passive_scan(timeout_seconds=settings.zap_passive_scan_timeout_seconds)

            # Context scoped to the base path so the active scan covers the full endpoint
            target_base = re.sub(r"[^/]+$", "", request.url)
            context_name = f"api-full-{operation_id[:8]}"
            context_id = zap_client.create_context(context_name)
            zap_client.include_in_context(context_name, target_base + ".*")

            # Active scan — full context, recursive, body fuzzing enabled
            self.app_logger.info(f"[{zap_container}] Starting full active scan: {operation_id}")
            ascan_id = zap_client.run_active_scan(url=request.url, context_id=context_id, recurse=True)
            self.operation_dao.update_operation_status(
                operation_id=operation_id,
                status=OperationStatus.RUNNING,
                result={"ascan_scan_id": ascan_id, "ascan_progress": "0%"},
            )
            zap_client.wait_for_active_scan(ascan_id, timeout_seconds=settings.zap_scan_timeout_seconds)
            self.app_logger.info(f"[{zap_container}] Full active scan done: {operation_id}")

            raw_alerts = zap_client.get_alerts(base_url=request.url)
            alerts = [self.zap_helpers.convert_raw_alert(a) for a in raw_alerts]
            zap_client.remove_context(context_name)

            view_report, export_data = self._save_reports(zap_client, operation_id)

            self.operation_dao.update_operation_status(
                operation_id=operation_id,
                status=OperationStatus.COMPLETED,
                result=ZapScanResult(
                    operation_id=operation_id,
                    project_name=request.project_name,
                    status="completed",
                    target_url=request.url,
                    duration_seconds=round(time.time() - start_time, 2),
                    alerts=alerts,
                    summary=self.zap_helpers.build_summary(alerts),
                    tls_result=self.zap_helpers.check_tls(request.url),
                    reports=ZapScanReports(view_report=view_report, export_data=export_data),
                ).model_dump(by_alias=True),
            )

        except Exception as e:
            self.app_logger.error(f"Error in zap_full_scan_worker for operation_id {operation_id}: {e}")
            self.operation_dao.update_operation_status(
                operation_id=operation_id,
                status=OperationStatus.FAILED,
                error=str(e),
            )

        finally:
            if zap_container:
                self.zap_pool.release_zap_slot(zap_container, operation_id)
