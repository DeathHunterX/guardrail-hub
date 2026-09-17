"""Conversation lifecycle schemas."""
from typing import Optional

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    """Request body for creating a new conversation."""

    conversation_id: str = Field(
        ...,
        description="Unique identifier for the new conversation.",
        examples=["conv_abc123"],
        min_length=1,
    )

    model_config = {"extra": "forbid"}


class CreateConversationResponse(BaseModel):
    """Response body after creating a conversation."""

    conversation_id: str = Field(
        ...,
        description="The conversation's unique identifier.",
    )

    state: str = Field(
        ...,
        description="The conversation's initial state (always 'created').",
    )

    message_count: int = Field(
        ...,
        description="Number of messages in the transcript (zero at creation).",
    )

    model_config = {"extra": "allow"}


class GetConversationResponse(BaseModel):
    """Response body for retrieving a conversation."""

    conversation_id: str
    state: str
    message_count: int
    created_at: str
    updated_at: str

    model_config = {"extra": "allow"}


class TransitionRequest(BaseModel):
    """Request body for transitioning a conversation to a new state."""

    to_state: str = Field(
        ...,
        description=(
            "Target state. Valid values: 'open', 'closed', 'archived'. "
            "See Conversation Standard for valid transitions."
        ),
        examples=["open"],
    )

    model_config = {"extra": "forbid"}


class TransitionResponse(BaseModel):
    """Response body after a state transition."""

    conversation_id: str
    from_state: str
    to_state: str

    model_config = {"extra": "allow"}


class RedactMessageRequest(BaseModel):
    """Request body for redacting a message within a conversation."""

    message_index: int = Field(
        ...,
        ge=0,
        description="Zero-based index of the message to redact.",
        examples=[0],
    )

    policy: str = Field(
        default="default",
        description=(
            "Name of the registered redaction policy to apply. "
            "Defaults to 'default' (pattern-based: emails, API keys, SSN-like patterns)."
        ),
        examples=["default"],
    )

    model_config = {"extra": "forbid"}


class RedactMessageResponse(BaseModel):
    """Response body after redacting a message."""

    conversation_id: str
    message_index: int
    redaction_policy: str
    marker_content: str = Field(
        ...,
        description="The content of the appended redaction marker message.",
    )

    model_config = {"extra": "allow"}
