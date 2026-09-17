"""Health check capability port — provider availability monitoring."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.intelligence.registry.types.capability import Capability


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """Result of a health check."""

    provider_id: str
    healthy: bool
    latency_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: Optional[str] = None
    error_type: Optional[str] = None


class HealthCheckable(ABC):
    """Contract for provider health monitoring.

    Providers implementing this port can be health-checked.
    """

    @property
    def capability(self) -> Capability:
        return Capability.HEALTH

    @abstractmethod
    async def check_health(self) -> HealthStatus:
        """Perform a health check on this provider.

        Returns:
            HealthStatus indicating provider health.

        Raises:
            LLMProviderError: If health check fails unexpectedly.
        """

    @abstractmethod
    async def check_model_health(self, model_id: str) -> HealthStatus:
        """Check health of a specific model.

        Args:
            model_id: The model to check.

        Returns:
            HealthStatus indicating model health.

        Raises:
            LLMModelNotFoundError: If model is not found.
            LLMProviderError: If health check fails unexpectedly.
        """
