"""LLM Service — public entry point for LLM operations.

The service is the only sanctioned entry point from the MCP server into the
Intelligence Layer. It coordinates Router, RoutingStrategy, and ProviderManager
to execute capability requests.

Authority: ADR-0013 §4 decision 5 (single public interface),
ADR-0014 §5 (model-centric routing), routing standard RT-1.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional, Sequence

from app.intelligence.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMModelNotFoundError,
    LLMProviderError,
)
from app.intelligence.inference.router.router import Router
from app.intelligence.inference.strategies.base import RoutingStrategy
from app.intelligence.inference.strategies.priority import PriorityStrategy
from app.intelligence.ports.base import BaseProvider
from app.intelligence.ports.chat import ChatCapable, ChatMessage, ChatOptions, ChatResponse
from app.intelligence.ports.embedding import EmbeddingCapable, EmbeddingOptions, EmbeddingResponse
from app.intelligence.ports.rerank import RerankCapable, RerankDocument, RerankOptions, RerankResponse
from app.intelligence.ports.vision import VisionCapable, VisionOptions, VisionResponse
from app.intelligence.providers.base_provider import BaseProviderRuntime
from app.intelligence.providers.provider_manager import ProviderManager
from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.types.capability import Capability


class LLMService:
    """Public entry point for LLM operations.

    The service is constructed with a frozen catalog, a provider manager,
    and optionally a router and routing strategy. Each capability method
    follows the same request path:

    1. Resolve the routing decision (model + provider).
    2. Retrieve the provider singleton from the manager.
    3. Guard that the provider has been started.
    4. Delegate to the capability port.

    The service never inspects registry records, never constructs providers,
    and never calls adapters directly.
    """

    def __init__(
        self,
        provider_manager: ProviderManager,
        catalog: ModelCatalog,
        router: Optional[Router] = None,
        default_strategy: Optional[RoutingStrategy] = None,
    ) -> None:
        """Construct the LLM service.

        Args:
            provider_manager: Owns provider singletons; must be started.
            catalog: Frozen model catalog for routing decisions.
            router: Explicit router. If None, a router is constructed
                with the default_strategy.
            default_strategy: Routing strategy used when no explicit router
                is provided. If both router and default_strategy are None,
                PriorityStrategy is used.
        """
        self._provider_manager = provider_manager
        self._catalog = catalog

        if router is not None:
            self._router = router
        else:
            strategy = (
                default_strategy
                if default_strategy is not None
                else PriorityStrategy(catalog)
            )
            self._router = Router(catalog, default_strategy=strategy)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, capability: Capability, model: Optional[str], provider: Optional[str]):
        """Resolve a routing decision and return (provider, model_id).

        Raises:
            LLMModelNotFoundError: No capable model found.
            LLMProviderError: Provider not found or not started.
        """
        decision = self._router.route(capability, model=model, provider=provider)

        if decision.provider_id is None:
            raise LLMModelNotFoundError(
                f"no capable model found for capability '{capability.value}'"
            )

        prov = self._provider_manager.get_provider(decision.provider_id)
        if prov is None:
            raise LLMProviderError(
                f"provider '{decision.provider_id}' is not started; "
                "call ProviderManager.start() before issuing requests"
            )

        # Guard: prevent inference on an unstarted provider.
        if isinstance(prov, BaseProviderRuntime):
            prov._check_started()

        return prov, decision.model_id

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **options: Any,
    ) -> ChatResponse:
        """Generate a chat completion.

        Args:
            messages: Conversation history, oldest to newest.
            model: Specific model_id. If None, the router selects the best
                model based on the configured strategy.
            provider: Specific provider_id. If None, the router selects.
            **options: Forwarded as ChatOptions fields. Supported keys:
                temperature, max_tokens, top_p, stop, stream, seed,
                response_format.

        Returns:
            ChatResponse with the model's reply.

        Raises:
            LLMModelNotFoundError: No capable model found.
            LLMProviderError: Provider not started.
            LLMError: Any provider-level error translated by the adapter.
        """
        prov, model_id = self._resolve(Capability.CHAT, model, provider)
        opts = ChatOptions(model=model_id, **options)
        chat_provider = prov  # type: ChatCapable
        return await chat_provider.chat(messages, opts)

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **options: Any,
    ) -> tuple[str, AsyncIterator[str]]:
        """Generate a streaming chat completion.

        Yields text chunks as they arrive from the provider. Returns the
        resolved model ID alongside the chunk stream so callers can report
        which model generated the response.

        Args:
            messages: Conversation history, oldest to newest.
            model: Specific model_id. If None, the router selects.
            provider: Specific provider_id. If None, the router selects.
            **options: Forwarded as ChatOptions fields.

        Returns:
            A tuple of (resolved_model_id, AsyncIterator of text chunks).

        Raises:
            LLMModelNotFoundError: No capable model found.
            LLMProviderError: Provider not started.
            LLMError: Any provider-level error translated by the adapter.
        """
        prov, model_id = self._resolve(Capability.CHAT, model, provider)
        opts = ChatOptions(model=model_id, **options)
        stream = prov.chat_stream(messages, opts)  # type: ignore[return-value]
        return model_id, stream

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    async def embed(
        self,
        texts: Sequence[str],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **options: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings for texts.

        Args:
            texts: Sequence of texts to embed.
            model: Specific model_id. If None, the router selects.
            provider: Specific provider_id. If None, the router selects.
            **options: Forwarded as EmbeddingOptions fields.
                Supported keys: encoding_format, dimensions.

        Returns:
            EmbeddingResponse with vector representations.

        Raises:
            LLMModelNotFoundError: No capable model found.
            LLMProviderError: Provider not started.
            LLMError: Any provider-level error translated by the adapter.
        """
        prov, model_id = self._resolve(Capability.EMBEDDING, model, provider)
        opts = EmbeddingOptions(model=model_id, **options)
        embed_provider = prov  # type: EmbeddingCapable
        return await embed_provider.embed(texts, opts)

    # ------------------------------------------------------------------
    # Reranking
    # ------------------------------------------------------------------

    async def rerank(
        self,
        documents: Sequence[RerankDocument],
        query: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        top_n: Optional[int] = None,
        **options: Any,
    ) -> RerankResponse:
        """Rerank documents by relevance to a query.

        Args:
            documents: Documents to rerank.
            query: Query string for relevance scoring.
            model: Specific model_id. If None, the router selects.
            provider: Specific provider_id. If None, the router selects.
            top_n: Return only the top N results.
            **options: Forwarded as RerankOptions fields.

        Returns:
            RerankResponse with ranked documents and scores.

        Raises:
            LLMModelNotFoundError: No capable model found.
            LLMProviderError: Provider not started.
            LLMError: Any provider-level error translated by the adapter.
        """
        prov, model_id = self._resolve(Capability.RERANK, model, provider)
        opts = RerankOptions(model=model_id, query=query, top_n=top_n, **options)
        rerank_provider = prov  # type: RerankCapable
        return await rerank_provider.rerank(documents, opts)

    # ------------------------------------------------------------------
    # Vision
    # ------------------------------------------------------------------

    async def vision(
        self,
        messages: Sequence[tuple[str, str]],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **options: Any,
    ) -> VisionResponse:
        """Analyze images in a conversation context.

        Args:
            messages: Sequence of (role, content) tuples. Content may include
                image URLs or base64-encoded image data.
            model: Specific model_id. If None, the router selects.
            provider: Specific provider_id. If None, the router selects.
            **options: Forwarded as VisionOptions fields.
                Supported keys: max_tokens.

        Returns:
            VisionResponse with the model's analysis.

        Raises:
            LLMModelNotFoundError: No capable model found.
            LLMProviderError: Provider not started.
            LLMError: Any provider-level error translated by the adapter.
        """
        prov, model_id = self._resolve(Capability.VISION, model, provider)
        opts = VisionOptions(model=model_id, **options)
        vision_provider = prov  # type: VisionCapable
        return await vision_provider.vision(messages, opts)

    # ------------------------------------------------------------------
    # Convenience — no routing required
    # ------------------------------------------------------------------

    def get_provider(self, provider_id: str) -> Optional[BaseProvider]:
        """Return a provider singleton by ID.

        Args:
            provider_id: The provider's stable identifier.

        Returns:
            The provider instance, or None if not found or not started.
        """
        return self._provider_manager.get_provider(provider_id)

    def list_available_providers(self) -> list[str]:
        """Return IDs of all started provider instances."""
        return self._provider_manager.list_providers()

    def list_available_models(
        self,
        provider_id: Optional[str] = None,
    ) -> Sequence[Any]:
        """Return model summaries from the frozen catalog.

        Args:
            provider_id: Filter to models on a specific provider.

        Returns:
            Sequence of ModelSummary objects.
        """
        return self._catalog.list_models(provider_id=provider_id)
