"""Typed conversation event contracts.

Authority: Conversation Standard CV-5 (state transitions are explicit), CV-7
(audit is mandatory), CV-8 (redaction preserves the original in audit).

These contracts extend the platform's audit ledger.  Every conversation
operation produces one of these events, which the platform's
:class:`~app.core.ports.event_publisher.EventPublisher` dispatches to
subscribers.  The contracts follow the same frozen-dataclass pattern as
:mod:`app.core.events.contracts`.

The Conversation context owns these contracts; the EventPublisher port is
imported from ``core/`` so the conversation context can publish through the
same transport as the rest of the platform without owning the transport.
"""

from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.ports.event_publisher import DomainEvent
from app.intelligence.conversation.state import ConversationState


@dataclass(frozen=True)
class ConversationEvent(DomainEvent):
    """Base for every conversation event."""

    name: ClassVar[str] = "conversation.event"
    conversation_id: str = ""


@dataclass(frozen=True)
class ConversationCreated(ConversationEvent):
    """A new conversation was created (initially CREATED)."""

    name: ClassVar[str] = "conversation.created"
    initial_state: ConversationState = ConversationState.CREATED


@dataclass(frozen=True)
class StateTransitioned(ConversationEvent):
    """A conversation transitioned from one state to another."""

    name: ClassVar[str] = "conversation.state_transitioned"
    from_state: ConversationState = ConversationState.CREATED
    to_state: ConversationState = ConversationState.OPEN


@dataclass(frozen=True)
class MessageAppended(ConversationEvent):
    """A message was appended to the transcript."""

    name: ClassVar[str] = "conversation.message_appended"
    message_index: int = 0
    role: str = ""
    # content is deliberately absent: a platform audit log must not accumulate
    # raw PII in event records.  The original message is preserved in the
    # conversation store; this event records the metadata (index, role, timestamp)
    # needed for replay without copying content.
    redacted: bool = False


@dataclass(frozen=True)
class RedactionPerformed(ConversationEvent):
    """A message was redacted within a conversation.

    CV-8 authority: ``original_content`` carries the pre-redaction content into
    the audit mechanism so that a full audit trail exists independently of the
    conversation store.  The conversation store also retains the original
    Message at its index; neither copy is modified.
    """

    name: ClassVar[str] = "conversation.redaction_performed"
    message_index: int = 0
    redaction_policy: str = ""
    # Original content carried into the audit ledger per CV-8.
    # The conversation store also preserves the original Message.
    original_content: Optional[str] = None
