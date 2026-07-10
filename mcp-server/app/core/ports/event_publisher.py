"""EventPublisher port — the outbound boundary for emitting domain events.

This is a cross-domain hexagonal port. Application code depends on the
*contract* of publishing an event, never on a concrete transport. At MVP the
only implementation is the in-process dispatcher
(``app.core.events.dispatcher.InProcessEventDispatcher``); a durable/broker
transport can implement the same port later with no change to publishers.

The event message (:class:`DomainEvent`) is intentionally vocabulary-neutral —
it does not reference any specific domain concept (Operation, scan, ...), so any
part of the application can publish or subscribe without coupling to another
domain's model.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """An immutable record that something happened inside the application.

    Attributes:
        name: Stable event name used to route to subscribers
            (e.g. ``"operation.created"``). Vocabulary-neutral by design.
        payload: Arbitrary, read-only context for the event.
        occurred_at: UTC timestamp of when the event occurred.
    """

    name: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=_utcnow)


class EventPublisher(ABC):
    """Contract for publishing a domain event to interested subscribers."""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event.

        Args:
            event: The event to deliver to every subscriber registered for its
                name. Delivery is best-effort: an individual subscriber failure
                must not raise back to the caller.
        """
