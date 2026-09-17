"""ConversationStore — the persistence port for the Conversation bounded context.

Authority: Conversation Standard CV-1, CV-3 (event-sourced transcript).

The ConversationStore is the only component that knows the persistence backend.
All other conversation logic — state machine, redaction, replay, export —
depends on this port, never on a concrete adapter.

The store manages an append-only event-sourced transcript: every change
(message appended, state transitioned, redaction performed) is recorded as an
immutable event.  The store handles state persistence; events are emitted by
the service layer through the EventPublisher.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.intelligence.conversation.message import Message
    from app.intelligence.conversation.state import ConversationState


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """Lightweight snapshot of a conversation.

    Used for listing operations and for replay reconstruction.
    The messages list is ordered oldest-first.
    """

    conversation_id: str
    state: "ConversationState"
    messages: tuple["Message", ...]
    created_at: datetime
    updated_at: datetime


class ConversationStore(ABC):
    """Abstract persistence port for conversation transcripts.

    Implementations are the **only** place that knows the backend (PostgreSQL,
    in-memory, DynamoDB, etc.).  No other conversation code imports a specific
    adapter.

    All mutations are append-only at the event level.  The store manages event
    ordering and snapshot creation internally.
    """

    @abstractmethod
    def read(self, conversation_id: str) -> ConversationSummary | None:
        """Return the current snapshot for a conversation, or None if not found.

        Args:
            conversation_id: Unique identifier of the conversation.

        Returns:
            The latest ConversationSummary (state + ordered messages), or None
            if the conversation does not exist.
        """

    @abstractmethod
    def create(
        self,
        conversation_id: str,
        initial_state: "ConversationState | None" = None,
    ) -> ConversationSummary:
        """Create a new empty conversation.

        Args:
            conversation_id: Unique identifier for the new conversation.
            initial_state: Starting state.  Defaults to CREATED.

        Returns:
            The initial ConversationSummary.

        Raises:
            KeyError: If a conversation with this id already exists.
        """

    @abstractmethod
    def append(
        self,
        conversation_id: str,
        message: "Message",
    ) -> ConversationSummary:
        """Append a message to the transcript and return the updated snapshot.

        Args:
            conversation_id: Conversation to append to.
            message: The immutable Message to append.

        Returns:
            The updated ConversationSummary.

        Raises:
            KeyError: If the conversation does not exist.
            ConversationClosedError: If the conversation is in a terminal state.
        """

    @abstractmethod
    def transition_to(
        self,
        conversation_id: str,
        new_state: "ConversationState",
    ) -> ConversationSummary:
        """Transition a conversation to a new state and return the updated snapshot.

        The store persists the new state.  Audit event emission is the caller's
        responsibility (the service layer publishes to EventPublisher).

        Args:
            conversation_id: Conversation to transition.
            new_state: The target state.

        Returns:
            The updated ConversationSummary.

        Raises:
            KeyError: If the conversation does not exist.
            ConversationClosedError: If the conversation is in a terminal state.
            ValueError: If the transition is not permitted by the state machine.
        """

    @abstractmethod
    def list_states(
        self,
        conversation_id: str,
    ) -> list[tuple["ConversationState", datetime]]:
        """Return the full state history of a conversation, oldest-first.

        Args:
            conversation_id: Conversation to query.

        Returns:
            A list of (state, transitioned_at) tuples in chronological order.

        Raises:
            KeyError: If the conversation does not exist.
        """


# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------

class ConversationStoreError(Exception):
    """Base exception for ConversationStore failures."""


class ConversationNotFoundError(ConversationStoreError, KeyError):
    """Raised when a conversation_id is not found in the store."""


class ConversationClosedError(ConversationStoreError, ValueError):
    """Raised when an operation targets a terminal-state conversation."""
