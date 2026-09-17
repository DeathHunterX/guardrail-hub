"""Request schema for a streaming conversation turn.

The route adapter is responsible for translating this into a call to
``ConversationService.handle_turn_stream()``.

``conversation_id`` is taken from the URL path, not this body, so it is
deliberately absent from this schema.  All other fields mirror
``HandleTurnRequest``.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class HandleTurnStreamRequest(BaseModel):
    """Request body for a streaming conversation turn.

    Identical to ``HandleTurnRequest`` minus ``conversation_id`` (which is
    provided via the URL path parameter).
    """

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
