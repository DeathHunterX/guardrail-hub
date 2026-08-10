"""Base provider interface — common contract for all LLM providers.

All provider implementations must satisfy this interface.
Capability-specific behavior is defined in dedicated ports.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.intelligence.registry.types.capability import Capability


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Common configuration shared by all providers.

    Provider-specific configuration extends this with additional fields.
    """

    provider_id: str
    timeout_seconds: float = 60.0
    max_retries: int = 3
    base_url: Optional[str] = None


class BaseProvider(ABC):
    """Base contract for all LLM providers.

    All providers must implement this interface. Specific capabilities
    (chat, embedding, etc.) are defined in dedicated ports that
    providers can additionally implement.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable identifier for this provider instance."""

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider type identifier (e.g., 'openai', 'anthropic', 'ollama')."""

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[Capability]:
        """Set of capabilities this provider supports."""

    @abstractmethod
    def validate_configuration(self) -> None:
        """Validate provider configuration at startup.

        Raises:
            LLMConfigurationError: If configuration is invalid.
        """
