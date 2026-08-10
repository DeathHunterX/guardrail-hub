"""Provider record — immutable metadata for an LLM provider.

This is static configuration data, not runtime state.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


@dataclass(frozen=True, slots=True)
class AuthConfig:
    """Authentication configuration for a provider.

    Actual secrets should come from environment variables or a secrets manager,
    not from the registry configuration file.
    """

    api_key_env: Optional[str] = None  # Environment variable name for API key
    api_key: Optional[str] = None  # Direct API key (not recommended for production)
    auth_header: Optional[str] = None  # Custom auth header name
    additional_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    """Network and connection configuration for a provider."""

    base_url: str
    timeout_seconds: float = 60.0
    max_retries: int = 3
    verify_ssl: bool = True
    proxy_url: Optional[str] = None
    ca_bundle: Optional[str] = None  # Path to CA certificate bundle


@dataclass(frozen=True, slots=True)
class ProviderRecord:
    """Immutable record of a provider's static configuration.

    Provider Registry stores this; Model Registry references it via provider_id.
    Model Registry MUST NOT duplicate provider connection configuration.

    Attributes:
        provider_id: Stable identifier (e.g., 'openai', 'anthropic-ollama').
        provider_type: The vendor/category of provider.
        deployment: How/where the provider is deployed.
        auth: Authentication configuration (secrets reference env vars).
        connection: Network and connection settings.
        capabilities: What this provider can do (set from factory or models).
            Stored as frozenset for immutability.
        enabled: Whether this provider is active.
        priority: Default priority when multiple providers support a capability.
        metadata: Provider-specific additional data.
    """

    provider_id: str
    provider_type: ProviderType
    deployment: DeploymentType
    auth: AuthConfig
    connection: ConnectionConfig
    capabilities: frozenset[Capability] = frozenset()
    enabled: bool = True
    priority: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)
