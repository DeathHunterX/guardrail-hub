"""Provider lifecycle management — factory, manager, and adapter implementations.

Phase 3: providers are created exclusively by :class:`ProviderFactory` from
frozen :class:`ModelCatalog` records via :class:`ProviderManager`. Adapters are
registered via :func:`app.intelligence.providers.adapters.register_all_adapters`.

Usage::

    from app.intelligence.providers import ProviderFactory, ProviderManager
    from app.intelligence.providers.adapters import register_all_adapters

    factory = ProviderFactory()
    register_all_adapters(factory)

    manager = ProviderManager(factory, catalog=catalog)
    await manager.start()

    provider = manager.get_provider("my-ollama")

Adapters (``OllamaAdapter``, ``OpenAICompatibleAdapter``, ``BedrockAdapter``)
are not re-exported here to keep the public surface minimal. Import them
directly from ``app.intelligence.providers.adapters`` when needed.
"""

from app.intelligence.providers.base_provider import BaseProviderRuntime
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.providers.provider_manager import ProviderManager

__all__ = [
    "BaseProviderRuntime",
    "ProviderFactory",
    "ProviderManager",
]
