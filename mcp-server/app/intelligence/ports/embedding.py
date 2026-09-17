"""Embedding capability port — text vectorization."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Sequence

from app.intelligence.registry.types.capability import Capability


@dataclass(frozen=True, slots=True)
class EmbeddingOptions:
    """Options for embedding requests."""

    model: str
    encoding_format: str = "float"  # 'float' or 'base64'
    dimensions: Optional[int] = None  # Optional dimensionality reduction


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    """Response from an embedding request."""

    embeddings: Sequence[Sequence[float]]
    model: str
    usage: Optional[dict[str, int]] = None


class EmbeddingCapable(ABC):
    """Contract for text embedding capability.

    Providers implementing this port can generate text embeddings.
    """

    @property
    def capability(self) -> Capability:
        return Capability.EMBEDDING

    @abstractmethod
    async def embed(
        self,
        texts: Sequence[str],
        options: EmbeddingOptions,
    ) -> EmbeddingResponse:
        """Generate embeddings for the given texts.

        Args:
            texts: Sequence of texts to embed.
            options: Request options and model selection.

        Returns:
            EmbeddingResponse with vector representations.

        Raises:
            LLMAuthenticationError: Invalid credentials.
            LLMRateLimitedError: Rate limit exceeded.
            LLMTimeoutError: Request timed out.
            LLMUnavailableError: Provider unavailable.
            LLMValidationError: Invalid request parameters.
        """
