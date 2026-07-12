"""NotificationChannel port — the outbound boundary for delivering a
notification to an external channel (Slack, Discord, email, ...).

This is a cross-domain hexagonal port. Application code depends only on this
contract, never on a specific chat SDK. Each concrete adapter renders and
delivers according to *its own* capabilities, declared via
:class:`ChannelCapabilities`, so the notification layer can adapt automatically
(update-in-place vs. new-message fallback, progress vs. lifecycle-only) without
any platform-specific branching of its own.

Adding a new platform (Discord, Teams, Telegram, Email, Webhook, Web Dashboard,
...) is only "implement this port + declare capabilities" — no change to the
Notification Service, renderer, or event flow.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

# An opaque, channel-native handle to a message already delivered — what a
# subsequent update targets. For Slack it is the message ``ts``; other channels
# use whatever their update API needs. ``None`` means "no handle" (the channel
# cannot, or chose not to, return one).
MessageRef = Optional[str]


@dataclass(frozen=True, slots=True)
class ChannelCapabilities:
    """What a channel can do, so the Notification Service can adapt to it.

    Defaults are the *safest* assumption (everything unsupported): a channel
    that declares nothing is treated as append-only and lifecycle-only, so an
    under-declared adapter degrades gracefully rather than silently dropping or
    spamming messages.

    Attributes:
        supports_message_update: The channel can edit a previously sent message
            in place (e.g. Slack ``chat.update``). Enables the "one message,
            keep updating it" strategy.
        supports_threads: The channel can group messages in a thread.
        supports_buttons: The channel can render interactive buttons/actions.
        supports_progress: The channel is willing to display incremental
            progress updates. When false, progress snapshots are skipped and
            only lifecycle transitions are delivered.
    """

    supports_message_update: bool = False
    supports_threads: bool = False
    supports_buttons: bool = False
    supports_progress: bool = False


class NotificationChannel(ABC):
    """Contract for delivering an already-rendered message to one channel."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable channel identifier, e.g. ``"slack"`` or ``"discord"``."""

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Declared capabilities of this channel.

        The base implementation returns the all-unsupported default so any
        adapter that does not override it is handled conservatively. Concrete
        adapters override this to advertise what they actually support.
        """
        return ChannelCapabilities()

    @abstractmethod
    def send(self, destination: str, message: str) -> MessageRef:
        """Deliver a new message to a channel-specific destination.

        Args:
            destination: Channel-native address (e.g. a Slack channel id or a
                thread reference). Opaque to the caller.
            message: The already-rendered message body to deliver.

        Returns:
            A :data:`MessageRef` handle to the delivered message (for a later
            :meth:`update`), or ``None`` if the channel does not provide one.
        """

    def update(self, destination: str, ref: MessageRef, message: str) -> MessageRef:
        """Edit a previously delivered message in place.

        Only called by the Notification Service when
        :attr:`ChannelCapabilities.supports_message_update` is true, so the base
        implementation raises rather than silently no-op'ing — a channel that
        declares update support but does not implement this is a programming
        error, not a runtime fallback path.

        Args:
            destination: The same channel-native address the message was sent to.
            ref: The handle returned by the original :meth:`send`.
            message: The new, already-rendered message body.

        Returns:
            A :data:`MessageRef` for the (still-updatable) message.
        """
        raise NotImplementedError(
            f"channel '{self.name}' does not support message updates"
        )
