"""Provider adapters — concrete implementations of the provider port contracts.

Each adapter corresponds to a :class:`ProviderType` value in the registry.
Adapters are registered with :class:`ProviderFactory` at application startup.

Adapter registration::

    from app.intelligence.providers.provider_factory import ProviderFactory
    from app.intelligence.providers.adapters import register_all_adapters

    factory = ProviderFactory()
    register_all_adapters(factory)

The registry runtime automatically performs this registration via
:meth:`register_all_adapters`.

Phase 3 contract: all adapters are placeholders. Inference methods
(``chat``, ``embed``) raise :class:`NotImplementedError`. Full
implementation is deferred to Phase 4 (Inference Execution).
"""

from app.intelligence.providers.adapters.bedrock import BedrockAdapter
from app.intelligence.providers.adapters.ollama import OllamaAdapter
from app.intelligence.providers.adapters.openai_compatible import (
    OpenAICompatibleAdapter,
)

__all__ = [
    "BedrockAdapter",
    "OllamaAdapter",
    "OpenAICompatibleAdapter",
]


def register_all_adapters(factory: "ProviderFactory") -> None:
    """Register all Phase 3 adapters with a ProviderFactory.

    Call this once during application bootstrap, before the
    :class:`ProviderManager` is started.

    Args:
        factory: The factory to register adapters with.
    """
    from app.intelligence.providers.provider_factory import ProviderFactory

    from app.intelligence.registry.types.capability import Capability

    factory: ProviderFactory

    factory.register(
        "ollama",
        OllamaAdapter,
        description="Ollama self-hosted inference (chat + embeddings)",
    )
    factory.register_capabilities(
        "ollama",
        frozenset({
            Capability.CHAT,
            Capability.EMBEDDING,
        }),
    )

    factory.register(
        "openai_compatible",
        OpenAICompatibleAdapter,
        description="OpenAI-API-compatible endpoint (chat + embeddings)",
    )
    factory.register_capabilities(
        "openai_compatible",
        frozenset({
            Capability.CHAT,
            Capability.EMBEDDING,
        }),
    )

    factory.register(
        "bedrock",
        BedrockAdapter,
        description="AWS Bedrock runtime (chat + embeddings)",
    )
    factory.register_capabilities(
        "bedrock",
        frozenset({
            Capability.CHAT,
            Capability.EMBEDDING,
        }),
    )
