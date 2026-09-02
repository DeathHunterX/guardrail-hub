"""Router — routes LLM requests to appropriate providers.

The router makes routing decisions based on:
- Requested capability (chat, embedding, vision, etc.)
- Requested model or provider
- Available models and their capabilities
- The configured routing strategy

Authority: ADR-0014 §5 (model-centric routing), ADR-0016 (Inference Policy).
"""

from typing import TYPE_CHECKING, Any, Optional

from app.intelligence.exceptions import LLMModelNotFoundError, LLMProviderError
from app.intelligence.inference.strategies.base import RoutingContext, RoutingDecision, RoutingStrategy
from app.intelligence.ports.base import BaseProvider
from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.types.capability import Capability

if TYPE_CHECKING:
    from app.intelligence.providers.provider_manager import ProviderManager


class Router:
    """Routes LLM requests to appropriate providers.

    The router is the bridge between the public capability request
    (capability X) and the concrete (provider_id, model_id) pair.

    Routing is **model-centric**: the router asks "which model supports
    this capability?" first, and "which provider hosts that model?" second.
    This is enforced by ADR-0014 §5.

    The router never creates providers or calls inference. It returns a
    decision; the caller resolves the decision to a provider instance.
    """

    def __init__(
        self,
        catalog: ModelCatalog,
        default_strategy: Optional[RoutingStrategy] = None,
    ) -> None:
        """Construct the router.

        Args:
            catalog: The frozen model catalog. Used for candidate discovery.
            default_strategy: The routing strategy to use when no explicit
                model or provider is specified. If None, a
                :class:`.PriorityStrategy` is constructed internally.
        """
        self._catalog = catalog
        self._default_strategy = default_strategy

    def route(
        self,
        capability: Capability,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs: Any,
    ) -> RoutingDecision:
        """Determine which provider and model to use for a request.

        Resolution order:

        1. **Explicit model + capability** — validate the named model
           exists and supports the capability. Return the decision immediately.
        2. **Explicit model, no capability check** — validate the model
           exists. Return the decision.
        3. **Explicit provider, no model** — find all models on the named
           provider that support the capability. Pass to the strategy
           for selection.
        4. **Capability only** — get all capable models from the catalog,
           pass to the strategy for selection.

        Args:
            capability: The required LLM capability.
            model: Explicit model_id requested. If None, the router
                selects the best model from the capable set.
            provider: Explicit provider_id requested. If None, the
                router selects the best provider from the capable set.
            **kwargs: Additional routing hints. ``excluded_provider_ids`` may
                remove unavailable providers from implicit candidate selection.

        Returns:
            RoutingDecision with the selected (provider_id, model_id).

        Raises:
            LLMModelNotFoundError: If a named model does not exist in
                the catalog, or if no capable models are found and no
                strategy fallback is available.
            LLMProviderError: If a named provider has no capable model
                for the requested capability.
        """
        strategy = self._default_strategy
        excluded_provider_ids = frozenset(kwargs.pop("excluded_provider_ids", ()))

        # Path 1 & 2: explicit model requested.
        if model is not None:
            return self._route_for_model(model, capability, provider, strategy)

        # Path 3: explicit provider requested.
        if provider is not None:
            return self._route_for_provider(provider, capability, strategy)

        # Path 4: capability only — delegate to the strategy.
        context = RoutingContext(
            capability=capability,
            requested_model=None,
            requested_provider=None,
            metadata=kwargs,
        )
        candidates = [
            candidate
            for candidate in strategy.get_candidates(context)
            if candidate.provider_id not in excluded_provider_ids
        ]
        decision = strategy.select(candidates, context)
        if decision.provider_id is None:
            raise LLMModelNotFoundError(
                f"no capable model found for capability '{capability.value}'"
            )
        return decision

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _route_for_model(
        self,
        model_id: str,
        capability: Capability,
        provider_hint: Optional[str],
        strategy: Optional[RoutingStrategy],
    ) -> RoutingDecision:
        """Resolve a decision when a specific model is requested."""
        model_record = self._catalog.get_model(model_id)
        if model_record is None:
            raise LLMModelNotFoundError(
                f"model '{model_id}' not found in the catalog"
            )

        # Validate capability.
        if capability not in model_record.capabilities:
            raise LLMModelNotFoundError(
                f"model '{model_id}' does not support capability "
                f"'{capability.value}'; supported: "
                f"{', '.join(c.value for c in sorted(model_record.capabilities))}"
            )

        provider_id = model_record.provider_id

        # If a provider was also specified, verify it matches.
        if provider_hint is not None and provider_hint != provider_id:
            raise LLMProviderError(
                f"model '{model_id}' is hosted by provider '{provider_id}', "
                f"not '{provider_hint}'"
            )

        return RoutingDecision(
            provider_id=provider_id,
            model_id=model_id,
            strategy_name="explicit_model",
            reason=f"model '{model_id}' explicitly requested",
        )

    def _route_for_provider(
        self,
        provider_id: str,
        capability: Capability,
        strategy: Optional[RoutingStrategy],
    ) -> RoutingDecision:
        """Resolve a decision when a specific provider is requested."""
        provider_record = self._catalog.get_provider(provider_id)
        if provider_record is None:
            raise LLMModelNotFoundError(
                f"provider '{provider_id}' not found in the catalog"
            )
        if not provider_record.enabled:
            raise LLMProviderError(f"provider '{provider_id}' is not enabled")

        # Filter models on this provider that support the capability.
        all_models = self._catalog.find_models_by_capability(
            capability, enabled_providers_only=True
        )
        candidates = [
            m for m in all_models if m.provider_id == provider_id
        ]

        if not candidates:
            raise LLMProviderError(
                f"provider '{provider_id}' has no model with capability "
                f"'{capability.value}'"
            )

        # Convert ModelRecord candidates to RoutingDecision for the strategy.
        decisions = [
            RoutingDecision(
                provider_id=m.provider_id,
                model_id=m.model_id,
                strategy_name="explicit_provider",
                reason=(
                    f"model '{m.model_id}' on explicit provider '{provider_id}'"
                ),
            )
            for m in candidates
        ]

        context = RoutingContext(
            capability=capability,
            requested_model=None,
            requested_provider=provider_id,
            metadata={},
        )

        if strategy is not None:
            decision = strategy.select(decisions, context)
        else:
            # No strategy — return the first candidate deterministically.
            decision = min(decisions, key=lambda d: d.model_id or "")

        if decision.provider_id is None:
            raise LLMModelNotFoundError(
                f"provider '{provider_id}' has no capable model for "
                f"capability '{capability.value}'"
            )
        return decision

    def validate_model_capability(
        self,
        model_id: str,
        capability: Capability,
    ) -> bool:
        """Check if a model supports a given capability.

        Args:
            model_id: The model to check.
            capability: The required capability.

        Returns:
            True if the model supports the capability; False otherwise.
        """
        model = self._catalog.get_model(model_id)
        if model is None:
            return False
        return capability in model.capabilities
