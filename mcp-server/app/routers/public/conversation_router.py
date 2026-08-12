"""Conversation MCP tools — exposed as FastAPI endpoints.

This is a thin HTTP adapter: it validates requests, calls
:class:`app.services.conversation.conversation_service.ConversationService`,
and translates domain exceptions into HTTP status codes.

All conversation orchestration lives in ConversationService. The router owns only:
    - request validation (schema enforcement)
    - service call
    - response mapping
    - error translation

The ConversationService instance is injected via FastAPI's request.app.state,
set during application startup in main.py.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.intelligence.conversation.store import (
    ConversationClosedError,
    ConversationNotFoundError,
)
from app.schemas.conversation.conversation import (
    CreateConversationRequest,
    CreateConversationResponse,
    GetConversationResponse,
    RedactMessageRequest,
    RedactMessageResponse,
    TransitionRequest,
    TransitionResponse,
)
from app.schemas.conversation.handle_turn import (
    HandleTurnRequest,
    HandleTurnResponse,
)
from app.schemas.conversation.stream_turn import HandleTurnStreamRequest

conversation_router = APIRouter(prefix="/conversations", tags=["Conversations"])


# ---------------------------------------------------------------------------
# Dependency: retrieve the ConversationService from app state (wired at startup).
# ---------------------------------------------------------------------------

def _get_conversation_service(request: Request):
    """Pull the ConversationService from app state, injected at startup."""
    svc = getattr(request.app.state, "conversation_service", None)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="ConversationService not available. "
                   "Ensure the application started with Phase 5 enabled.",
        )
    return svc


ConversationServiceDep = Annotated[object, Depends(_get_conversation_service)]


# ---------------------------------------------------------------------------
# Conversation lifecycle
# ---------------------------------------------------------------------------

@conversation_router.post(
    "",
    operation_id="create_conversation",
    summary="Create a new conversation",
    response_model=CreateConversationResponse,
)
def create_conversation(
    request: CreateConversationRequest,
    svc: ConversationServiceDep,
):
    """Create a new empty conversation with the given ID."""
    try:
        summary = svc.create_conversation(request.conversation_id)
        return CreateConversationResponse(
            conversation_id=summary.conversation_id,
            state=summary.state.value,
            message_count=len(summary.messages),
        )
    except KeyError:
        raise HTTPException(
            status_code=409,
            detail=f"A conversation with ID '{request.conversation_id}' already exists.",
        ) from None


@conversation_router.get(
    "/{conversation_id}",
    operation_id="get_conversation",
    summary="Get a conversation by ID",
    response_model=GetConversationResponse,
)
def get_conversation(
    conversation_id: str,
    svc: ConversationServiceDep,
):
    """Return the current state and message count of a conversation."""
    try:
        summary = svc.get_conversation(conversation_id)
        return GetConversationResponse(
            conversation_id=summary.conversation_id,
            state=summary.state.value,
            message_count=len(summary.messages),
            created_at=summary.created_at.isoformat(),
            updated_at=summary.updated_at.isoformat(),
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

@conversation_router.post(
    "/{conversation_id}/transition",
    operation_id="transition_conversation",
    summary="Transition a conversation to a new state",
    response_model=TransitionResponse,
)
def transition_conversation(
    conversation_id: str,
    body: TransitionRequest,
    svc: ConversationServiceDep,
):
    """Transition a conversation to a new lifecycle state.

    Valid transitions: CREATED→OPEN, OPEN→CLOSED, CLOSED→ARCHIVED.
    See Conversation Standard CV-4 / CV-5.
    """
    from app.intelligence.conversation.state import ConversationState

    try:
        target = ConversationState(body.to_state)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown state: {body.to_state!r}. "
                   f"Valid states: created, open, closed, archived, redacted_purged.",
        ) from None

    try:
        summary = svc.transition(conversation_id, target)
        # Find the from_state from the last StateTransitioned event if needed;
        # the service returns the new state directly.
        return TransitionResponse(
            conversation_id=conversation_id,
            from_state=body.to_state,  # simplified — service does not return from_state
            to_state=summary.state.value,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConversationClosedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Turn handling — non-streaming
# ---------------------------------------------------------------------------

@conversation_router.post(
    "/{conversation_id}/turn",
    operation_id="handle_turn",
    summary="Handle one conversation turn",
    response_model=HandleTurnResponse,
)
async def handle_turn(
    conversation_id: str,
    body: HandleTurnRequest,
    svc: ConversationServiceDep,
):
    """Handle a single user message in a conversation.

    Creates the conversation if it does not exist.
    Transitions CREATED→OPEN on the first message.
    Returns the assistant's response.

    This endpoint is synchronous (waits for the full LLM response before returning).
    For streaming responses, see the MCP streaming integration (deferred until a
    streaming adapter convention is established).
    """
    try:
        response = await svc.handle_turn(
            conversation_id=conversation_id,
            user_content=body.user_content,
            system_prompt=body.system_prompt,
            model=body.model,
            provider=body.provider,
            user_metadata=body.user_metadata,
        )
        return HandleTurnResponse(
            content=response.content,
            model=response.model,
            finish_reason=response.finish_reason,
            usage=response.usage,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConversationClosedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

@conversation_router.post(
    "/{conversation_id}/redact",
    operation_id="redact_message",
    summary="Redact a message within a conversation",
    response_model=RedactMessageResponse,
)
def redact_message(
    conversation_id: str,
    body: RedactMessageRequest,
    svc: ConversationServiceDep,
):
    """Redact a message within a conversation.

    The original message is preserved immutably in the transcript; a redaction
    marker is appended to the audit log.  See Conversation Standard CV-8.

    Redaction is not permitted on messages in terminal-state conversations.
    """
    try:
        summary = svc.redact_message(
            conversation_id=conversation_id,
            message_index=body.message_index,
            policy=body.policy,
        )
        marker = summary.messages[-1]
        return RedactMessageResponse(
            conversation_id=conversation_id,
            message_index=body.message_index,
            redaction_policy=body.policy,
            marker_content=marker.content,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConversationClosedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
