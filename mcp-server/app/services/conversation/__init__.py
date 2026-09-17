"""Conversation application service — public API.

Exposes :class:`ConversationService` as the single application-layer
orchestrator for conversation turns and lifecycle management.

Authority: Phase 5 implementation contract (Option B).
Placement: ``app/services/conversation/`` — outside ``app/intelligence/``.
"""

from app.services.conversation.conversation_service import (
    ConversationService,
)

__all__ = [
    "ConversationService",
]
