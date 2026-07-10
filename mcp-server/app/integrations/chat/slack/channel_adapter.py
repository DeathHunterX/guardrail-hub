"""Slack implementation of the NotificationChannel port.

Delivers a message to a Slack channel via the Web API (``chat.postMessage``).
The HTTP transport is injectable, so the adapter is unit-testable without
network access; the default transport uses the Python standard library
(``urllib``), so no new dependency is introduced.
"""

import json
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

from app.core.ports.notification_channel import NotificationChannel


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
    """Deliver notifications to Slack via ``chat.postMessage``."""

    API_URL = "https://slack.com/api/chat.postMessage"

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

    def send(self, destination: str, message: str) -> None:
        """Post *message* to the Slack channel *destination*.

        Args:
            destination: The Slack channel id to post to.
            message: The already-rendered message body.

        Raises:
            SlackDeliveryError: If the transport returns a non-200 status or
                Slack reports ``ok = false``.
        """
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        body = json.dumps({"channel": destination, "text": message}).encode("utf-8")

        response = self._transport(self.API_URL, headers, body)
        if response.status != 200:
            raise SlackDeliveryError(f"Slack HTTP {response.status}")

        payload = json.loads(response.body or "{}")
        if not payload.get("ok", False):
            raise SlackDeliveryError(payload.get("error", "unknown_error"))
