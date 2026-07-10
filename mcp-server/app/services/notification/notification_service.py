"""Notification application service.

Decides *which channel* handles a notification and delegates actual delivery to
that channel's adapter. It owns routing, not delivery: it must never contain a
Slack/Discord SDK call. Richer decisioning (preferences, severity, templates,
subscribing to domain events) is added when an event source requires it (YAGNI).
"""

from typing import Iterable

from app.core.ports.notification_channel import NotificationChannel
from app.services.notification.notification import Notification


class UnknownChannelError(LookupError):
    """Raised when a notification targets a channel that is not registered."""


class NotificationService:
    """Routes a notification to a registered channel and delegates delivery."""

    def __init__(self, channels: Iterable[NotificationChannel]) -> None:
        """
        Args:
            channels: The delivery channels this service can route to. Each is
                keyed by its :attr:`NotificationChannel.name`.
        """
        self._channels: dict[str, NotificationChannel] = {c.name: c for c in channels}

    @property
    def channels(self) -> tuple[str, ...]:
        """Names of the registered channels."""
        return tuple(self._channels)

    def notify(self, notification: Notification) -> None:
        """Deliver *notification* through its target channel.

        Args:
            notification: The message to deliver.

        Raises:
            UnknownChannelError: If no registered channel matches
                ``notification.channel``.
            Exception: Any delivery error raised by the channel adapter
                propagates to the caller.
        """
        channel = self._channels.get(notification.channel)
        if channel is None:
            raise UnknownChannelError(notification.channel)
        channel.send(notification.destination, notification.message)
