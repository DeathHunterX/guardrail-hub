"""
ZAP base client — thin wrapper around the zaproxy Python SDK.

ZAP exposes a single port (default 8080) that serves both:
- The REST management API  →  http://zap-host:8080/JSON/...
- The HTTP/HTTPS proxy    →  configure browser / httpx to tunnel through it

Thread safety
-------------
Each ``ZapClient`` instance is safe for concurrent use from multiple threads.
The underlying ``ZAPv2`` object is created once (lazy, under a lock) and then
reused for the lifetime of the client.  All blocking ZAP SDK calls should still
be offloaded to a thread pool by the caller (use ``asyncio.to_thread`` in async
endpoints) so that the event loop is never blocked.

Multiple workers
----------------
``api_url`` is always required and always comes from a worker's *registered*
``endpoint`` (see ``app/integrations/owasp_zap/registry.py``) — never derived
from a configurable prefix. ``OwaspZapPoolManager`` creates (and caches) one
``ZapClient`` per registered worker endpoint so that parallel scans run
against independent ZAP processes.
"""
import threading
import time
import uuid
from typing import Optional

from zapv2 import ZAPv2

from app.core.config import settings
from app.core.mcp_logger import MCPLogger

logger = MCPLogger("OwaspZapClient")


class ZapNotAvailableError(Exception):
    """Raised when ZAP REST API is unreachable."""


class ZapScanHealthError(Exception):
    """Raised when an Active Scan is aborted because it is no longer healthy.

    "Unhealthy" means ZAP became unresponsive, the scan disappeared from ZAP, or
    the scan genuinely stalled (no progress and no new requests) — NOT that it
    ran for a long time. Elapsed time is never a failure. Distinct from a generic
    exception so the caller can attribute the FAILED state to scan health, and
    completely rule-agnostic.
    """


# Backward-compatibility alias: earlier code raised/handled ``ZapScanTimeoutError``
# when the (now removed) fixed overall timeout expired. The concept is gone, but
# the name is preserved so any external importer keeps working.
ZapScanTimeoutError = ZapScanHealthError


