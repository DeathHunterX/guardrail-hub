"""Routing Strategy base — interface for routing algorithms.

Strategies determine how to select from available providers and models.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

from app.intelligence.registry.types.capability import Capability

if TYPE_CHECKING:
    pass


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Result of a routing decision."""

    provider_id: str | None
    model_id: str | None
    strategy_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class RoutingContext:
    """Context for routing decisions."""

    capability: Capability
    requested_model: str | None
    requested_provider: str | None
    metadata: dict[str, Any]


class RoutingStrategy(ABC):
    """Base class for routing strategies.

    A routing strategy decides which provider and model to use
    from a list of candidates, based on the routing context.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the strategy."""

    @abstractmethod
    def select(
        self,
        candidates: Sequence[RoutingDecision],
        context: RoutingContext,
    ) -> RoutingDecision:
        """Select the best candidate from available options.

        Args:
            candidates: Available routing options.
            context: Context for the routing decision.

        Returns:
            The selected RoutingDecision.
        """
        raise NotImplementedError

    @abstractmethod
    def get_candidates(
        self,
        context: RoutingContext,
        **kwargs: Any,
    ) -> Sequence[RoutingDecision]:
        """Get available candidates for routing.

        Args:
            context: Context for the routing decision.
            **kwargs: Additional query parameters.

        Returns:
            Sequence of RoutingDecision objects.
        """
        raise NotImplementedError
