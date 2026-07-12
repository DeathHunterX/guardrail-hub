"""Slack implementation of the NotificationChannel port.

Delivers a message to a Slack channel via the Web API (``chat.postMessage``) and
edits it in place via ``chat.update``. The HTTP transport is injectable, so the
adapter is unit-testable without network access; the default transport uses the
Python standard library (``urllib``), so no new dependency is introduced.

Slack supports editing a posted message, threads, interactive buttons, and
incremental progress, so it declares all four capabilities. The notification
layer reads those to drive the "one message, keep updating it" strategy.
"""

import json
import re
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

from app.core.ports.notification_channel import (
    ChannelCapabilities,
    MessageRef,
    NotificationChannel,
)


class SlackDeliveryError(RuntimeError):
    """Raised when Slack reports the message was not delivered."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Minimal HTTP response the transport returns to the adapter."""

    status: int
    body: str


# A transport performs one HTTP POST and returns an HttpResponse.
Transport = Callable[[str, Mapping[str, str], bytes], HttpResponse]


def _urllib_transport(url: str, headers: Mapping[str, str], body: bytes) -> HttpResponse:
    """Default transport: POST via the standard library (no third-party deps)."""
    request = urllib.request.Request(
        url, data=body, headers=dict(headers), method="POST"
    )
    # nosec B310 - url is the fixed, https-only Slack API endpoint below
    with urllib.request.urlopen(request, timeout=10) as response:
        return HttpResponse(
            status=response.status, body=response.read().decode("utf-8")
        )


