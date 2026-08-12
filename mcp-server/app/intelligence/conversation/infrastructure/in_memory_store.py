"""In-memory ConversationStore adapter — for testing and as a reference implementation.

Authority: Conversation Standard CV-3 (append-only events), CV-2 (immutable messages).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.intelligence.conversation.machine import can_transition_to
from app.intelligence.conversation.message import Message
from app.intelligence.conversation.state import ConversationState
from app.intelligence.conversation.store import (
    ConversationClosedError,
    ConversationNotFoundError,
    ConversationStore,
    ConversationSummary,
)


@dataclass
class _ConversationRecord:
    state: ConversationState = ConversationState.CREATED
    messages: list[Message] = field(default_factory=list)
    state_history: list[tuple[ConversationState, datetime]] = field(
        default_factory=lambda: [(ConversationState.CREATED, datetime.now(timezone.utc))]
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InMemoryConversationStore(ConversationStore):
    """Thread-unsafe in-memory store; use only for testing."""

    def __init__(self) -> None:
        self._conversations: dict[str, _ConversationRecord] = {}

    def read(self, conversation_id: str) -> ConversationSummary | None:
        rec = self._conversations.get(conversation_id)
        if rec is None:
            return None
        return ConversationSummary(
            conversation_id=conversation_id,
            state=rec.state,
            messages=tuple(rec.messages),
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )

    def create(
        self,
        conversation_id: str,
        initial_state: ConversationState | None = None,
    ) -> ConversationSummary:
        if conversation_id in self._conversations:
            raise KeyError(f"conversation {conversation_id!r} already exists")
        state = initial_state or ConversationState.CREATED
        now = datetime.now(timezone.utc)
        rec = _ConversationRecord(
            state=state,
            state_history=[(state, now)],
            created_at=now,
            updated_at=now,
        )
        self._conversations[conversation_id] = rec
        return ConversationSummary(
            conversation_id=conversation_id,
            state=state,
            messages=(),
            created_at=now,
            updated_at=now,
        )

    def append(
        self,
        conversation_id: str,
        message: Message,
    ) -> ConversationSummary:
        rec = self._conversations.get(conversation_id)
        if rec is None:
            raise ConversationNotFoundError(conversation_id)
        if rec.state.is_terminal:
            raise ConversationClosedError(
                f"conversation {conversation_id!r} is in terminal state "
                f"{rec.state.value!r}; no messages may be appended"
            )
        rec.messages.append(message)
        now = datetime.now(timezone.utc)
        rec.updated_at = now
        return ConversationSummary(
            conversation_id=conversation_id,
            state=rec.state,
            messages=tuple(rec.messages),
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )

    def transition_to(
        self,
        conversation_id: str,
        new_state: ConversationState,
    ) -> ConversationSummary:
        rec = self._conversations.get(conversation_id)
        if rec is None:
            raise ConversationNotFoundError(conversation_id)
        # Cannot transition from a terminal state.
        if rec.state.is_terminal:
            raise ConversationClosedError(
                f"conversation {conversation_id!r} is in terminal state "
                f"{rec.state.value!r}; cannot transition"
            )
        # The state machine determines if this specific transition is valid.
        if not can_transition_to(rec.state, new_state):
            raise ValueError(
                f"invalid transition: {rec.state.value!r} -> {new_state.value!r}"
            )
        now = datetime.now(timezone.utc)
        rec.state = new_state
        rec.state_history.append((new_state, now))
        rec.updated_at = now
        return ConversationSummary(
            conversation_id=conversation_id,
            state=rec.state,
            messages=tuple(rec.messages),
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )

    def list_states(
        self,
        conversation_id: str,
    ) -> list[tuple[ConversationState, datetime]]:
        rec = self._conversations.get(conversation_id)
        if rec is None:
            raise ConversationNotFoundError(conversation_id)
        return list(rec.state_history)
