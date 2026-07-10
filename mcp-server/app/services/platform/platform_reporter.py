"""PlatformReporter — operational visibility for Guardrail Hub.

Infrastructure feature (not a business domain). It fans a *platform lifecycle*
event out to two targets:

    platform event
        ├──> logger                (always — source of truth, unchanged)
        └──> NotificationService   (optional — human-facing, best-effort)

The bot speaks as the platform to an administrator, in lifecycle terms
(starting / ready / shutting down / stopped), not in server-internal events.
Every bot message uses one consistent layout and stays concise (no config dumps,
no stack traces, no internal IDs). Logging behaviour is unchanged — only the
human-facing messages are formatted.

Notifications are best-effort: if disabled, unavailable, or delivery raises,
logging continues and the platform keeps running.
"""

from typing import Any, Iterable, Optional

from app.services.notification.notification import Notification
from app.services.notification.notification_service import NotificationService

SLACK_CHANNEL_NAME = "slack"

_HEADER = "🛡️ Guardrail Hub"
_DIVIDER = "━" * 12
_SERVER = "mcp-server"


class PlatformReporter:
    """Decides when to log and when to notify for platform lifecycle events."""

    def __init__(
        self,
        logger: Any,
        notification_service: Optional[NotificationService] = None,
        destination: Optional[str] = None,
        channel: str = SLACK_CHANNEL_NAME,
    ) -> None:
        self._log = logger
        self._notifications = notification_service
        self._destination = destination
        self._channel = channel

    # ------------------------------------------------------------------
    # Lifecycle events (log + bot)
    # ------------------------------------------------------------------

    def starting(self, environment: str, version: str) -> None:
        self._emit(
            "Platform starting",
            {"event": "starting", "environment": environment, "version": version},
            self._render(
                "🚀 Guardrail Hub Starting",
                [("Environment", self._env(environment)), ("Version", self._ver(version))],
                footer=[("Status", "Starting")],
            ),
        )

    def ready(
        self,
        environment: str,
        version: str,
        server: str = _SERVER,
        integrations=None,
        status: str = "Healthy",
    ) -> None:
        """The single aggregated startup summary (env, version, server, integrations, health)."""
        self._emit(
            "Platform ready",
            {
                "event": "ready",
                "environment": environment,
                "version": version,
                "server": server,
                "status": status,
            },
            self._render(
                "✅ Platform Ready",
                [
                    ("Environment", self._env(environment)),
                    ("Version", self._ver(version)),
                    ("Server", server),
                ],
                integrations=integrations,
                footer=[("Status", status)],
            ),
        )

    def slack_connected(
        self,
        workspace: Optional[str],
        channel: Optional[str],
        environment: str,
        notifications: str = "Enabled",
    ) -> None:
        self._emit(
            "Slack connected",
            {"event": "slack_connected", "workspace": workspace, "channel": channel, "environment": environment},
            self._render(
                "🤖 Slack Connected",
                [
                    ("Workspace", workspace or "Unknown"),
                    ("Channel", channel or "Unknown"),
                    ("Environment", self._env(environment)),
                ],
                footer=[("Notifications", notifications)],
            ),
        )

    def slack_disconnected(self, reason: str) -> None:
        self._emit(
            "Slack disconnected",
            {"event": "slack_disconnected", "reason": reason},
            self._render(
                "🔌 Slack Disconnected",
                [("Reason", reason or "Unknown")],
                footer=[("Notifications", "Unavailable")],
            ),
            level="warning",
        )

    def shutting_down(self, reason: str = "Manual shutdown") -> None:
        self._emit(
            "Platform shutting down",
            {"event": "shutting_down", "reason": reason},
            self._render(
                "🛑 Platform Stopping",
                [("Reason", reason)],
                footer=[("Status", "Stopping")],
            ),
        )

    def stopped(self, reason: str) -> None:
        """Fatal/unrecoverable stop — the platform is going down unexpectedly."""
        self._emit(
            "Platform stopped",
            {"event": "stopped", "reason": reason},
            self._render(
                "❌ Guardrail Hub Stopped",
                [("Reason", reason)],
                footer=[("Status", "Unavailable")],
            ),
            level="error",
        )

    def configuration_error(self, missing: Iterable[str]) -> None:
        items = list(missing)
        self._emit(
            "Configuration error",
            {"event": "configuration_error", "missing": items},
            self._render(
                "❌ Configuration Error",
                [("Missing", ", ".join(items) if items else "Unknown")],
                footer=[("Status", "Unavailable")],
            ),
            level="error",
        )

    # ------------------------------------------------------------------
    # Log-only events (unchanged behaviour; never sent to the bot)
    # ------------------------------------------------------------------

    def configuration_loaded(
        self,
        environment: str,
        database_provider: str,
        notification_provider: str,
        log_level: str,
    ) -> None:
        self._log_only(
            "Configuration loaded",
            {
                "event": "configuration_loaded",
                "environment": environment,
                "database_provider": database_provider,
                "notification_provider": notification_provider,
                "log_level": log_level,
            },
        )

    def mcp_tools_registered(self, tools: Iterable[str]) -> None:
        items = list(tools)
        self._log_only(
            f"Registered MCP tools ({len(items)})",
            {"event": "mcp_tools_registered", "tools": items, "total": len(items)},
        )

    def platform_summary(self, **summary: Any) -> None:
        self._log_only("Platform summary", {"event": "platform_summary", **summary})

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _env(value: Any) -> str:
        return str(value).capitalize() if value else "Unknown"

    @staticmethod
    def _ver(value: Any) -> str:
        text = str(value)
        return text if text.startswith("v") else f"v{text}"

    def _render(self, title: str, fields, integrations=None, footer=None) -> str:
        lines = [_HEADER, _DIVIDER, title]
        if fields:
            width = max(len(label) for label, _ in fields)
            for label, value in fields:
                lines.append(f"{label.ljust(width)} : {value}")
        if integrations:
            lines.append("Integrations:")
            for label, value in integrations:
                lines.append(f"{label} : {value}")
        lines.append(_DIVIDER)
        if footer:
            for label, value in footer:
                lines.append(f"{label} : {value}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals (unchanged: log always, notify best-effort)
    # ------------------------------------------------------------------

    def _emit(self, message: str, extra: dict, bot_message: str, level: str = "info") -> None:
        self._write_log(level, message, extra)
        self._notify(bot_message)

    def _log_only(self, message: str, extra: dict, level: str = "info") -> None:
        self._write_log(level, message, extra)

    def _write_log(self, level: str, message: str, extra: dict) -> None:
        log_fn = getattr(self._log, level, None) or getattr(self._log, "info")
        try:
            log_fn(message, extra=extra)
        except TypeError:
            log_fn(message)

    def _notify(self, message: str) -> None:
        if self._notifications is None or self._destination is None:
            return
        try:
            self._notifications.notify(
                Notification(channel=self._channel, destination=self._destination, message=message)
            )
        except Exception as exc:  # noqa: BLE001 - notifications must never crash the platform
            try:
                self._write_log(
                    "error",
                    "Platform notification delivery failed",
                    {"event": "notification_failed", "reason": str(exc)},
                )
            except Exception:  # pragma: no cover
                pass
