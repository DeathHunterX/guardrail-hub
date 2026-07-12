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

Queueing model
--------------
``init_api_scan`` no longer picks a worker or submits work itself. It only
persists a ``QUEUED`` operation (the full request goes into ``metadata`` so
the operation can be resumed even after a server restart) and returns
immediately. The background dispatcher
(``app/services/tools/owasp_zap/dispatcher.py``) polls the Operations table
for queued work, assigns it to an idle worker via the Pool Manager, and only
then calls :meth:`ZapApiScanService.run_assigned_scan`, which is what
actually submits ``zap_scan_worker`` / ``zap_full_scan_worker`` to the thread
pool below.
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
from app.core.events.dispatcher import InProcessEventDispatcher
from app.core.mcp_logger import MCPLogger
from app.dao.operation_dao import get_operation_dao
from app.helpers.tools.owasp_zap_helpers import ZapApiScanHelpers
from app.integrations.owasp_zap.client import ZapClient
from app.integrations.owasp_zap.runtime import pool_manager as default_pool_manager
from app.schemas.tools.owasp_zap.api_scan import ZapApiScanRequest
from app.schemas.tools.owasp_zap.common import OperationStatus, ZapScanMode
from app.schemas.tools.owasp_zap.scan_result import ZapScanReports, ZapScanResult
from app.schemas.tools.owasp_zap.worker import ZapWorkerInfo
from app.services.operations.operation_service import OperationService

# Thread-pool sizing is decoupled from worker count on purpose: how many
# scans can actually run concurrently is bounded by how many ZAP workers are
# registered and Active (see the Pool Manager), not by this executor. A
# generous fixed cap just bounds in-process thread overhead.
executor = ThreadPoolExecutor(max_workers=32, thread_name_prefix="zap-scan-worker")


