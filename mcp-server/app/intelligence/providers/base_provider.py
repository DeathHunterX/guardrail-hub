"""Base Provider Runtime — shared lifecycle contract for all provider adapters.

Every concrete provider adapter inherits from this class. It provides:

* ``initialize()`` — synchronous setup that runs before validation.
  Subclasses override this to resolve environment variables, open local
  resources, or otherwise prepare themselves.
* ``validate_configuration()`` — called by :class:`ProviderManager` during
  startup to confirm that all required fields are present and well-formed.
* ``start()`` — asynchronous resource acquisition. Adapters open HTTP
  clients, connection pools, and credentials here.
* ``close()`` — asynchronous graceful shutdown. Adapters flush and close
  resources here.

The ``BaseProvider`` contract (provider_id, provider_type, capabilities) is
satisfied by the concrete adapter — this class does not re-declare those
properties. Adapters inherit from both :class:`BaseProviderRuntime` and the
relevant capability ports (``ChatCapable``, ``EmbeddingCapable``, etc.).

Phase 2 contract: all providers are created exclusively by
:class:`ProviderFactory` from frozen :class:`ModelCatalog` records.
No provider is constructed outside that path.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Optional

from app.intelligence.exceptions import LLMConfigurationError
from app.intelligence.ports.base import BaseProvider

if TYPE_CHECKING:
    from app.intelligence.providers.credential import ProviderCredential
    from app.intelligence.registry.models.provider import ProviderRecord


class BaseProviderRuntime(BaseProvider):
    """Shared runtime lifecycle for all provider adapters.

    Concrete adapters inherit from this class and from the relevant
    capability ports. The four lifecycle methods are called exclusively by
    :class:`ProviderManager` during the catalog-driven bootstrap sequence.

    Subclasses MUST implement ``validate_configuration()``.
    Subclasses SHOULD override ``initialize()`` if they need synchronous
    setup. Subclasses MUST override ``start()`` and ``close()``.
    """

    # The record this adapter was constructed with. Subclasses may access
    # this during initialize / start / close to read configuration.
    _record: ProviderRecord

    # Flag set to True once start() has been called.
    _started: bool = False

    # Runtime-only authentication material. Attached by the ProviderManager
    # (via attach_credential) after construction and before initialize(), and
    # ONLY for providers whose auth.type requires a resolved secret (api_key).
    # It is None for providers that need no resolved credential (auth.type
    # none or aws). This value never enters the catalog, records, routing, or
    # chat options, and is never logged.
    _credential: "Optional[ProviderCredential]" = None

    def __init__(self, record: ProviderRecord) -> None:
        """Initialize the adapter with its configuration record.

        Subclasses that override ``__init__`` MUST call ``super().__init__(record)``.

        Args:
            record: The immutable configuration for this provider.
        """
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_started", False)
        object.__setattr__(self, "_credential", None)

    # ------------------------------------------------------------------
    # Runtime credential attachment
    # ------------------------------------------------------------------

    def attach_credential(self, credential: "ProviderCredential") -> None:
        """Attach runtime-only authentication material resolved by the bootstrap.

        Called by :class:`ProviderManager` after the adapter is constructed and
        before ``initialize()`` runs — only for providers whose ``auth.type``
        requires a resolved secret (``api_key``). The adapter reads the value
        from ``self._credential`` when it builds its authenticated client.

        The credential value is never logged; ``ProviderCredential`` masks its
        own ``repr`` / ``str``.

        Args:
            credential: The resolved credential for this provider.
        """
        object.__setattr__(self, "_credential", credential)

    # ------------------------------------------------------------------
    # Lifecycle — called by ProviderManager
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Synchronous one-time setup before validation and startup.

        Default implementation does nothing. Override to perform env-var
        resolution, open local files, or other synchronous setup that
        must occur before ``validate_configuration`` is called.

        Raises:
            LLMConfigurationError: If synchronous setup fails.
        """
        pass

    def validate_configuration(self) -> None:
        """Validate the provider's configuration.

        Called by :class:`ProviderManager` during startup, after
        ``initialize()`` and before ``start()``. The provider MUST raise
        ``LLMConfigurationError`` if any configuration value is invalid,
        missing, or inconsistent.

        Examples of what to check:
        - Required environment variables are set
        - base_url is well-formed
        - API key is not empty
        - Region identifier is valid for the provider type

        Raises:
            LLMConfigurationError: If configuration is invalid.
        """
        self._raise_unimplemented()

    async def start(self) -> None:
        """Acquire resources needed to handle requests.

        Called by :class:`ProviderManager` after ``validate_configuration``
        succeeds. Open HTTP clients, connection pools, credential refresh
        loops, or other async resources here.

        The default implementation marks the provider as started but
        acquires no resources — suitable for adapters that make no
        persistent connections.

        Raises:
            LLMConfigurationError: If a resource cannot be acquired.
        """
        object.__setattr__(self, "_started", True)

    async def close(self) -> None:
        """Release all resources acquired in ``start()``.

        Called by :class:`ProviderManager` during shutdown. Adapters that
        opened resources in ``start()`` MUST close them here. The default
        implementation is a no-op for adapters that hold no persistent
        connections.

        Errors during close SHOULD be logged but MUST NOT raise, because
        shutdown must complete even when individual providers fail.
        """
        object.__setattr__(self, "_started", False)

    @property
    def is_started(self) -> bool:
        """Whether ``start()`` has been called and ``close()`` has not yet run."""
        return self._started

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _raise_unimplemented() -> None:
        """Raise a clear error for stub methods that must be overridden."""
        raise NotImplementedError(
            "this method must be overridden by the concrete adapter"
        )

    def _require_field(self, value: object, field_name: str) -> None:
        """Assert that a required configuration field is non-None and non-empty.

        Raises:
            LLMConfigurationError: If the field is missing or empty.
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': "
                f"required field '{field_name}' is missing or empty"
            )

    def _check_started(self) -> None:
        """Raise if the provider has not been started."""
        if not self._started:
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}' has not been started; "
                f"call ProviderManager.start() first"
            )
