"""Reranking capability port — document re-ranking for retrieval."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Sequence

from app.intelligence.registry.types.capability import Capability


@dataclass(frozen=True, slots=True)
class RerankDocument:
    """A document to be reranked."""

    id: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RerankOptions:
    """Options for reranking requests."""

    model: str
    query: str
    top_n: Optional[int] = None
    return_documents: bool = True


@dataclass(frozen=True, slots=True)
class RerankResult:
    """A single reranked result."""

    index: int
    document: Optional[RerankDocument] = None
    relevance_score: float = 0.0


@dataclass(frozen=True, slots=True)
class RerankResponse:
    """Response from a reranking request."""

    results: Sequence[RerankResult]
    model: str


class RerankCapable(ABC):
    """Contract for document reranking capability.

    Providers implementing this port can rerank documents for improved retrieval.
    """

    @property
    def capability(self) -> Capability:
        return Capability.RERANK

    @abstractmethod
    async def rerank(
        self,
        documents: Sequence[RerankDocument],
        options: RerankOptions,
    ) -> RerankResponse:
        """Rerank documents based on query relevance.

        Args:
            documents: Documents to rerank.
            options: Request options with query and model selection.

        Returns:
            RerankResponse with ranked documents and scores.

        Raises:
            LLMAuthenticationError: Invalid credentials.
            LLMRateLimitedError: Rate limit exceeded.
            LLMTimeoutError: Request timed out.
            LLMUnavailableError: Provider unavailable.
            LLMValidationError: Invalid request parameters.
        """
