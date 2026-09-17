"""Conversation Context — message history and state management.

This bounded context owns:
- The conversation state machine and its transitions.
- The immutable transcript model (Message, ConversationSummary).
- The ConversationStore port and its adapters.
- The event contracts used for audit (CV-7).
- Redaction, replay, and JSONL export.

Authority: Conversation Standard (Active, v1.0.0).

Dependency rules (enforced):
- This package MUST NOT import LLMService.
- This package MUST NOT import provider adapters.
- This package MUST NOT import FastAPI or any HTTP framework.
"""

from app.intelligence.conversation.events import (
    ConversationCreated,
    ConversationEvent,
    MessageAppended,
    RedactionPerformed,
    StateTransitioned,
)
from app.intelligence.conversation.message import Message
from app.intelligence.conversation.state import ConversationState
from app.intelligence.conversation.store import (
    ConversationClosedError,
    ConversationNotFoundError,
    ConversationStore,
    ConversationStoreError,
    ConversationSummary,
)

__all__ = [
    # State
    "ConversationState",
    # Message
    "Message",
    # Store
    "ConversationStore",
    "ConversationSummary",
    "ConversationStoreError",
    "ConversationNotFoundError",
    "ConversationClosedError",
    # Events
    "ConversationEvent",
    "ConversationCreated",
    "StateTransitioned",
    "MessageAppended",
    "RedactionPerformed",
]
