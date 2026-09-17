"""Message — the immutable unit of a conversation transcript.

Authority: Conversation Standard CV-2 (transcripts are immutable; a Message
is appended, never mutated), CV-8 (redaction preserves the original).

A Message is append-only.  Redaction is a separate audit event; the
original Message content is preserved in the event log, never overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True, slots=True)
class Message:
    """An immutable record of a single turn in a conversation.

    A Message is **append-only**.  No field is mutable after construction.
    Redaction does not mutate this record — it produces a new event that
    records the redaction action; the original Message is preserved.

    Attributes:
        role: One of ``"system"``, ``"user"``, or ``"assistant"``.
        content: The text content of the message.  May be empty for
            assistant messages that consist solely of metadata.
        timestamp: UTC time the message was received or generated.
        metadata: Arbitrary non-sensitive context attached at creation time
            (e.g. model_id, finish_reason).  May be empty.
        redacted: Whether this message's content has been redacted.
            When True, ``content`` holds the redacted replacement text.
            The original content is preserved in the audit log.
        name: Optional participant identifier for multi-party conversations.
    """

    role: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: tuple[tuple[str, Any], ...] = field(default_factory=dict)
    redacted: bool = False
    name: Optional[str] = None

    def __post_init__(self) -> None:
        # Validate role without importing an enum — the Conversation Standard
        # specifies the three values without mandating a closed enum here.
        if self.role not in ("system", "user", "assistant"):
            raise ValueError(
                f"Message.role must be 'system', 'user', or 'assistant'; "
                f"got {self.role!r}"
            )
        # frozen=True + slots=True + dataclass means we cannot assign to
        # slots after __post_init__ runs; validation-only side-effects only.
        # Only convert if a dict was passed; a tuple is already in canonical form.
        if isinstance(self.metadata, dict):
            object.__setattr__(self, "metadata", tuple(self.metadata.items()))

    @property
    def metadata_dict(self) -> dict[str, Any]:
        """Materialise metadata as a plain dict for consumers that expect one."""
        return dict(self.metadata)
