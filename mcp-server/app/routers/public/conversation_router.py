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
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

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
# SSE helpers
# ---------------------------------------------------------------------------

async def _sse_event(event_type: str, data: object) -> str:
    """Serialize an SSE event with a JSON body.

    Args:
        event_type: SSE event name (e.g. "chunk", "done", "error").
        data: Python object to serialize as JSON.

    Returns:
        A properly formatted SSE message, e.g.:
            event: chunk
            data: {"content": "Hello"}

    The JSON body is always one line; newlines within string values are
    escaped as \\n so the SSE format remains valid.
    """
    body = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {body}\n\n"


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
    For streaming responses, see POST /conversations/{conversation_id}/turn/stream.
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
# Turn handling — streaming
# ---------------------------------------------------------------------------

@conversation_router.post(
    "/{conversation_id}/turn/stream",
    operation_id="handle_turn_stream",
    summary="Handle one conversation turn with streaming response",
)
async def handle_turn_stream(
    conversation_id: str,
    body: HandleTurnStreamRequest,
    svc: ConversationServiceDep,
):
    """Handle a single user message with a streaming assistant response.

    The assistant's response is streamed back as Server-Sent Events (SSE).
    The user message is persisted immediately; the assistant message is
    persisted via ConversationService.finalise_stream() after the stream
    completes.

    SSE event contract:
        event: chunk
        data: {"content": "<text chunk>"}

        event: done
        data: {"content": "<full content>", "model": "<model>", "finish_reason": "stop"}

        event: error
        data: {"detail": "<error message>"}

    The stream always terminates with exactly one terminal event (done or error).
    finalise_stream() is called regardless of how the stream ends.
    """
    try:
        prior_summary, chunk_stream = await svc.handle_turn_stream(
            conversation_id=conversation_id,
            user_content=body.user_content,
            system_prompt=body.system_prompt,
            model=body.model,
            provider=body.provider,
            user_metadata=body.user_metadata,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConversationClosedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    accumulated: list[str] = []
    resolved_model: str | None = None

    async def event_generator():
        """Async generator producing SSE events.

        Guarantees finalise_stream() is called on:
        - Normal stream completion
        - Provider/LLM error during iteration
        - Client disconnection (aclose() / cancellation)

        The finally block is critical: it runs when FastAPI/uvicorn calls
        aclose() on this generator after a client disconnect, which injects
        GeneratorExit into the async iteration.  The finally block runs
        regardless of how the generator exits, ensuring finalise_stream()
        is called with the accumulated content even when the stream is
        cancelled mid-iteration.

        Note: yielding from a finally block raises RuntimeError in Python 3.10,
        so the error event is yielded only in the except path.
        """
        nonlocal accumulated, resolved_model
        _finalised = False  # guard against double-finalise if normal path succeeds

        try:
            async for chunk in chunk_stream:
                accumulated.append(chunk)
                yield await _sse_event("chunk", {"content": chunk})

            # Stream completed normally.
            final_content = "".join(accumulated)
            _finalised = True
            svc.finalise_stream(
                conversation_id=conversation_id,
                prior_summary=prior_summary,
                final_content=final_content,
                model=resolved_model,
            )
            yield await _sse_event(
                "done",
                {"content": final_content, "model": resolved_model or "", "finish_reason": "stop"},
            )

        except Exception as exc:
            # An LLM/provider error occurred after streaming started.
            # Call finalise_stream() with partial content, then emit error event.
            # Set _finalised so the finally block does not double-finalise.
            partial_content = "".join(accumulated)
            if not _finalised:
                _finalised = True
                try:
                    svc.finalise_stream(
                        conversation_id=conversation_id,
                        prior_summary=prior_summary,
                        final_content=partial_content,
                        model=resolved_model,
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "finalise_stream() failed after stream error for conversation %s",
                        conversation_id,
                    )
            yield await _sse_event("error", {"detail": str(exc)})

        finally:
            # Runs on aclose() (client disconnect), CancelledError, or normal exit.
            # Must NOT yield — raising GeneratorExit after a yield raises RuntimeError.
            if not _finalised:
                partial_content = "".join(accumulated)
                try:
                    svc.finalise_stream(
                        conversation_id=conversation_id,
                        prior_summary=prior_summary,
                        final_content=partial_content,
                        model=resolved_model,
                    )
                except Exception:
                    # Log but do not re-raise — the SSE stream may already be closed.
                    import logging
                    logging.getLogger(__name__).exception(
                        "finalise_stream() failed during cleanup for conversation %s",
                        conversation_id,
                    )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # Disable FastAPI's default JSON charset so the SSE stream is
            # treated as raw text. UTF-8 is the default encoding.
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Tell HTTP/1.1 proxies and clients this is a streaming response.
            "X-Accel-Buffering": "no",
        },
    )


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
