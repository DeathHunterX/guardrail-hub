"""Priority Strategy — deployment-preference then model-priority routing.

Implements ADR-0016 (Inference Policy) §2.2.

Selection order:
  1. Deployment preference  — self-hosted > local > proxy > cloud
  2. Model priority        — lower numeric value = higher preference
  3. Stable tie-break      — model_id lexicographic sort

The strategy is deterministic, reproducible, and has no randomness,
no mutation, and no caching. It is the default strategy for Phase 4.

Algorithmic complexity
----------------------
``get_candidates()`` — O(N) where N = total models with the requested
capability across all enabled providers. Uses the catalog's secondary index
(``_models_by_capability``), which is a dict get: O(1) average.

``select()`` — O(N log N) sort over N candidate decisions, where N is
bounded by the number of capable models returned by ``get_candidates()``.
Uses ``sorted()`` (non-mutating). The catalog-owned candidate collection
is never modified.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from app.intelligence.inference.strategies.base import RoutingContext, RoutingDecision, RoutingStrategy
from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType

if TYPE_CHECKING:
    pass


# Deployment preference order: lower index = higher priority.
# ADR-0016 §2.2: self-hosted-first policy.
_DEPLOYMENT_ORDER: dict[DeploymentType, int] = {
    DeploymentType.SELF_HOSTED: 0,
    DeploymentType.LOCAL: 1,
    DeploymentType.PROXY: 2,
    DeploymentType.CLOUD: 3,
}


class PriorityStrategy(RoutingStrategy):
    """Deployment-preference + model-priority routing strategy.

    Candidates are sorted by:
      1. Deployment preference (self-hosted first)
      2. Model priority (lower value = higher preference)
      3. model_id (lexicographic, stable tie-break)

    No randomness. No mutation. No caching.
    """

    def __init__(self, catalog: ModelCatalog) -> None:
        """Construct the strategy.

        Args:
            catalog: The frozen model catalog used for candidate discovery.
        """
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "priority"

    def get_candidates(
        self,
        context: RoutingContext,
        **kwargs: object,
    ) -> Sequence[RoutingDecision]:
        """Return all candidate routing decisions for the given capability.

        Queries the catalog for all enabled models that support the
        requested capability. Returns a :class:`RoutingDecision` per
        candidate model.

        Args:
            context: Carries the requested :attr:`RoutingContext.capability`.
            **kwargs: Accepted but ignored in this strategy.

        Returns:
            Sequence of RoutingDecision objects, one per candidate model.
            Never empty — the caller is responsible for handling an empty
            result.
        """
        candidates = self._catalog.find_models_by_capability(
            context.capability,
            enabled_providers_only=True,
        )
        return [
            RoutingDecision(
                provider_id=model.provider_id,
                model_id=model.model_id,
                strategy_name=self.name,
                reason=(
                    f"capability={context.capability.value}; "
                    f"deployment={model.provider_id} resolved at startup"
                ),
            )
            for model in candidates
        ]

    def select(
        self,
        candidates: Sequence[RoutingDecision],
        context: RoutingContext,
    ) -> RoutingDecision:
        """Select the best candidate from the provided set.

        Sorts by deployment preference (self-hosted > local > proxy > cloud),
        then by model priority (lower = higher preference), then by model_id
        lexicographically for a stable tie-break.

        Args:
            candidates: Pre-filtered candidate RoutingDecision objects.
                Typically the output of :meth:`get_candidates`.
            context: Routing context (not used in this strategy).

        Returns:
            The selected RoutingDecision, or a decision with
            ``provider_id=None`` if the candidate set is empty.

        Raises:
            ValueError: Never raised. Empty candidates produce a
                ``provider_id=None`` decision instead.
        """
        if not candidates:
            return RoutingDecision(
                provider_id=None,
                model_id=None,
                strategy_name=self.name,
                reason="no candidate models available for the requested capability",
            )

        # Build a lookup from provider_id -> ProviderRecord for deployment info.
        # The catalog is frozen and the lookup is a dict get — O(1) per candidate.
        provider_map = {p.provider_id: p for p in self._catalog.iter_providers()}

        def sort_key(decision: RoutingDecision) -> tuple[int, int, str]:
            provider = provider_map.get(decision.provider_id)
            deployment_order = (
                _DEPLOYMENT_ORDER.get(provider.deployment, 99)
                if provider is not None
                else 99
            )
            model_record = self._catalog.get_model(decision.model_id)
            priority = getattr(model_record, "priority", 999) if model_record else 999
            return (deployment_order, priority, decision.model_id or "")

        sorted_candidates = sorted(candidates, key=sort_key)
        return sorted_candidates[0]
