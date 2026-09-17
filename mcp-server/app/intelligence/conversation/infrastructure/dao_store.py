"""PostgreSQL adapter for ConversationStore.

Authority: Conversation Standard CV-3 (event-sourced transcript).

This adapter implements the ConversationStore port using a PostgreSQL backend.
The schema uses a single ``conversations`` table with JSONB columns for the
message list and state history, enabling append-only event replay without a
separate event log table at Phase 5.

The conversation event log (CV-7) is stored alongside the snapshot in the
same JSONB ``messages`` column — each append records the full Message object.
A separate ``state_history`` column tracks state transitions with timestamps.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.dao.postgres.postgres_dao import PostgresDAO
from app.intelligence.conversation.message import Message
from app.intelligence.conversation.state import ConversationState
from app.intelligence.conversation.store import (
    ConversationClosedError,
    ConversationNotFoundError,
    ConversationStore,
    ConversationSummary,
)


class PostgresConversationStore(PostgresDAO, ConversationStore):
    """PostgreSQL-backed ConversationStore.

    The ``conversations`` table must exist.  Run migration
    ``0003_create_conversations_table.sql`` (in ``app/dao/postgres/migrations/``)
    to create it.
    """

    def __init__(self) -> None:
        PostgresDAO.__init__(self)

    # ── ConversationStore implementation ───────────────────────────────────────

    def read(self, conversation_id: str) -> ConversationSummary | None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT current_state, messages, state_history, created_at, updated_at "
                    "FROM conversations WHERE conversation_id = %(id)s",
                    {"id": conversation_id},
                )
                row = cur.fetchone()
                if row is None:
                    return None
                state_str, messages_json, state_history_json, created_at, updated_at = row
                return ConversationSummary(
                    conversation_id=conversation_id,
                    state=ConversationState(state_str),
                    messages=tuple(self._deserialize_messages(messages_json or [])),
                    created_at=created_at,
                    updated_at=updated_at,
                )
        finally:
            conn.close()

    def create(
        self,
        conversation_id: str,
        initial_state: ConversationState | None = None,
    ) -> ConversationSummary:
        state = initial_state or ConversationState.CREATED
        now = datetime.now(timezone.utc)
        initial_history = [{"state": state.value, "at": now.isoformat()}]
        conn = self._connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO conversations "
                        "(conversation_id, current_state, messages, state_history, created_at, updated_at) "
                        "VALUES (%(id)s, %(state)s, %(messages)s, %(history)s, %(created)s, %(updated)s)",
                        {
                            "id": conversation_id,
                            "state": state.value,
                            "messages": "[]",
                            "history": json.dumps(initial_history),
                            "created": now,
                            "updated": now,
                        },
                    )
                    return ConversationSummary(
                        conversation_id=conversation_id,
                        state=state,
                        messages=(),
                        created_at=now,
                        updated_at=now,
                    )
        finally:
            conn.close()

    def append(
        self,
        conversation_id: str,
        message: Message,
    ) -> ConversationSummary:
        conn = self._connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    # Lock the row for update to prevent concurrent append races.
                    cur.execute(
                        "SELECT current_state, messages, state_history, created_at, updated_at "
                        "FROM conversations WHERE conversation_id = %(id)s FOR UPDATE",
                        {"id": conversation_id},
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise ConversationNotFoundError(conversation_id)

                    current_state_str, messages_json, state_history_json, created_at, updated_at = row
                    current_state = ConversationState(current_state_str)

                    if current_state.is_terminal:
                        raise ConversationClosedError(
                            f"conversation {conversation_id!r} is in terminal state "
                            f"{current_state.value!r}; no messages may be appended"
                        )

                    messages = self._deserialize_messages(messages_json or [])
                    messages.append(message)
                    now = datetime.now(timezone.utc)

                    cur.execute(
                        "UPDATE conversations "
                        "SET messages=%(messages)s, updated_at=%(updated_at)s "
                        "WHERE conversation_id=%(id)s",
                        {
                            "id": conversation_id,
                            "messages": json.dumps([self._serialize_message(m) for m in messages]),
                            "updated_at": now,
                        },
                    )

                    return ConversationSummary(
                        conversation_id=conversation_id,
                        state=current_state,
                        messages=tuple(messages),
                        created_at=created_at,
                        updated_at=now,
                    )
        finally:
            conn.close()

    def transition_to(
        self,
        conversation_id: str,
        new_state: ConversationState,
    ) -> ConversationSummary:
        conn = self._connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT current_state, messages, state_history, created_at, updated_at "
                        "FROM conversations WHERE conversation_id = %(id)s FOR UPDATE",
                        {"id": conversation_id},
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise ConversationNotFoundError(conversation_id)

                    current_state_str, messages_json, state_history_json, created_at, updated_at = row
                    current_state = ConversationState(current_state_str)

                    if current_state.is_terminal:
                        raise ConversationClosedError(
                            f"conversation {conversation_id!r} is in terminal state "
                            f"{current_state.value!r}; cannot transition"
                        )

                    now = datetime.now(timezone.utc)
                    history = state_history_json or []
                    history.append({"state": new_state.value, "at": now.isoformat()})

                    cur.execute(
                        "UPDATE conversations "
                        "SET current_state=%(state)s, state_history=%(history)s, updated_at=%(updated_at)s "
                        "WHERE conversation_id=%(id)s",
                        {
                            "id": conversation_id,
                            "state": new_state.value,
                            "history": json.dumps(history),
                            "updated_at": now,
                        },
                    )

                    return ConversationSummary(
                        conversation_id=conversation_id,
                        state=new_state,
                        messages=tuple(self._deserialize_messages(messages_json or [])),
                        created_at=created_at,
                        updated_at=now,
                    )
        finally:
            conn.close()

    def list_states(
        self,
        conversation_id: str,
    ) -> list[tuple[ConversationState, datetime]]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT state_history FROM conversations WHERE conversation_id = %(id)s",
                    {"id": conversation_id},
                )
                row = cur.fetchone()
                if row is None:
                    raise ConversationNotFoundError(conversation_id)
                history_json = row[0] or []
                return [
                    (
                        ConversationState(entry["state"]),
                        datetime.fromisoformat(entry["at"]),
                    )
                    for entry in history_json
                ]
        finally:
            conn.close()

    # ── Serialisation helpers ─────────────────────────────────────────────────

    @staticmethod
    def _serialize_message(msg: Message) -> dict[str, Any]:
        """Serialise a Message to a plain dict for JSONB storage."""
        return {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "metadata": dict(msg.metadata),
            "redacted": msg.redacted,
            "name": msg.name,
        }

    @staticmethod
    def _deserialize_messages(raw: Any) -> list[Message]:
        """Deserialise a list of raw dicts back to Message objects."""
        if not raw:
            return []
        messages: list[Message] = []
        for obj in raw:
            messages.append(
                Message(
                    role=str(obj["role"]),
                    content=str(obj.get("content", "")),
                    timestamp=datetime.fromisoformat(obj["timestamp"]),
                    metadata=tuple(obj.get("metadata", {}).items()),
                    redacted=bool(obj.get("redacted", False)),
                    name=obj.get("name"),
                )
            )
        return messages
