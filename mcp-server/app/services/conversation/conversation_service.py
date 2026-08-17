"""ConversationService — application-layer orchestration for conversation turns.

Authority: Phase 5 implementation contract (Option B).

This service is the single orchestrator for the conversation lifecycle.  It
owns the read -> assemble -> infer -> append -> audit sequence.  It does NOT
own conversation semantics (those belong to the Conversation bounded context)
and it does NOT own inference (that belongs to LLMService).

Placement: ``app/services/conversation/`` — outside ``app/intelligence/``.
All imports from ``app/intelligence.conversation`` are read-only.

Orchestration contract per turn::

    MCP route
      └─ ConversationService.handle_turn()
            ├─ read  ConversationStore (get transcript)
            ├─ validate state (non-terminal)
            ├─ transition CREATED → OPEN if first message
            ├─ append user Message  → ConversationStore
            ├─ await LLMService.chat(messages)
            ├─ append assistant Message → ConversationStore
            ├─ emit  ConversationEvent(s) → EventPublisher
            └─ return ChatResponse

Error contract: if LLMService.chat() fails after the user Message has been
appended to the store, the conversation transcript contains the user Message but
no assistant response.  This is recoverable — the next turn can include the
partial transcript.  The ConversationService never discards a user Message.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from app.core.ports.event_publisher import EventPublisher
from app.intelligence.conversation.events import (
    ConversationCreated,
    MessageAppended,
    RedactionPerformed,
    StateTransitioned,
)
from app.intelligence.conversation.machine import can_transition_to
from app.intelligence.conversation.message import Message
from app.intelligence.conversation.redaction import apply_redaction
from app.intelligence.conversation.state import ConversationState
from app.intelligence.conversation.store import (
    ConversationClosedError,
    ConversationNotFoundError,
    ConversationStore,
    ConversationSummary,
)
from app.intelligence.inference.services.llm_service import LLMService
from app.intelligence.ports.chat import ChatMessage, ChatResponse


class ConversationService:
    """Orchestrates conversation turns: read, infer, append, audit."""

    def __init__(
        self,
        store: ConversationStore,
        llm_service: LLMService,
        publisher: EventPublisher,
    ) -> None:
        """
        Args:
            store: The ConversationStore port (in-memory or DAO adapter).
            llm_service: The Intelligence Layer's LLMService.
            publisher: The platform EventPublisher for audit events.
        """
        self._store = store
        self._llm = llm_service
        self._pub = publisher

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create_conversation(
        self,
        conversation_id: str,
        initial_state: ConversationState | None = None,
    ) -> ConversationSummary:
        """Create a new empty conversation.

        Args:
            conversation_id: Unique identifier.
            initial_state: Starting state.  Defaults to CREATED.

        Returns:
            The initial ConversationSummary.

        Raises:
            KeyError: If a conversation with this id already exists.
        """
        summary = self._store.create(conversation_id, initial_state=initial_state)
        self._pub.publish(
            ConversationCreated(
                conversation_id=conversation_id,
                initial_state=summary.state,
            )
        )
        return summary

    def get_conversation(self, conversation_id: str) -> ConversationSummary:
        """Return the current snapshot for a conversation.

        Args:
            conversation_id: Conversation to retrieve.

        Returns:
            ConversationSummary.

        Raises:
            ConversationNotFoundError: If the conversation does not exist.
        """
        summary = self._store.read(conversation_id)
        if summary is None:
            raise ConversationNotFoundError(conversation_id)
        return summary

    def transition(
        self,
        conversation_id: str,
        to_state: ConversationState,
    ) -> ConversationSummary:
        """Transition a conversation to a new state.

        Args:
            conversation_id: Conversation to transition.
            to_state: The target state.

        Returns:
            The updated ConversationSummary.

        Raises:
            ConversationNotFoundError: If the conversation does not exist.
            ValueError: If the transition is not permitted.
            ConversationClosedError: If the conversation is in a terminal state
                and cannot transition.
        """
        summary = self._store.read(conversation_id)
        if summary is None:
            raise ConversationNotFoundError(conversation_id)

        if not can_transition_to(summary.state, to_state):
            raise ValueError(
                f"invalid transition: {summary.state.value!r} -> {to_state.value!r}"
            )

        from_state = summary.state
        summary = self._store.transition_to(conversation_id, to_state)
        self._pub.publish(
            StateTransitioned(
                conversation_id=conversation_id,
                from_state=from_state,
                to_state=to_state,
            )
        )
        return summary

    # ------------------------------------------------------------------
    # Turn orchestration — non-streaming
    # ------------------------------------------------------------------

    async def handle_turn(
        self,
        conversation_id: str,
        user_content: str,
        system_prompt: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """Handle one user turn end-to-end.

        Orchestration sequence::

            1. Read conversation state from the store.
            2. Validate: conversation exists and is not terminal.
            3. Transition CREATED -> OPEN if first message.
            4. Append user Message to the store.
            5. Assemble messages: [system?] + transcript + [user Message].
            6. Await LLMService.chat() with the assembled messages.
            7. Append assistant Message to the store.
            8. Emit audit events for both appends.
            9. Return the ChatResponse to the caller.

        Error contract: if LLMService.chat() fails after step 4, the user
        Message is already persisted — the transcript is consistent (a user
        message with no assistant reply is recoverable).  The error is
        propagated to the caller.

        Args:
            conversation_id: The conversation to continue.
            user_content: The user's message content.
            system_prompt: Optional system prompt prepended to the transcript.
            model: Specific model to use (optional).
            provider: Specific provider to use (optional).
            user_metadata: Arbitrary metadata attached to the user Message.

        Returns:
            ChatResponse from the LLM.

        Raises:
            ConversationNotFoundError: If the conversation does not exist.
            ConversationClosedError: If the conversation is in a terminal state.
            LLMError: Any provider-level error from LLMService.
        """
        # 1-2: read and validate
        summary = self._store.read(conversation_id)
        if summary is None:
            raise ConversationNotFoundError(conversation_id)
        if summary.state.is_terminal:
            raise ConversationClosedError(
                f"conversation {conversation_id!r} is in terminal state "
                f"{summary.state.value!r}; no new turns accepted"
            )

        # 3: transition CREATED -> OPEN on first message
        #     Persist first, then publish — never publish before the store succeeds.
        if summary.state == ConversationState.CREATED:
            if can_transition_to(summary.state, ConversationState.OPEN):
                self._store.transition_to(conversation_id, ConversationState.OPEN)
                self._pub.publish(
                    StateTransitioned(
                        conversation_id=conversation_id,
                        from_state=ConversationState.CREATED,
                        to_state=ConversationState.OPEN,
                    )
                )
            summary = self._store.read(conversation_id)

        # 4: append user message
        user_msg = Message(
            role="user",
            content=user_content,
            timestamp=datetime.now(timezone.utc),
            metadata=tuple((user_metadata or {}).items()),
        )
        summary = self._store.append(conversation_id, user_msg)
        self._pub.publish(
            MessageAppended(
                conversation_id=conversation_id,
                message_index=len(summary.messages) - 1,
                role=user_msg.role,
                redacted=False,
            )
        )

        # 5: assemble messages for LLMService
        llm_messages = self._build_llm_messages(summary, system_prompt)

        # 6: await LLMService
        response = await self._llm.chat(
            messages=llm_messages,
            model=model,
            provider=provider,
        )

        # 7: append assistant message
        assistant_msg = Message(
            role="assistant",
            content=response.content,
            timestamp=datetime.now(timezone.utc),
            metadata=(
                ("model", response.model),
                ("finish_reason", response.finish_reason),
            ),
        )
        summary = self._store.append(conversation_id, assistant_msg)
        self._pub.publish(
            MessageAppended(
                conversation_id=conversation_id,
                message_index=len(summary.messages) - 1,
                role=assistant_msg.role,
                redacted=False,
            )
        )

        # 8 + 9: audit already published; return
        return response

    # ------------------------------------------------------------------
    # Turn orchestration — streaming
    # ------------------------------------------------------------------

    async def handle_turn_stream(
        self,
        conversation_id: str,
        user_content: str,
        system_prompt: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> tuple[ConversationSummary, str, AsyncIterator[str]]:
        """Handle one streaming user turn.

        Like handle_turn but the LLM response is streamed.  The assistant
        Message is persisted after the stream completes so the content is
        available.  Call :meth:`finalise_stream` to complete the sequence.

        Args:
            conversation_id: The conversation to continue.
            user_content: The user's message content.
            system_prompt: Optional system prompt.
            model: Specific model to use.
            provider: Specific provider to use.
            user_metadata: Arbitrary metadata attached to the user Message.

        Returns:
            A tuple of (updated ConversationSummary, resolved_model_id, AsyncIterator of text chunks).
            The resolved_model_id is the actual model ID used to generate the response.

        Raises:
            ConversationNotFoundError: If the conversation does not exist.
            ConversationClosedError: If the conversation is in a terminal state.
            LLMError: Any provider-level error from LLMService.
        """
        # 1-5: same read/validate/append/assemble as handle_turn
        summary = self._store.read(conversation_id)
        if summary is None:
            raise ConversationNotFoundError(conversation_id)
        if summary.state.is_terminal:
            raise ConversationClosedError(
                f"conversation {conversation_id!r} is in terminal state "
                f"{summary.state.value!r}; no new turns accepted"
            )

        # 3: transition CREATED -> OPEN — persist first, then publish.
        if summary.state == ConversationState.CREATED:
            if can_transition_to(summary.state, ConversationState.OPEN):
                self._store.transition_to(conversation_id, ConversationState.OPEN)
                self._pub.publish(
                    StateTransitioned(
                        conversation_id=conversation_id,
                        from_state=ConversationState.CREATED,
                        to_state=ConversationState.OPEN,
                    )
                )
            summary = self._store.read(conversation_id)

        user_msg = Message(
            role="user",
            content=user_content,
            timestamp=datetime.now(timezone.utc),
            metadata=tuple((user_metadata or {}).items()),
        )
        summary = self._store.append(conversation_id, user_msg)
        self._pub.publish(
            MessageAppended(
                conversation_id=conversation_id,
                message_index=len(summary.messages) - 1,
                role=user_msg.role,
                redacted=False,
            )
        )

        llm_messages = self._build_llm_messages(summary, system_prompt)

        resolved_model_id, stream = await self._llm.chat_stream(
            messages=llm_messages,
            model=model,
            provider=provider,
        )

        # Return summary so caller can call finalise_stream with it
        return summary, resolved_model_id, stream

    def finalise_stream(
        self,
        conversation_id: str,
        prior_summary: ConversationSummary,
        final_content: str,
        model: str | None = None,
    ) -> ConversationSummary:
        """Append the completed assistant message after a streaming turn.

        Call this after the caller has fully consumed the stream and has the
        complete ``final_content``.

        Args:
            conversation_id: The conversation.
            prior_summary: The ConversationSummary returned by handle_turn_stream
                (before the assistant message was appended).
            final_content: The complete assistant response accumulated from the stream.
            model: The model that generated the response.

        Returns:
            The updated ConversationSummary.
        """
        assistant_msg = Message(
            role="assistant",
            content=final_content,
            timestamp=datetime.now(timezone.utc),
            metadata=(("model", model or ""),),
        )
        summary = self._store.append(conversation_id, assistant_msg)
        self._pub.publish(
            MessageAppended(
                conversation_id=conversation_id,
                message_index=len(summary.messages) - 1,
                role=assistant_msg.role,
                redacted=False,
            )
        )
        return summary

    # ------------------------------------------------------------------
    # Redaction — CV-8
    # ------------------------------------------------------------------

    def redact_message(
        self,
        conversation_id: str,
        message_index: int,
        policy: str = "default",
    ) -> ConversationSummary:
        """Redact a message within a conversation.

        Immutability contract (CV-2): the original Message is never modified.
        Instead, the redaction appends a new system Message that records the
        redaction action and the redacted content.  The original Message stays
        at its index in the transcript.

        Audit contract (CV-7): the RedactionPerformed event is published after
        the store append succeeds.  The original content is NOT included in the
        event (per CV-8: original content is preserved in the conversation store).

        Terminal-state contract (CV-6): redaction is not permitted on messages
        within terminal-state conversations.

        Args:
            conversation_id: The conversation containing the message.
            message_index: Zero-based index of the message to redact.
            policy: The registered redaction policy name.  Defaults to "default".

        Returns:
            The updated ConversationSummary.

        Raises:
            ConversationNotFoundError: If the conversation does not exist.
            IndexError: If message_index is out of range.
            ValueError: If the policy name is not registered.
            ConversationClosedError: If the conversation is in a terminal state.
        """
        summary = self._store.read(conversation_id)
        if summary is None:
            raise ConversationNotFoundError(conversation_id)
        if summary.state.is_terminal:
            raise ConversationClosedError(
                f"conversation {conversation_id!r} is in terminal state "
                f"{summary.state.value!r}; redaction is not permitted"
            )

        if message_index < 0 or message_index >= len(summary.messages):
            raise IndexError(
                f"message_index {message_index} out of range "
                f"[0, {len(summary.messages)})"
            )

        original_message = summary.messages[message_index]

        # Apply the redaction policy to the content.
        redacted_content = apply_redaction(original_message.content, policy=policy)

        # Append a system message that records the redaction.
        # The original message stays immutable in the transcript at its index.
        redaction_marker_msg = Message(
            role="system",
            content=(
                f"[Message at index {message_index} redacted by policy "
                f"'{policy}': {redacted_content}]"
            ),
            timestamp=datetime.now(timezone.utc),
            metadata=(
                ("redacted_index", message_index),
                ("redaction_policy", policy),
                ("original_content_preserved", True),
            ),
            redacted=False,
        )

        summary = self._store.append(conversation_id, redaction_marker_msg)
        self._pub.publish(
            RedactionPerformed(
                conversation_id=conversation_id,
                message_index=message_index,
                redaction_policy=policy,
                original_content=original_message.content,
            )
        )
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_llm_messages(
        self,
        summary: ConversationSummary,
        system_prompt: str | None,
    ) -> list[ChatMessage]:
        """Assemble a Sequence[ChatMessage] from a ConversationSummary."""
        messages: list[ChatMessage] = []
        if system_prompt is not None:
            messages.append(ChatMessage(role="system", content=system_prompt))
        for msg in summary.messages:
            messages.append(ChatMessage(role=msg.role, content=msg.content, name=msg.name))
        return messages
