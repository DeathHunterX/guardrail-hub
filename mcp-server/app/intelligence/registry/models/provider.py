"""Provider record — immutable metadata for an LLM provider.

This is static configuration data, not runtime state.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


class AuthType(str, Enum):
    """Supported authentication types for LLM providers.

    Each value declares HOW a provider authenticates — not the secret itself.
    The actual credential is obtained by the selected runtime backend. For an
    API-key provider, ``api_key_env`` is only the environment locator used by
    the explicit env backend; it is never the secret value or storage policy.

    Attributes:
        API_KEY:   Provider uses a bearer / API key. ``auth.api_key_env`` is
                   locator metadata for env-mode resolution, never a directive
                   to persist a value in an environment file.
        AWS:       Provider uses AWS credentials (access key + secret, or IAM
                   role). Region is declared in connection.region. Credentials
                   come from the standard AWS SDK credential chain (env vars,
                   config file, or IAM role).
        NONE:      No authentication required (e.g., local Ollama without auth).
                   Explicitly declaring ``type: none`` is optional but preferred.
    """

    API_KEY = "api_key"  # Bearer / API-key auth
    AWS = "aws"  # AWS SDK credential chain
    NONE = "none"  # No authentication required


# Sentinel object used to distinguish "auth.type absent from YAML" from
# "auth.type explicitly set to api_key" when AuthConfig is constructed.
# The loader sets auth.type to this sentinel when the field is absent;
# the validator uses it to skip the api_key_env requirement for configs
# that omit auth.type entirely (Phase 1 backward compatibility).
AUTH_TYPE_DEFAULT_SENTINEL = object()


# Union of the actual type plus the sentinel.
# ProviderRecord.auth.type is typed as AuthType only (not the sentinel);
# the sentinel is stored transiently during the load → validate round-trip.
AuthTypeField = Union[AuthType, object]


@dataclass(frozen=True, slots=True)
class AuthConfig:
    """Authentication configuration for a provider.

    Describes HOW authentication works — the actual secret value must NOT
    be stored in the registry configuration file (llm.yaml).

    The ``type`` field is the primary declaration. When ``type`` is absent
    from the YAML (Phase 1 backward compatibility), it is set to the
    ``AUTH_TYPE_DEFAULT_SENTINEL`` sentinel value. The validator checks for
    this sentinel to decide whether to require ``api_key_env``.
    """

    # Primary auth type declaration.
    # Set to an AuthType value when declared in YAML.
    # Set to AUTH_TYPE_DEFAULT_SENTINEL when the field is absent from the YAML,
    # including when AuthConfig is constructed with its class-level defaults.
    type: AuthTypeField = AUTH_TYPE_DEFAULT_SENTINEL

    # Environment credential locator used only when the explicit env backend
    # is selected. Optional for AuthType.API_KEY: the env backend derives the
    # ADR-0017 fallback name when absent. Unused for AWS/NONE. The actual
    # value must NOT appear in llm.yaml or be persisted by setup.
    api_key_env: Optional[str] = None

    # Custom auth header name (e.g. "X-API-Key"). Optional.
    auth_header: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    """Network and connection configuration for a provider.

    Attributes:
        base_url: The base URL for the provider API. Required for most providers
            (OpenAI, Ollama, OpenAI-compatible). Not used for AWS Bedrock.
        region: AWS region for Bedrock providers. When set, the adapter constructs
            the Bedrock endpoint from the region; base_url is not required.
    """

    base_url: str = ""
    region: Optional[str] = None  # AWS region (Bedrock)


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
    """

    provider_id: str
    provider_type: ProviderType
    deployment: DeploymentType
    auth: AuthConfig
    connection: ConnectionConfig
    capabilities: frozenset[Capability] = frozenset()
    enabled: bool = True
    priority: int = 100
