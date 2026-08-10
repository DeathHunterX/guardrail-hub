"""Model Catalog — in-memory query layer for providers and models.

The catalog is built from Registry objects at startup and provides
efficient read-only query capabilities for the Inference Service.

This is NOT storage. It is a derived view of the registry.

Phase 2 invariants:

- After :meth:`freeze` is called, every mutating method raises
  :class:`RuntimeError`. The catalog is read-only.
- Indexes are consistent with the primary indexes at all times.
- Records returned from the catalog are the same immutable dataclass
  instances produced by the loader.

Authority: Decision 0014 §4.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterator, Optional, Sequence

from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import ProviderRecord
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.model import ModelType
from app.intelligence.registry.types.provider import ProviderType


# Maximum priority value allowed by the validator. Kept as a constant so
# callers can rely on a single source of truth for priority ranges.
MAX_PRIORITY = 100


@dataclass(frozen=True, slots=True)
class ProviderSummary:
    """Summary view of a provider for catalog queries."""

    provider_id: str
    provider_type: ProviderType
    capabilities: frozenset[Capability]
    enabled: bool
    priority: int
    deployment: DeploymentType


@dataclass(frozen=True, slots=True)
class ModelSummary:
    """Summary view of a model for catalog queries."""

    model_id: str
    provider_id: str
    model_type: ModelType
    capabilities: frozenset[Capability]
    context_window: Optional[int]
    priority: int


class CatalogFrozenError(RuntimeError):
    """Raised when a mutating method is called on a frozen catalog."""


class ModelCatalog:
    """In-memory query layer for providers and models.

    Build flow::

        catalog = ModelCatalog()
        for provider in providers:
            catalog.register_provider(provider)
        for model in models:
            catalog.register_model(model)
        catalog.freeze()  # locks the catalog

    Once frozen, every mutating method (``register_provider``,
    ``register_model``, ``clear``) raises :class:`CatalogFrozenError`.

    The catalog exposes:

    - Primary indexes: ``get_provider``, ``get_model``.
    - Secondary indexes: ``models_by_provider``, ``models_by_capability``,
      ``models_by_type``, ``models_by_deployment``, ``providers_by_capability``,
      ``providers_by_deployment``.
    - Query methods: ``list_providers``, ``list_models``,
      ``find_models_by_capability``.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderRecord] = {}
        self._models: dict[str, ModelRecord] = {}
        # Secondary indices for efficient querying.
        self._models_by_provider: dict[str, list[ModelRecord]] = {}
        self._models_by_capability: dict[Capability, list[ModelRecord]] = {}
        self._models_by_type: dict[ModelType, list[ModelRecord]] = {}
        self._models_by_deployment: dict[DeploymentType, list[ModelRecord]] = {}
        self._providers_by_capability: dict[Capability, list[ProviderRecord]] = {}
        self._providers_by_deployment: dict[DeploymentType, list[ProviderRecord]] = {}
        self._frozen: bool = False

    # ------------------------------------------------------------------
    # Freezing
    # ------------------------------------------------------------------

    def freeze(self) -> None:
        """Lock the catalog against further mutation.

        Idempotent. Once frozen, ``register_provider``, ``register_model``,
        and ``clear`` raise :class:`CatalogFrozenError`.
        """
        self._frozen = True

    @property
    def frozen(self) -> bool:
        """Whether the catalog has been frozen."""
        return self._frozen

    def _check_frozen(self) -> None:
        if self._frozen:
            raise CatalogFrozenError(
                "ModelCatalog is frozen — mutation is forbidden after build. "
                "Build a new catalog via CatalogBuilder instead."
            )

    # ------------------------------------------------------------------
    # Provider queries / registration
    # ------------------------------------------------------------------

    def register_provider(self, provider: ProviderRecord) -> None:
        """Register a provider. Overwrites if already exists."""
        self._check_frozen()
        existing = self._providers.get(provider.provider_id)
        self._providers[provider.provider_id] = provider
        for cap in provider.capabilities:
            bucket = self._providers_by_capability.setdefault(cap, [])
            if existing is not None and existing in bucket:
                bucket.remove(existing)
            if provider not in bucket:
                bucket.append(provider)
        bucket = self._providers_by_deployment.setdefault(provider.deployment, [])
        if existing is not None and existing in bucket:
            bucket.remove(existing)
        if provider not in bucket:
            bucket.append(provider)

    def get_provider(self, provider_id: str) -> Optional[ProviderRecord]:
        """Get a provider by ID."""
        return self._providers.get(provider_id)

    def list_providers(
        self,
        enabled_only: bool = True,
        provider_type: Optional[ProviderType] = None,
        deployment: Optional[DeploymentType] = None,
        capability: Optional[Capability] = None,
    ) -> Sequence[ProviderSummary]:
        """List providers with optional filtering.

        Filters compose with AND semantics. The result is sorted by priority
        ascending (lower priority value = higher preference).
        """
        providers = list(self._providers.values())
        if enabled_only:
            providers = [p for p in providers if p.enabled]
        if provider_type is not None:
            providers = [p for p in providers if p.provider_type == provider_type]
        if deployment is not None:
            providers = [p for p in providers if p.deployment == deployment]
        if capability is not None:
            providers = [p for p in providers if capability in p.capabilities]
        return [
            ProviderSummary(
                provider_id=p.provider_id,
                provider_type=p.provider_type,
                capabilities=p.capabilities,
                enabled=p.enabled,
                priority=p.priority,
                deployment=p.deployment,
            )
            for p in sorted(providers, key=lambda x: (x.priority, x.provider_id))
        ]

    def iter_providers(self) -> Iterator[ProviderRecord]:
        """Iterate over all providers."""
        return iter(tuple(self._providers.values()))

    def providers_by_capability(
        self,
        capability: Capability,
    ) -> Sequence[ProviderRecord]:
        """Return providers that support ``capability``, sorted by priority."""
        return tuple(
            sorted(
                self._providers_by_capability.get(capability, []),
                key=lambda x: (x.priority, x.provider_id),
            )
        )

    def providers_by_deployment(
        self,
        deployment: DeploymentType,
    ) -> Sequence[ProviderRecord]:
        """Return providers with a given deployment type, sorted by priority."""
        return tuple(
            sorted(
                self._providers_by_deployment.get(deployment, []),
                key=lambda x: (x.priority, x.provider_id),
            )
        )

    # ------------------------------------------------------------------
    # Model queries / registration
    # ------------------------------------------------------------------

    def register_model(self, model: ModelRecord) -> None:
        """Register a model. Overwrites if already exists."""
        self._check_frozen()
        existing = self._models.get(model.model_id)
        self._models[model.model_id] = model

        # Update provider index.
        provider_bucket = self._models_by_provider.setdefault(model.provider_id, [])
        if existing is not None and existing in provider_bucket:
            provider_bucket.remove(existing)
        if model not in provider_bucket:
            provider_bucket.append(model)

        # Update capability index.
        for cap in model.capabilities:
            cap_bucket = self._models_by_capability.setdefault(cap, [])
            if existing is not None and existing in cap_bucket:
                cap_bucket.remove(existing)
            if model not in cap_bucket:
                cap_bucket.append(model)

        # Update type index.
        type_bucket = self._models_by_type.setdefault(model.model_type, [])
        if existing is not None and existing in type_bucket:
            type_bucket.remove(existing)
        if model not in type_bucket:
            type_bucket.append(model)

        # Update deployment index (derived from the provider).
        provider = self._providers.get(model.provider_id)
        if provider is not None:
            dep_bucket = self._models_by_deployment.setdefault(provider.deployment, [])
            if existing is not None and existing in dep_bucket:
                dep_bucket.remove(existing)
            if model not in dep_bucket:
                dep_bucket.append(model)

    def get_model(self, model_id: str) -> Optional[ModelRecord]:
        """Get a model by ID."""
        return self._models.get(model_id)

    def list_models(
        self,
        provider_id: Optional[str] = None,
        capability: Optional[Capability] = None,
        model_type: Optional[ModelType] = None,
        deployment: Optional[DeploymentType] = None,
        enabled_providers_only: bool = True,
    ) -> Sequence[ModelSummary]:
        """List models with optional filtering.

        Filters compose with AND semantics. The result is sorted by priority
        ascending.
        """
        models = list(self._models.values())
        if provider_id is not None:
            models = [m for m in models if m.provider_id == provider_id]
        if capability is not None:
            models = [m for m in models if capability in m.capabilities]
        if model_type is not None:
            models = [m for m in models if m.model_type == model_type]
        if enabled_providers_only:
            enabled = {p.provider_id for p in self._providers.values() if p.enabled}
            models = [m for m in models if m.provider_id in enabled]
        if deployment is not None:
            deployment_providers = {
                p.provider_id
                for p in self._providers.values()
                if p.deployment == deployment
            }
            models = [m for m in models if m.provider_id in deployment_providers]
        return [
            ModelSummary(
                model_id=m.model_id,
                provider_id=m.provider_id,
                model_type=m.model_type,
                capabilities=m.capabilities,
                context_window=m.context_window,
                priority=m.priority,
            )
            for m in sorted(models, key=lambda x: (x.priority, x.model_id))
        ]

    def find_models_by_capability(
        self,
        capability: Capability,
        enabled_providers_only: bool = True,
    ) -> Sequence[ModelRecord]:
        """Find all models supporting a capability, sorted by priority."""
        models = list(self._models_by_capability.get(capability, []))
        if enabled_providers_only:
            enabled = {p.provider_id for p in self._providers.values() if p.enabled}
            models = [m for m in models if m.provider_id in enabled]
        return tuple(
            sorted(models, key=lambda x: (x.priority, x.model_id))
        )

    def iter_models(self) -> Iterator[ModelRecord]:
        """Iterate over all models."""
        return iter(tuple(self._models.values()))

    def models_by_provider(self, provider_id: str) -> Sequence[ModelRecord]:
        """Return models for a given provider."""
        return tuple(self._models_by_provider.get(provider_id, ()))

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all registered data. Used for testing or rebuild."""
        self._check_frozen()
        self._providers.clear()
        self._models.clear()
        self._models_by_provider.clear()
        self._models_by_capability.clear()
        self._models_by_type.clear()
        self._models_by_deployment.clear()
        self._providers_by_capability.clear()
        self._providers_by_deployment.clear()

    @property
    def is_empty(self) -> bool:
        """Check if catalog has no data."""
        return len(self._providers) == 0 and len(self._models) == 0

    # ------------------------------------------------------------------
    # Read-only views (handed to consumers that should never mutate)
    # ------------------------------------------------------------------

    @property
    def providers_view(self) -> MappingProxyType:
        """Read-only view of all providers, keyed by ``provider_id``."""
        return MappingProxyType(self._providers)

    @property
    def models_view(self) -> MappingProxyType:
        """Read-only view of all models, keyed by ``model_id``."""
        return MappingProxyType(self._models)


__all__ = [
    "ModelCatalog",
    "ModelSummary",
    "ProviderSummary",
    "CatalogFrozenError",
    "MAX_PRIORITY",
]