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
                    self._zap = ZAPv2(
                        apikey=self._api_key,
                        proxies={
                            "http": self._api_url,
                            "https": self._api_url,
                        },
                    )
        return self._zap

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

    def wait_for_active_scan(self, scan_id: str, timeout_seconds: int = 600) -> None:
        start = time.time()
        while True:
            try:
                progress = int(self.zap_api.ascan.status(scan_id))
                if progress >= 100:
                    break
            except Exception:
                break
            if time.time() - start > timeout_seconds:
                logger.warning("Active scan timed out after %ds", timeout_seconds)
                break
            time.sleep(5)

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
