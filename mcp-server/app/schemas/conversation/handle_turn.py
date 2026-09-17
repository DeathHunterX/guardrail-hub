"""Request and response schemas for a non-streaming conversation turn."""
from typing import Any, Optional

from pydantic import BaseModel, Field


class HandleTurnRequest(BaseModel):
    """Request body for a single conversation turn.

    The route adapter is responsible for translating this into a call to
    ``ConversationService.handle_turn()``.
    """

    conversation_id: str = Field(
        ...,
        description=(
            "Unique identifier for the conversation. If a conversation with this "
            "ID does not exist, a new one is created automatically in the CREATED state."
        ),
        examples=["conv_abc123"],
        min_length=1,
    )

    user_content: str = Field(
        ...,
        description="The user's message to the assistant.",
        examples=["What are the top three vulnerabilities found in my last scan?"],
        min_length=1,
    )

    system_prompt: Optional[str] = Field(
        default=None,
        description=(
            "Optional system prompt prepended to the conversation transcript. "
            "When omitted, the conversation uses only the message history."
        ),
        examples=["You are a helpful security analysis assistant."],
    )

    model: Optional[str] = Field(
        default=None,
        description=(
            "Specific model ID to use for this turn. "
            "When omitted, the Intelligence Layer's routing strategy selects the model."
        ),
        examples=["gpt-4o-mini"],
    )

    provider: Optional[str] = Field(
        default=None,
        description=(
            "Specific provider to use for this turn. "
            "When omitted, the Intelligence Layer's routing strategy selects the provider."
        ),
        examples=["openai"],
    )

    user_metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Arbitrary key-value metadata attached to the user Message. "
            "Not used by the service; stored verbatim for audit traceability."
        ),
    )

    model_config = {"extra": "forbid"}


class HandleTurnResponse(BaseModel):
    """Response body for a single conversation turn.

    Mirrors ``ChatResponse`` from the Intelligence Layer port contract.
    """

    content: str = Field(
        ...,
        description="The assistant's reply text.",
    )

    model: str = Field(
        ...,
        description="Model ID that generated the response.",
    )

    finish_reason: Optional[str] = Field(
        default=None,
        description="Reason the model stopped generating (e.g. 'stop', 'length').",
    )

    usage: Optional[dict[str, int]] = Field(
        default=None,
        description="Token usage information if available from the provider.",
    )

    model_config = {"extra": "allow"}
