"""Chat capability port — text completion and conversation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional, Sequence

from app.intelligence.registry.types.capability import Capability


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A single message in a chat conversation."""

    role: str  # 'system', 'user', 'assistant'
    content: str
    name: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ChatOptions:
    """Options for chat completion requests."""

    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stop: Optional[Sequence[str]] = None
    stream: bool = False
    seed: Optional[int] = None
    response_format: Optional[dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """Response from a chat completion request."""

    content: str
    model: str
    finish_reason: Optional[str] = None
    usage: Optional[dict[str, int]] = None


class ChatCapable(ABC):
    """Contract for text chat completion capability.

    Providers implementing this port can handle chat completions.
    """

    @property
    def capability(self) -> Capability:
        return Capability.CHAT

    @abstractmethod
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> ChatResponse:
        """Generate a chat completion response.

        Args:
            messages: Conversation history, oldest to newest.
            options: Request options and model selection.

        Returns:
            ChatResponse with the model's reply.

        Raises:
            LLMAuthenticationError: Invalid credentials.
            LLMRateLimitedError: Rate limit exceeded.
            LLMTimeoutError: Request timed out.
            LLMUnavailableError: Provider unavailable.
            LLMValidationError: Invalid request parameters.
        """

    @abstractmethod
    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> AsyncIterator[str]:
        """Generate a streaming chat completion response.

        Args:
            messages: Conversation history, oldest to newest.
            options: Request options and model selection.

        Yields:
            Text chunks of the response as they arrive.

        Raises:
            Same as chat() method.
        """