class ZapApiScanService:
    """Singleton service that runs OWASP ZAP API scans on a thread-pool worker."""

    _instance: Optional["ZapApiScanService"] = None
    _instance_lock: Lock = Lock()

    def __new__(cls, *args, **kwargs) -> "ZapApiScanService":
        # Accept (and ignore) constructor args: a custom __new__ receives whatever
        # was passed to the class call, so it must tolerate __init__'s keyword
        # arguments (e.g. operation_service=...). __init__ is what consumes them.
        # Double-checked locking: fast path (no lock) when instance already exists,
        # slow path (with lock) only on the very first call to avoid a race condition.
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, operation_service: Optional[OperationService] = None) -> None:
        # Singleton: allow startup to inject the shared (event-publishing)
        # OperationService even if a prior no-arg construction already ran.
        if getattr(self, "_initialized", False):
            if operation_service is not None:
                self.operation_service = operation_service
            return

        self.app_logger = MCPLogger("OwaspZapApiScanService")
        self.pool_manager = default_pool_manager
        self.zap_helpers = ZapApiScanHelpers()
        self.operation_dao = get_operation_dao()
        # All lifecycle transitions + progress go through OperationService (the
        # single owner of state transition, persistence, and event publication).
        # The scanner stays transport-agnostic: it knows OperationService, never
        # Slack/NotificationService/OperationNotifier. When not injected, an
        # unsubscribed in-process bus makes this behave exactly like the previous
        # direct-DAO path — persist, publish to no subscribers.
        self.operation_service = operation_service or OperationService(
            self.operation_dao, InProcessEventDispatcher()
        )

        self._initialized = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _findings_from_summary(summary) -> dict:
        """Map a :class:`ZapScanSummary` to the generic severity breakdown the
        notification layer understands. ZAP's risk scale tops out at High, so
        ``critical`` is always 0 here; the field is kept so the presentation
        model stays tool-agnostic (a future tool can populate it)."""
        return {
            "critical": 0,
            "high": summary.high,
            "medium": summary.medium,
            "low": summary.low,
            "informational": summary.informational,
        }

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
    # Public: init scan (persist as QUEUED, no assignment yet)
    # ------------------------------------------------------------------

    def init_api_scan(self, request: ZapApiScanRequest) -> Dict:
        """
        Validate *request* and persist a ``QUEUED`` operation record.

        The full request is stored under ``metadata["request"]`` so the
        dispatcher can reconstruct it and run the scan later — including
        after an mcp-server restart, since this row is the queue.

        Returns:
            Dict with ``operation_id``, ``status``, and a status-check message.
        """
        if not (request.project_name or "").strip():
            raise HTTPException(status_code=400, detail="Project name is required")

        try:
            op_id = str(uuid.uuid4())
            self.operation_service.create(
                batch_type=BatchType.API_SCAN,
                operation_id=op_id,
                metadata={
                    "name": "Owasp Zap check",
                    "target_url": request.url,
                    "method": request.method,
                    "request": request.model_dump(mode="json", by_alias=True),
                },
            )

            self.app_logger.info(
                f"Queued {request.scan_mode.value} API scan with operation_id: {op_id}"
            )

            return {
                "operation_id": op_id,
                "status": OperationStatus.QUEUED,
                "message": (
                    f"Zap API scan queued with operation_id: {op_id}. It will start as soon as "
                    f"a ZAP worker is available. Check status at API api/history/get-result "
                    f"with param operation_id: {op_id}"
                ),
            }

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error initializing API scan:\n{str(e)}",
            ) from e

    @staticmethod
    def request_from_metadata(metadata: dict) -> ZapApiScanRequest:
        """Reconstruct the original :class:`ZapApiScanRequest` from a persisted operation.

        Used by the dispatcher to resume a ``QUEUED`` operation without
        needing anything held in memory — including across a server restart.
        """
        return ZapApiScanRequest.model_validate(metadata["request"])

    # ------------------------------------------------------------------
    # Public: run an already-assigned scan (called by the dispatcher)
    # ------------------------------------------------------------------

    def run_assigned_scan(
        self, operation_id: str, request: ZapApiScanRequest, worker: ZapWorkerInfo
    ) -> None:
        """Submit the worker function matching *request.scan_mode* to the thread pool.

        Called by the dispatcher only after the Pool Manager has already
        assigned *worker* to *operation_id* — this method does no scheduling
        of its own.
        """
        if request.scan_mode == ZapScanMode.QUICK:
            executor.submit(self.zap_scan_worker, operation_id, request, worker)
        else:
            executor.submit(self.zap_full_scan_worker, operation_id, request, worker)

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def zap_scan_worker(
        self, operation_id: str, request: ZapApiScanRequest, worker: ZapWorkerInfo
    ) -> None:
        """
        QUICK scan: passive scan → spider → single-target active scan.

        Active scan targets URL parameters only (injectable mask = 3).
        Body fuzzing is disabled to keep the scan fast.

        *worker* was already assigned by the Pool Manager before this method
        is invoked (see :meth:`run_assigned_scan`) — this method only runs
        the scan and releases the worker when done.
        """
        start_time = time.time()

        try:
            zap_client = self.pool_manager.get_client(worker)
            zap_api = zap_client.zap_api
            self.app_logger.info(
                f"[{worker.worker_id}] Start QUICK API scan {request.url}: {operation_id}"
            )

            zap_client.require_healthy()
            self.operation_service.start(operation_id)
            self.operation_service.report_progress(
                operation_id, stage="initializing", progress=5, worker_id=worker.worker_id
            )

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
            self.app_logger.info(f"[{worker.worker_id}] Starting spider scan: {operation_id}")
            self.operation_service.report_progress(
                operation_id, stage="spider", progress=25, worker_id=worker.worker_id
            )
            spider_id = zap_client.run_spider(url=request.url, context_name=context_name)
            zap_client.wait_for_spider(spider_id, timeout_seconds=settings.zap_spider_timeout_seconds)
            self.app_logger.info(f"[{worker.worker_id}] Spider scan done: {operation_id}")

            # Active scan — single URL, no recursion
            self.app_logger.info(f"[{worker.worker_id}] Starting active scan: {operation_id}")
            self.operation_service.report_progress(
                operation_id, stage="active scan", progress=55, worker_id=worker.worker_id
            )
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
            # No overall duration limit: an Active Scan runs as long as it stays
            # healthy (ZAP responsive + scan present + still doing work). It only
            # fails on a genuine stall or unrecoverable ZAP communication loss.
            zap_client.wait_for_active_scan(
                ascan_id,
                stall_timeout_seconds=settings.zap_scan_stall_timeout_seconds,
                unresponsive_timeout_seconds=settings.zap_scan_unresponsive_timeout_seconds,
            )
            self.app_logger.info(f"[{worker.worker_id}] Active scan done: {operation_id}")

            raw_alerts = zap_client.get_alerts(base_url=request.url)
            alerts = [self.zap_helpers.convert_raw_alert(a) for a in raw_alerts]
            zap_client.remove_context(context_name)

            self.operation_service.report_progress(
                operation_id, stage="report generation", progress=90, worker_id=worker.worker_id
            )
            view_report, export_data = self._save_reports(zap_client, operation_id)

            summary = self.zap_helpers.build_summary(alerts)
            self.operation_service.complete(
                operation_id,
                result=ZapScanResult(
                    operation_id=operation_id,
                    project_name=request.project_name,
                    status="completed",
                    target_url=request.url,
                    duration_seconds=round(time.time() - start_time, 2),
                    alerts=alerts,
                    summary=summary,
                    tls_result=self.zap_helpers.check_tls(request.url),
                    reports=ZapScanReports(view_report=view_report, export_data=export_data),
                ).model_dump(by_alias=True),
                # Forward the severity breakdown into the completed event so the
                # notification renders it — without loading/parsing the report.
                findings=self._findings_from_summary(summary),
            )

        except Exception as e:  # pylint: disable=broad-except
            self.app_logger.error(f"Error in zap_scan_worker for operation_id {operation_id}: {e}")
            self.operation_service.fail(operation_id, str(e))

        finally:
            self.pool_manager.release_worker(worker.worker_id, operation_id)

    def zap_full_scan_worker(
        self, operation_id: str, request: ZapApiScanRequest, worker: ZapWorkerInfo
    ) -> None:
        """
        FULL scan: passive scan → context-scoped active scan with body fuzzing.

        Active scan targets all injectable points including the request body
        (injectable mask = 31). No spider — the proxy-recorded request seeds the
        context directly so ZAP can fuzz the exact endpoint.

        *worker* was already assigned by the Pool Manager before this method
        is invoked (see :meth:`run_assigned_scan`) — this method only runs
        the scan and releases the worker when done.
        """
        start_time = time.time()

        try:
            zap_client = self.pool_manager.get_client(worker)
            zap_api = zap_client.zap_api
            self.app_logger.info(f"[{worker.worker_id}] Start FULL API scan {request.url}: {operation_id}")

            zap_client.require_healthy()
            self.operation_service.start(operation_id)
            self.operation_service.report_progress(
                operation_id, stage="initializing", progress=5, worker_id=worker.worker_id
            )

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
            self.app_logger.info(f"[{worker.worker_id}] Starting full active scan: {operation_id}")
            self.operation_service.report_progress(
                operation_id, stage="active scan", progress=55, worker_id=worker.worker_id
            )
            ascan_id = zap_client.run_active_scan(url=request.url, context_id=context_id, recurse=True)
            self.operation_dao.update_operation_status(
                operation_id=operation_id,
                status=OperationStatus.RUNNING,
                result={"ascan_scan_id": ascan_id, "ascan_progress": "0%"},
            )
            # No overall duration limit: an Active Scan runs as long as it stays
            # healthy (ZAP responsive + scan present + still doing work). It only
            # fails on a genuine stall or unrecoverable ZAP communication loss.
            zap_client.wait_for_active_scan(
                ascan_id,
                stall_timeout_seconds=settings.zap_scan_stall_timeout_seconds,
                unresponsive_timeout_seconds=settings.zap_scan_unresponsive_timeout_seconds,
            )
            self.app_logger.info(f"[{worker.worker_id}] Full active scan done: {operation_id}")

            raw_alerts = zap_client.get_alerts(base_url=request.url)
            alerts = [self.zap_helpers.convert_raw_alert(a) for a in raw_alerts]
            zap_client.remove_context(context_name)

            self.operation_service.report_progress(
                operation_id, stage="report generation", progress=90, worker_id=worker.worker_id
            )
            view_report, export_data = self._save_reports(zap_client, operation_id)

            summary = self.zap_helpers.build_summary(alerts)
            self.operation_service.complete(
                operation_id,
                result=ZapScanResult(
                    operation_id=operation_id,
                    project_name=request.project_name,
                    status="completed",
                    target_url=request.url,
                    duration_seconds=round(time.time() - start_time, 2),
                    alerts=alerts,
                    summary=summary,
                    tls_result=self.zap_helpers.check_tls(request.url),
                    reports=ZapScanReports(view_report=view_report, export_data=export_data),
                ).model_dump(by_alias=True),
                # Forward the severity breakdown into the completed event so the
                # notification renders it — without loading/parsing the report.
                findings=self._findings_from_summary(summary),
            )

        except Exception as e:  # pylint: disable=broad-except
            self.app_logger.error(f"Error in zap_full_scan_worker for operation_id {operation_id}: {e}")
            self.operation_service.fail(operation_id, str(e))

        finally:
            self.pool_manager.release_worker(worker.worker_id, operation_id)
