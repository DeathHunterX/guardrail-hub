"""Intelligence Layer — LLM provider abstraction, model registry, and inference orchestration.

This layer provides:
- Registry Context: Static metadata for providers and models
- Provider Runtime: Provider lifecycle management (Phase 3+)
- Inference Context: LLM service orchestration and routing
- Conversation Context: Message history and state management (Phase 4+)
- Health Context: Provider health monitoring (Phase 4+)

Architecture: Hexagonal (Ports & Adapters) with clean dependency boundaries.

Public API
===========

Import stable types directly from this package::

    from app.intelligence import LLMService, LLMConfigurationError

Or use sub-package imports for more specific types::

    from app.intelligence.exceptions import LLMConfigurationError
    from app.intelligence.providers import ProviderFactory, ProviderManager
    from app.intelligence.registry import ProviderRecord, ModelCatalog
    from app.intelligence.runtime import RegistryRuntime

Loaders, validators, builders, adapters, and internal helpers are not part of
the public API and must not be imported from this package.
"""

from app.intelligence.exceptions.llm import LLMError
from app.intelligence.inference.services.llm_service import LLMService
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.providers.provider_manager import ProviderManager
from app.intelligence.runtime.registry_runtime import RegistryRuntime

__all__ = [
    # Service interface
    "LLMService",
    # Provider lifecycle
    "ProviderFactory",
    "ProviderManager",
    # Registry runtime
    "RegistryRuntime",
    # Exception hierarchy
    "LLMError",
]
