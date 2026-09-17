"""Provider Factory — creates, registers, and discovers provider instances.

The factory is the central registry for provider implementations.
It supports:
- Registration: Register provider constructors by type
- Construction: Create provider instances from records
- Discovery: Query available providers by capability

Provider instances are managed by ProviderManager, not the factory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Iterator, Sequence

from app.intelligence.exceptions import LLMConfigurationError
from app.intelligence.ports.base import BaseProvider
from app.intelligence.registry.types.capability import Capability

if TYPE_CHECKING:
    from app.intelligence.registry.models.provider import ProviderRecord
    from app.intelligence.registry.types.provider import ProviderType


# Type alias for provider constructor functions
ProviderConstructor = Callable[["ProviderRecord"], BaseProvider]


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    """Registration metadata for a provider type."""

    provider_type: str
    constructor: ProviderConstructor
    capabilities: frozenset[Capability] = frozenset()
    description: str = ""


class ProviderFactory:
    """Factory for creating, registering, and discovering providers.

    The factory maintains a registry of provider constructors and their
    declared capabilities. It supports:
    - Registration of provider constructors by type
    - Construction of provider instances from records
    - Discovery of providers supporting specific capabilities

    Provider instances are created by the factory but managed by
    ProviderManager. The factory itself does not own instances.

    Usage:
        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, OpenAIProvider)
        factory.register_capabilities(ProviderType.OPENAI_COMPATIBLE.value, {Capability.CHAT, Capability.EMBEDDING})

        provider = factory.create(provider_record)
    """

    def __init__(self) -> None:
        self._registrations: dict[str, ProviderRegistration] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        provider_type: str,
        constructor: ProviderConstructor,
        *,
        description: str = "",
    ) -> None:
        """Register a provider constructor.

        Args:
            provider_type: The provider type identifier (e.g., 'openai_compatible').
            constructor: Callable that creates a provider instance.
            description: Optional human-readable description.
        """
        registration = ProviderRegistration(
            provider_type=provider_type,
            constructor=constructor,
            description=description,
        )
        self._registrations[provider_type] = registration

    def register_capabilities(
        self,
        provider_type: str,
        capabilities: frozenset[Capability],
    ) -> None:
        """Register the capabilities for a provider type.

        Args:
            provider_type: The provider type identifier.
            capabilities: Set of capabilities this provider supports.

        Raises:
            LLMConfigurationError: If provider type is not registered.
        """
        if provider_type not in self._registrations:
            raise LLMConfigurationError(
                f"cannot register capabilities for unregistered provider type '{provider_type}'"
            )
        # Create new registration with capabilities (frozen dataclass)
        existing = self._registrations[provider_type]
        self._registrations[provider_type] = ProviderRegistration(
            provider_type=existing.provider_type,
            constructor=existing.constructor,
            capabilities=capabilities,
            description=existing.description,
        )

    def unregister(self, provider_type: str) -> bool:
        """Unregister a provider type.

        Args:
            provider_type: The provider type to unregister.

        Returns:
            True if the type was registered, False otherwise.
        """
        return self._registrations.pop(provider_type, None) is not None

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def create(
        self,
        record: "ProviderRecord",
        **kwargs: Any,
    ) -> BaseProvider:
        """Create a provider instance from a record.

        Args:
            record: Provider configuration record.
            **kwargs: Additional arguments passed to the constructor.

        Returns:
            A provider instance implementing BaseProvider.

        Raises:
            LLMConfigurationError: If provider type is not registered.
        """
        registration = self._registrations.get(record.provider_type.value)
        if registration is None:
            raise LLMConfigurationError(
                f"no constructor registered for provider type '{record.provider_type.value}'. "
                f"Available types: {list(self._registrations.keys())}"
            )

        provider = registration.constructor(record, **kwargs)
        return provider

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def is_registered(self, provider_type: str) -> bool:
        """Check if a provider type is registered.

        Args:
            provider_type: The provider type to check.

        Returns:
            True if the type is registered.
        """
        return provider_type in self._registrations

    def get_capabilities(self, provider_type: str) -> frozenset[Capability]:
        """Get the declared capabilities for a provider type.

        Args:
            provider_type: The provider type to query.

        Returns:
            Frozenset of capabilities, or empty frozenset if not registered.
        """
        registration = self._registrations.get(provider_type)
        if registration is None:
            return frozenset()
        return registration.capabilities

    def find_by_capability(
        self,
        capability: Capability,
    ) -> Sequence[str]:
        """Find all provider types that support a capability.

        Args:
            capability: The capability to search for.

        Returns:
            List of provider types supporting the capability.
        """
        return [
            pt
            for pt, reg in self._registrations.items()
            if capability in reg.capabilities
        ]

    def iter_registrations(
        self,
        *,
        has_capabilities: frozenset[Capability] | None = None,
    ) -> Iterator[ProviderRegistration]:
        """Iterate over provider registrations.

        Args:
            has_capabilities: If provided, only yield registrations with
                all of these capabilities.

        Yields:
            ProviderRegistration objects.
        """
        for registration in self._registrations.values():
            if has_capabilities is None:
                yield registration
            elif has_capabilities <= registration.capabilities:
                yield registration

    @property
    def registered_types(self) -> list[str]:
        """List all registered provider types."""
        return list(self._registrations.keys())

    @property
    def registration_count(self) -> int:
        """Number of registered provider types."""
        return len(self._registrations)
