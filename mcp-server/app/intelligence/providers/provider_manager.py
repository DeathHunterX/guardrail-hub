"""Provider Manager — manages provider lifecycle and instances.

Owns provider instances. Providers are singleton per provider_id.
Do NOT create providers per request.

Phase 2 contract: the frozen :class:`ModelCatalog` is the **single source
of truth** for provider initialization. A catalog must be provided at
construction time; no other bootstrap path exists.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator, Optional

from app.intelligence.exceptions import LLMConfigurationError, LLMProviderError
from app.intelligence.ports.base import BaseProvider
from app.intelligence.providers.base_provider import BaseProviderRuntime
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.registry.catalog.catalog import ModelCatalog

if TYPE_CHECKING:
    pass


_logger = logging.getLogger(__name__)


class ProviderManager:
    """Manages the lifecycle of all enabled providers.

    Responsibilities:
    * Startup: Call ``initialize()`` → ``validate_configuration()`` →
      ``start()`` on every enabled provider from the frozen catalog.
    * Shutdown: Call ``close()`` on every provider instance.
    * Access: Return provider instances by ID.

    Provider instances are singleton per ``provider_id`` — the manager
    never creates two instances with the same ID.

    Phase 2 contract: the catalog is the **single source of truth** for
    provider initialization. A catalog must be provided; there is no
    fallback or manual-add path.
    """

    def __init__(
        self,
        factory: ProviderFactory,
        catalog: ModelCatalog,
    ) -> None:
        """Construct the manager.

        Args:
            factory: ProviderFactory instance with all known adapter types registered.
            catalog: Frozen ModelCatalog containing all enabled ProviderRecords.

        Raises:
            LLMConfigurationError: If ``catalog`` is None.
        """
        if catalog is None:
            raise LLMConfigurationError(
                "ProviderManager requires a ModelCatalog; "
                "the catalog is the single source of truth for provider initialization"
            )
        self._factory = factory
        self._catalog = catalog
        self._providers: dict[str, BaseProvider] = {}
        self._initialized = False

    @property
    def initialized(self) -> bool:
        """Whether :meth:`start` has been called successfully."""
        return self._initialized

    @property
    def provider_count(self) -> int:
        """Number of provider instances currently held."""
        return len(self._providers)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize all enabled providers from the frozen catalog.

        For each enabled provider record:
        1. ``factory.create(record)`` — constructs the adapter
        2. ``adapter.initialize()`` — synchronous setup (env vars, local files)
        3. ``adapter.validate_configuration()`` — raises if config is invalid
        4. ``adapter.start()`` — async resource acquisition (HTTP client, etc.)

        Raises:
            LLMConfigurationError: If a provider's configuration is invalid.
            LLMProviderError: If any provider raises during initialization.
        """
        if self._initialized:
            return

        if not self._catalog.frozen:
            raise LLMConfigurationError(
                "the catalog must be frozen before starting the ProviderManager. "
                "Call catalog.freeze() first."
            )

        provider_summaries = self._catalog.list_providers(enabled_only=True)
        errors: list[str] = []
        initialized: list[str] = []

        for summary in provider_summaries:
            try:
                provider = await self._initialize_provider(summary.provider_id)
                self._providers[summary.provider_id] = provider
                initialized.append(summary.provider_id)
            except Exception as e:  # noqa: BLE001
                errors.append(f"provider '{summary.provider_id}': {e}")

        if errors:
            # Attempt graceful rollback: close any providers that were
            # successfully started before the error occurred.
            await self._rollback_started(initialized)
            raise LLMProviderError(
                f"failed to initialize {len(errors)} provider(s):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        self._initialized = True

    async def stop(self) -> None:
        """Shutdown all provider instances and release their resources.

        Calls ``await provider.close()`` on every initialized provider,
        removing it from the manager's pool. Errors during close are
        logged but do not prevent remaining providers from being closed.
        """
        self._initialized = False
        for provider_id in list(self._providers.keys()):
            try:
                await self._shutdown_provider(self._providers[provider_id])
            except Exception as e:  # noqa: BLE001
                # Log but do not propagate — all providers must be attempted.
                _logger.warning(
                    "provider shutdown failed",
                    extra={
                        "provider_id": provider_id,
                        "exception_type": type(e).__name__,
                    },
                )
            finally:
                del self._providers[provider_id]

        self._providers.clear()

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator["ProviderManager"]:
        """Context manager for the full provider lifecycle.

        Usage::

            async with provider_manager.lifespan() as manager:
                provider = manager.get_provider("openai")
                ...

        Equivalent to calling ``await start()``, yielding ``self``,
        then calling ``await stop()`` on exit.
        """
        await self.start()
        try:
            yield self
        finally:
            await self.stop()

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get_provider(self, provider_id: str) -> Optional[BaseProvider]:
        """Return a provider instance by ID, or None if not initialized.

        Args:
            provider_id: The provider's stable identifier.

        Returns:
            The provider instance, or None if it was not found or not started.
        """
        return self._providers.get(provider_id)

    def get_provider_or_raise(self, provider_id: str) -> BaseProvider:
        """Return a provider instance or raise if it is not initialized.

        Args:
            provider_id: The provider's stable identifier.

        Returns:
            The provider instance.

        Raises:
            LLMProviderError: If the provider is not initialized.
        """
        provider = self._providers.get(provider_id)
        if provider is None:
            raise LLMProviderError(
                f"provider '{provider_id}' is not initialized; "
                f"call ProviderManager.start() first or use the lifespan() context manager"
            )
        return provider

    def list_providers(self) -> list[str]:
        """Return the IDs of all currently-initialized provider instances."""
        return list(self._providers.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _initialize_provider(self, provider_id: str) -> BaseProvider:
        """Construct, configure, and start a single provider.

        The full lifecycle is:
        1. Read the ProviderRecord from the frozen catalog.
        2. Construct the adapter via ``ProviderFactory.create``.
        3. Call ``adapter.initialize()``.
        4. Call ``adapter.validate_configuration()``; raise on failure.
        5. Call ``adapter.start()``.
        6. Return the ready provider.

        Raises:
            LLMConfigurationError: If the record is not in the catalog.
            LLMConfigurationError: If configuration validation fails.
            Any exception from ``start()`` propagates to the caller.
        """
        record = self._catalog.get_provider(provider_id)
        if record is None:
            raise LLMConfigurationError(
                f"provider '{provider_id}' not found in the catalog"
            )

        # 1. Construct the adapter.
        adapter = self._factory.create(record)

        # 2. Synchronous setup (env var resolution, file handles, etc.).
        if isinstance(adapter, BaseProviderRuntime):
            adapter.initialize()
        else:
            # Adapters that have not yet been migrated to BaseProviderRuntime
            # skip the initialize() step.
            pass

        # 3. Validate configuration before opening any connections.
        adapter.validate_configuration()

        # 4. Acquire async resources (HTTP client, credential refresh, etc.).
        await adapter.start()

        return adapter

    async def _shutdown_provider(self, provider: BaseProvider) -> None:
        """Close a single provider instance.

        Delegates to ``provider.close()`` if the provider implements
        :class:`BaseProviderRuntime`, otherwise performs a no-op.

        Args:
            provider: The provider to shut down.
        """
        if isinstance(provider, BaseProviderRuntime):
            await provider.close()

    async def _rollback_started(self, provider_ids: list[str]) -> None:
        """Close providers that were started before an error occurred.

        Called during rollback when ``start()`` fails partway through
        initializing the provider pool.

        Args:
            provider_ids: IDs of providers that were successfully started.
        """
        for provider_id in provider_ids:
            provider = self._providers.get(provider_id)
            if provider is not None:
                try:
                    await self._shutdown_provider(provider)
                except Exception as e:  # noqa: BLE001
                    # Log but do not propagate — rollback must attempt every
                    # provider even if some fail.
                    _logger.warning(
                        "provider rollback failed during shutdown",
                        extra={
                            "provider_id": provider_id,
                            "exception_type": type(e).__name__,
                        },
                    )