class ZapClient:
    """
    Thread-safe wrapper around ZAPv2 for a single ZAP container.

    Parameters
    ----------
    api_url:
        Full base URL of the ZAP REST API / proxy endpoint, e.g.
        ``"http://guardrail-hub-zap-1:8080"``. Always the ``endpoint`` a
        worker reported at registration — the server never generates this
        from a prefix + index. In production the ZAP container is accessed
        via the Docker-internal (or Kubernetes Service) hostname — ports are
        never exposed to the host.
    api_key:
        ZAP API key.  Defaults to ``settings.zap_api_key``.
    """

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
    ) -> None:
        if not api_url:
            raise ValueError(
                "ZapClient requires an explicit api_url (a registered worker's "
                "endpoint) — there is no prefix-derived default."
            )
        if api_key is None:
            api_key = settings.zap_api_key

        self._api_url: str = api_url
        self._api_key: str = api_key
        # Transport-level (communication) timeout applied to every ZAP HTTP call.
        # Not a scan-duration limit — it bounds each request so a hung ZAP is
        # detected by the health model instead of blocking forever.
        self._request_timeout: float = settings.zap_request_timeout_seconds

        self._zap: Optional[ZAPv2] = None
        self._zap_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @property
    def proxy_url(self) -> str:
        """Public accessor for the ZAP proxy/API base URL."""
        return self._api_url

    @property
    def zap_api(self) -> ZAPv2:
        """Return the raw ``ZAPv2`` SDK connection, creating it on first access."""
        if self._zap is None:
            with self._zap_lock:
                if self._zap is None:
                    zap = ZAPv2(
                        apikey=self._api_key,
                        proxies={
                            "http": self._api_url,
                            "https": self._api_url,
                        },
                    )
                    self._apply_request_timeout(zap)
                    self._zap = zap
        return self._zap

    def _apply_request_timeout(self, zap: ZAPv2) -> None:
        """Enforce a transport-level request timeout on every ZAP API call.

        The zaproxy SDK issues its HTTP requests without a default timeout, so a
        hung ZAP could otherwise block the health-monitoring poll loop forever.
        Injecting a default ``timeout`` on the shared ``requests`` session bounds
        each call — a communication timeout, never a scan-duration limit. Purely
        best-effort: if the SDK internals differ, ZAP calls simply keep their
        previous behaviour.
        """
        try:
            session = zap.session  # requests.Session used by the SDK
            original_request = session.request
            timeout = self._request_timeout

            def request_with_timeout(method, url, **kwargs):
                kwargs.setdefault("timeout", timeout)
                return original_request(method, url, **kwargs)

            session.request = request_with_timeout
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Could not set ZAP request timeout: %s", exc)

    def is_healthy(self) -> bool:
        """Check if the ZAP is healthy."""
        try:
            version = self.zap_api.core.version
            return bool(version)
        except Exception:
            return False

    def require_healthy(self) -> None:
        """Require the ZAP to be healthy."""
        if not self.is_healthy():
            raise ZapNotAvailableError(
                f"ZAP is not accessible at {self._api_url}. "
                "Ensure the ZAP container is running (docker compose --profile zap up)."
            )

    

    # ------------------------------------------------------------------
    # Session / Context
    # ------------------------------------------------------------------

    def new_session(self, name: Optional[str] = None) -> None:
        """Create a new ZAP session."""
        session_name = name or f"session_{uuid.uuid4().hex[:8]}"
        try:
            self.zap_api.core.new_session(name=session_name, overwrite=True)
        except Exception as exc:
            logger.warning("Could not create new ZAP session: %s", exc)

    def create_context(self, name: str) -> str:
        """Create a new ZAP context and return its ID."""
        return str(self.zap_api.context.new_context(contextname=name))

    def include_in_context(self, context_name: str, regex_pattern: str) -> None:
        """Include the given regex pattern in the given context."""
        self.zap_api.context.include_in_context(contextname=context_name, regex=regex_pattern)

    def remove_context(self, context_name: str) -> None:
        """Remove the context identified by *context_name*."""
        try:
            self.zap_api.context.remove_context(contextname=context_name)
        except Exception as exc:
            logger.debug("Could not remove context %s: %s", context_name, exc)

    # ------------------------------------------------------------------
    # Passive scan
    # ------------------------------------------------------------------

    def wait_for_passive_scan(self, timeout_seconds: int = 120) -> None:
        """Wait for the passive scan to complete."""
        start = time.time()
        while True:
            try:
                records = int(self.zap_api.pscan.records_to_scan())
                if records == 0:
                    break
            except Exception:
                break
            if time.time() - start > timeout_seconds:
                logger.warning("Passive scan timeout after %ds", timeout_seconds)
                break
            time.sleep(2)

    # ------------------------------------------------------------------
    # Spider
    # ------------------------------------------------------------------

    def run_spider(
        self,
        url: str,
        context_name: Optional[str] = None,
        recurse: bool = True,
        max_children: Optional[int] = None,
    ) -> str:
        scan_id = self.zap_api.spider.scan(
            url=url,
            maxchildren=max_children,
            recurse=recurse,
            contextname=context_name,
        )
        return str(scan_id)

    def run_spider_as_user(
        self,
        context_id: str,
        user_id: str,
        url: str,
        recurse: bool = True,
    ) -> str:
        scan_id = self.zap_api.spider.scan_as_user(
            contextid=context_id,
            userid=user_id,
            url=url,
            recurse=recurse,
        )
        return str(scan_id)

    def wait_for_spider(self, scan_id: str, timeout_seconds: int = 300) -> None:
        start = time.time()
        while True:
            try:
                progress = int(self.zap_api.spider.status(scan_id))
                if progress >= 100:
                    break
            except Exception:
                break
            if time.time() - start > timeout_seconds:
                logger.warning("Spider timed out after %ds", timeout_seconds)
                break
            time.sleep(5)

    # ------------------------------------------------------------------
    # Active scan
    # ------------------------------------------------------------------

    def run_active_scan(
        self,
        url: str,
        context_id: Optional[str] = None,
        recurse: bool = True,
        method: Optional[str] = None,
        postdata: Optional[str] = None,
    ) -> str:
        scan_id = self.zap_api.ascan.scan(
            url=url,
            recurse=recurse,
            inscopeonly=True,
            contextid=context_id,
            method=method,
            postdata=postdata,
        )
        return str(scan_id)

    def run_active_scan_as_user(
        self,
        url: str,
        context_id: str,
        user_id: str,
        recurse: bool = True,
    ) -> str:
        scan_id = self.zap_api.ascan.scan_as_user(
            url=url,
            contextid=context_id,
            userid=user_id,
            recurse=recurse,
        )
        return str(scan_id)

    def stop_active_scan(self, scan_id: str) -> None:
        """Ask ZAP to stop a running active scan using the official stop API.

        Best-effort and never raises: it is called to free the ZAP worker when a
        scan is aborted for an unhealthy condition, so a failure to stop must not
        mask the health error the caller is already handling.
        """
        try:
            self.zap_api.ascan.stop(scan_id)
        except Exception as exc:
            logger.warning("Could not stop active scan %s: %s", scan_id, exc)

    def active_scan_progress(self, scan_id: str) -> Optional[int]:
        """Return the Active Scan's completion percent (0-100).

        Returns ``None`` when ZAP responds but no longer knows this scan (it
        disappeared — e.g. cancelled or lost inside ZAP). Raises on a
        communication error, so the caller can tell "ZAP unreachable" apart from
        "scan gone".
        """
        raw = self.zap_api.ascan.status(scan_id)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def zap_message_count(self) -> Optional[int]:
        """Total messages ZAP has recorded — rises while the scan sends requests.

        Used as a liveness signal so a slow-but-active scan (whose overall
        percentage can legitimately sit still for a long time while a rule works)
        is not mistaken for a stall. Best-effort: returns ``None`` if unavailable.
        """
        try:
            return int(self.zap_api.core.number_of_messages())
        except Exception:
            return None

    def wait_for_active_scan(
        self,
        scan_id: str,
        timeout_seconds: Optional[int] = None,  # deprecated, accepted but ignored
        *,
        stall_timeout_seconds: int,
        unresponsive_timeout_seconds: int,
        poll_interval_seconds: int = 5,
    ) -> None:
        """Wait for the Active Scan to finish, letting it run as long as it stays
        HEALTHY.

        There is deliberately **no overall duration limit**: enterprise Active
        Scans — and slow rules such as timing-based SQL-injection checks — can
        legitimately run for hours, so elapsed time alone is never a failure. The
        scan is aborted (via the official ``ascan.stop`` API, then
        :class:`ZapScanHealthError`) only when it is genuinely unhealthy, and the
        logic is completely rule-agnostic:

        * **ZAP unresponsive** — ZAP's API fails to respond for
          ``unresponsive_timeout_seconds`` (sustained; transient blips are
          tolerated). This is scan-health monitoring backed by the transport
          request timeout, not a duration limit.
        * **scan disappeared** — ZAP responds but no longer knows this scan.
        * **stalled** — no progress AND no new ZAP requests for
          ``stall_timeout_seconds``; a slow-but-active scan keeps ZAP's request
          counter moving and so keeps resetting this window.

        Worker liveness (crash / lost heartbeat) is a *different* responsibility,
        handled by the heartbeat sweep in the Worker Registry — not here.

        Args:
            scan_id: The ZAP Active Scan id to monitor.
            timeout_seconds: Deprecated and ignored — the fixed overall timeout
                was removed. Kept only for backward compatibility.
            stall_timeout_seconds: Abort if the scan shows no activity at all for
                this long (stall detection).
            unresponsive_timeout_seconds: Abort if ZAP stays unreachable for this
                long (communication health).
            poll_interval_seconds: How often to poll scan health.

        Returns:
            ``None`` when the scan reaches 100%.
        """
        last_progress = -1
        last_messages = self.zap_message_count()
        last_activity_at = time.monotonic()
        last_response_at = time.monotonic()

        while True:
            now = time.monotonic()

            try:
                progress = self.active_scan_progress(scan_id)
                last_response_at = now
            except Exception as exc:
                # ZAP did not respond this tick. Tolerate transient failures and
                # give up only once ZAP has been unresponsive for the whole grace
                # window — a communication problem, never a duration limit.
                logger.debug("ZAP status probe failed for scan %s: %s", scan_id, exc)
                if now - last_response_at > unresponsive_timeout_seconds:
                    self.stop_active_scan(scan_id)
                    raise ZapScanHealthError(
                        f"ZAP stopped responding for over {unresponsive_timeout_seconds}s; "
                        "the active scan could not be monitored and was aborted."
                    ) from exc
                time.sleep(poll_interval_seconds)
                continue

            if progress is None:
                # ZAP is up but the scan is gone (cancelled/crashed inside ZAP).
                self.stop_active_scan(scan_id)
                raise ZapScanHealthError(
                    "The active scan no longer exists in ZAP (it disappeared); "
                    "the operation is marked failed."
                )

            if progress >= 100:
                return

            # Liveness: either forward progress OR ZAP still issuing requests.
            messages = self.zap_message_count()
            made_progress = progress != last_progress
            sent_requests = (
                messages is not None
                and last_messages is not None
                and messages > last_messages
            )
            if made_progress or sent_requests:
                last_activity_at = now
            last_progress = progress
            if messages is not None:
                last_messages = messages

            # Genuine stall: ZAP healthy and the scan exists, but no activity of
            # any kind for the stall window. A legitimately long scan never
            # reaches here because it keeps sending requests.
            if now - last_activity_at > stall_timeout_seconds:
                self.stop_active_scan(scan_id)
                raise ZapScanHealthError(
                    "Active scan stalled — no progress and no new requests for over "
                    f"{stall_timeout_seconds}s (at {progress}%); the scan was aborted."
                )

            time.sleep(poll_interval_seconds)

            time.sleep(poll_interval_seconds)

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def get_alerts(
        self,
        base_url: str,
        risk_id: Optional[int] = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Get the alerts for the given base URL."""
        alerts: list[dict] = []
        start = 0
        while True:
            try:
                batch = self.zap_api.alert.alerts(
                    baseurl=base_url,
                    start=start,
                    count=page_size,
                    riskid=risk_id,
                )
                if not batch:
                    break
                alerts.extend(batch)
                start += len(batch)
                if len(batch) < page_size:
                    break
            except Exception as exc:
                logger.warning("Error fetching alerts (offset=%d): %s", start, exc)
                break
        return alerts

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def setup_form_auth(
        self,
        context_id: str,
        login_url: str,
        username_param: str = "username",
        password_param: str = "password",
        extra_post_data: Optional[str] = None,
    ) -> None:
        """Set up form-based authentication for the given context."""
        post_data = f"{username_param}={{%username%}}&{password_param}={{%password%}}"
        if extra_post_data:
            post_data += f"&{extra_post_data}"
        params = f"loginUrl={login_url}&loginRequestData={post_data}"
        self.zap_api.authentication.set_authentication_method(
            contextid=context_id,
            authmethodname="formBasedAuthentication",
            authmethodconfigparams=params,
        )

    def set_login_indicator(self, context_id: str, indicator: str) -> None:
        """Set the login indicator for the given context."""
        try:
            self.zap_api.authentication.set_logged_in_indicator(
                contextid=context_id, loggedinindicatorregex=indicator
            )
        except Exception as exc:
            logger.debug("Could not set login indicator: %s", exc)

    def set_logout_indicator(self, context_id: str, indicator: str) -> None:
        """Set the logout indicator for the given context."""
        try:
            self.zap_api.authentication.set_logged_out_indicator(
                contextid=context_id, loggedoutindicatorregex=indicator
            )
        except Exception as exc:
            logger.debug("Could not set logout indicator: %s", exc)

    def create_user(self, context_id: str, username: str) -> str:
        """Create a new user for the given context."""
        user_id = self.zap_api.users.new_user(contextid=context_id, name=username)
        return str(user_id)

    def set_user_credentials(
        self, context_id: str, user_id: str, username: str, password: str
    ) -> None:
        """Set the credentials for the given user."""
        credentials = f"username={username}&password={password}"
        self.zap_api.users.set_authentication_credentials(
            contextid=context_id,
            userid=user_id,
            authcredentialsconfigparams=credentials,
        )
        self.zap_api.users.set_user_enabled(
            contextid=context_id, userid=user_id, enabled=True
        )

    def set_forced_user(self, context_id: str, user_id: str) -> None:
        """Set the forced user for the given context."""
        self.zap_api.forcedUser.set_forced_user(contextid=context_id, userid=user_id)
        self.zap_api.forcedUser.set_forced_user_mode_enabled(boolean=True)

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def html_report(self) -> str:
        """Generate an HTML report."""
        try:
            return self.zap_api.core.htmlreport()
        except Exception as exc:
            logger.warning("Could not generate HTML report: %s", exc)
            return ""

    def json_report(self) -> str:
        """Generate a JSON report."""
        try:
            return self.zap_api.core.jsonreport()
        except Exception as exc:
            logger.warning("Could not generate JSON report: %s", exc)
            return "{}"

    # ------------------------------------------------------------------
    # Recorded URLs
    # ------------------------------------------------------------------

    def get_recorded_urls(self, base_url: Optional[str] = None) -> list[str]:
        """Get the recorded URLs."""
        try:
            urls = self.zap_api.core.urls(baseurl=base_url)
            return [u for u in urls if isinstance(u, str)]
        except Exception as exc:
            logger.warning("Could not get recorded URLs: %s", exc)
            return []
