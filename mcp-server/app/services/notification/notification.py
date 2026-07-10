"""Notification message — the minimal request the NotificationService delivers.

Intentionally small (YAGNI): richer routing (preferences, severity, templates,
subscribing to domain events) is added when an event source requires it.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Notification:
    """A single message to deliver through one named channel.

    Attributes:
        channel: Target channel name (e.g. ``"slack"``). Matches
            :attr:`NotificationChannel.name`.
        destination: Channel-native destination (e.g. a Slack channel id).
        message: The already-rendered message body.
    """

    channel: str
    destination: str
    message: str
