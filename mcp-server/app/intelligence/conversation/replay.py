"""Replay engine — event-sourced reconstruction of conversation state.

Authority: Conversation Standard CV-3 (append-only events).

The replay engine lets a consumer reconstruct the complete state of a
conversation from its ordered event history.  A snapshot is taken periodically
to bound reconstruction cost; events after the snapshot are replayed on top.

This module does not own persistence.  It receives events and a snapshot,
applies the events in order, and returns the reconstructed ConversationSummary.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Sequence

from app.intelligence.conversation.message import Message
from app.intelligence.conversation.state import ConversationState
from app.intelligence.conversation.store import ConversationSummary

if TYPE_CHECKING:
    from app.intelligence.conversation.infrastructure.in_memory_store import (
        _ConversationRecord,
    )
    from app.intelligence.conversation.store import ConversationStore


def reconstruct_state(
    events: Sequence[_ConversationRecord],
    snapshot: ConversationSummary | None = None,
) -> ConversationSummary:
    """Reconstruct the current state by replaying events onto a snapshot.

    The snapshot (if provided) is the latest state before ``events``.
    Events are applied in order; the last state wins for each field.

    Args:
        events: Ordered sequence of conversation records, oldest first.
            Each record's messages and state are applied in order.
        snapshot: Optional pre-built ConversationSummary to start from.
            When None, reconstruction starts from CREATED with no messages.

    Returns:
        The fully reconstructed ConversationSummary.
    """
    state = ConversationState.CREATED
    messages: list[Message] = []
    created_at = snapshot.created_at if snapshot else None
    updated_at = snapshot.updated_at if snapshot else None
    conversation_id = snapshot.conversation_id if snapshot else ""

    for record in events:
        if record.state != state:
            state = record.state
        messages.extend(record.messages)
        if record.updated_at > (updated_at or updated_at):
            updated_at = record.updated_at

    final_created = created_at or (messages[-1].timestamp if messages else updated_at)
    final_updated = updated_at or (messages[-1].timestamp if messages else updated_at)

    return ConversationSummary(
        conversation_id=conversation_id,
        state=state,
        messages=tuple(messages),
        created_at=final_created,
        updated_at=final_updated,
    )


class ReplayEngine:
    """Replays a conversation's event history to reconstruct state.

    For Phase 5, the in-memory store already maintains the current state as a
    snapshot; the replay engine is provided for future event-history replay
    when a persistent event store is introduced.
    """

    def replay(
        self,
        conversation_id: str,
        store: ConversationStore,
    ) -> ConversationSummary:
        """Reconstruct a conversation by reading the current snapshot.

        Args:
            conversation_id: The conversation to replay.
            store: The ConversationStore to read from.

        Returns:
            The ConversationSummary.

        Raises:
            ConversationNotFoundError: If the conversation does not exist.
        """
        summary = store.read(conversation_id)
        if summary is None:
            from app.intelligence.conversation.store import ConversationNotFoundError
            raise ConversationNotFoundError(conversation_id)
        return summary