class SlackNotificationChannel(NotificationChannel):
    """Deliver notifications to Slack via ``chat.postMessage`` / ``chat.update``."""

    API_URL = "https://slack.com/api/chat.postMessage"
    UPDATE_URL = "https://slack.com/api/chat.update"

    def __init__(self, token: str, transport: Optional[Transport] = None) -> None:
        """
        Args:
            token: Slack bot token used to authenticate the Web API call.
            transport: HTTP transport that performs the POST. Defaults to a
                standard-library implementation; inject a fake in tests.
        """
        self._token = token
        self._transport = transport or _urllib_transport

    @property
    def name(self) -> str:
        return "slack"

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            supports_message_update=True,
            supports_threads=True,
            supports_buttons=True,
            supports_progress=True,
        )

    def send(self, destination: str, message: str) -> MessageRef:
        """Post *message* to the Slack channel *destination*.

        Args:
            destination: The Slack channel id to post to.
            message: The already-rendered message body.

        Returns:
            The Slack message ``ts`` (a :data:`MessageRef` a later
            :meth:`update` targets), or ``None`` if Slack did not return one.

        Raises:
            SlackDeliveryError: If the transport returns a non-200 status or
                Slack reports ``ok = false``.
        """
        payload = self._post(
            self.API_URL,
            {
                "channel": destination,
                "text": message,  # plain-text fallback (notifications, a11y)
                "blocks": self._build_blocks(message),
            },
        )
        return payload.get("ts")

    def update(self, destination: str, ref: MessageRef, message: str) -> MessageRef:
        """Edit the message identified by *ref* in the channel *destination*.

        Falls back to posting a new message when *ref* is missing (nothing to
        edit), so a lost handle never drops the update entirely.

        Args:
            destination: The Slack channel id the message lives in.
            ref: The Slack ``ts`` returned by the original :meth:`send`.
            message: The new, already-rendered message body.

        Returns:
            The message ``ts`` (unchanged for an edit), for any further update.

        Raises:
            SlackDeliveryError: If the transport returns a non-200 status or
                Slack reports ``ok = false``.
        """
        if not ref:
            return self.send(destination, message)
        payload = self._post(
            self.UPDATE_URL,
            {
                "channel": destination,
                "ts": ref,
                "text": message,  # plain-text fallback (notifications, a11y)
                "blocks": self._build_blocks(message),
            },
        )
        return payload.get("ts", ref)

    # Product brand shown as a small context line at the top of rich cards.
    BRAND = "🛡️ Guardrail Hub"

    # Severity rows for the completed-scan findings section, in display order:
    # (emoji, label, key in the parsed counts).
    _SEVERITIES = (
        ("🔴", "Critical", "critical"),
        ("🟠", "High", "high"),
        ("🟡", "Medium", "medium"),
        ("🟢", "Low", "low"),
        ("🔵", "Informational", "informational"),
    )

    @classmethod
    def _build_blocks(cls, message: str) -> list:
        """Turn the transport-neutral card text into Slack Block Kit.

        Slack-specific presentation lives *only* here — never in the renderer or
        domain layer. A completed-scan card is rebuilt as a polished product
        card (brand context, header, one section per topic, dividers between
        them, a per-severity findings list and a get-result footer). Every other
        card keeps the compact generic layout. Both are derived purely from the
        neutral text, so nothing Slack-specific leaks upstream and other
        transports are unaffected.
        """
        if "get-result" in message and "Operation ID:" in message:
            completed = cls._completed_scan_blocks(message)
            if completed:
                return completed
        return cls._generic_blocks(message)

    @staticmethod
    def _generic_blocks(message: str) -> list:
        """Compact fallback layout: bold title, divider, body as one section."""
        title, _, body = message.partition("\n")
        blocks: list = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{title.strip()}*"}}
        ]
        body = body.strip("\n")
        if body:
            # Monospace the operation id for easy copy/paste.
            body = re.sub(r"(?m)^Operation ID:\s*(\S+)$", r"Operation ID: `\1`", body)
            blocks.append({"type": "divider"})
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body}})
        return blocks

    @classmethod
    def _completed_scan_blocks(cls, message: str):
        """Build the rich completed-scan card from the neutral text's fields.

        Returns ``None`` if the expected fields are missing, so the caller can
        fall back to the generic layout instead of emitting a broken card.
        """
        title = message.splitlines()[0].strip() if message else ""
        target = cls._field(message, "Target")
        duration = cls._field(message, "Duration")
        report = cls._field(message, "Report")
        op_id = cls._field(message, "Operation ID")
        counts = cls._parse_findings(message)
        if not op_id or counts is None:
            return None

        # Header already states completion, so no "Status: Completed" row.
        blocks: list = [
            {"type": "context", "elements": [{"type": "mrkdwn", "text": cls.BRAND}]},
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{title} Completed", "emoji": True},
            },
        ]
        if target:
            blocks += [
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"🎯 *Target*\n{target}"}},
            ]
        blocks += [
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": cls._findings_section(counts)}},
        ]
        if duration:
            blocks += [
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"⏱ *Duration*\n{duration}"}},
            ]
        if report:
            # Native Slack link — renders as a clickable "View Report".
            blocks += [
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"📄 *Report*\n<{report}|View Report>"}},
            ]
        blocks += [
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"🆔 *Operation ID*\n`{op_id}`"}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Use this Operation ID with `get-result` to retrieve the complete scan report.",
                    }
                ],
            },
        ]
        return blocks

    @classmethod
    def _findings_section(cls, counts: dict) -> str:
        """One mrkdwn section: each severity on its own line, then the total."""
        rows = [f"{icon} {label}  `{counts[key]}`" for icon, label, key in cls._SEVERITIES]
        total = sum(counts[key] for _, _, key in cls._SEVERITIES)
        rows.append(f"*Total Findings*  `{total}`")
        return "📊 *Findings*\n" + "\n".join(rows)

    @staticmethod
    def _field(message: str, label: str):
        """Extract the value of a ``Label: value`` line from the neutral card."""
        match = re.search(rf"(?m)^{re.escape(label)}:[ \t]*(.+?)\s*$", message)
        return match.group(1).strip() if match else None

    @staticmethod
    def _parse_findings(message: str):
        """Parse the neutral one-line severity breakdown into a counts dict."""
        match = re.search(
            r"Critical\s+(\d+)\s*·\s*High\s+(\d+)\s*·\s*Medium\s+(\d+)\s*·\s*"
            r"Low\s+(\d+)\s*·\s*Info\w*\s+(\d+)",
            message,
        )
        if match:
            return {
                "critical": int(match.group(1)),
                "high": int(match.group(2)),
                "medium": int(match.group(3)),
                "low": int(match.group(4)),
                "informational": int(match.group(5)),
            }
        if "No vulnerabilities found" in message:
            return {"critical": 0, "high": 0, "medium": 0, "low": 0, "informational": 0}
        return None

    def _post(self, url: str, request_body: dict) -> dict:
        """POST *request_body* to *url* and return Slack's parsed JSON payload.

        Raises:
            SlackDeliveryError: On a non-200 status or a Slack ``ok = false``.
        """
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        body = json.dumps(request_body).encode("utf-8")

        response = self._transport(url, headers, body)
        if response.status != 200:
            raise SlackDeliveryError(f"Slack HTTP {response.status}")

        payload = json.loads(response.body or "{}")
        if not payload.get("ok", False):
            raise SlackDeliveryError(payload.get("error", "unknown_error"))
        return payload
