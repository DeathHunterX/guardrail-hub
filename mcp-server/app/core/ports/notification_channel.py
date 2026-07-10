"""NotificationChannel port — the outbound boundary for delivering a
notification to an external channel (Slack, Discord, email, ...).

This is a cross-domain hexagonal port. No channel implementation exists yet;
concrete adapters are introduced with their vertical slice. The port is defined
now so that, when the Notification application service is built, it depends only
on this contract and never on a specific chat SDK.
"""

from abc import ABC, abstractmethod


class NotificationChannel(ABC):
    """Contract for delivering an already-rendered message to one channel."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable channel identifier, e.g. ``"slack"`` or ``"discord"``."""

    @abstractmethod
    def send(self, destination: str, message: str) -> None:
        """Deliver a message to a channel-specific destination.

        Args:
            destination: Channel-native address (e.g. a Slack channel id or a
                thread reference). Opaque to the caller.
            message: The already-rendered message body to deliver.
        """
