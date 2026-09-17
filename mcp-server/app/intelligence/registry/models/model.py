"""Model record — immutable metadata for an LLM model.

Model Registry stores this; Catalog provides query capabilities.
Model Registry MUST NOT duplicate provider connection configuration.
"""

from dataclasses import dataclass
from typing import Optional

from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.model import ModelType


@dataclass(frozen=True, slots=True)
class ModelRecord:
    """Immutable record of a model's static configuration.

    Attributes:
        model_id: Stable identifier (e.g., 'gpt-4o', 'claude-3-5-sonnet').
        provider_id: Reference to the provider that hosts this model.
        model_type: The class/type of model.
        deployment_name: Provider-specific deployment name (may differ from model_id).
        context_window: Maximum context length in tokens. None if unknown.
        capabilities: What this model can do.
        priority: Default priority for routing (lower = higher priority).
    """

    model_id: str
    provider_id: str
    model_type: ModelType
    deployment_name: Optional[str] = None  # Provider-specific name
    context_window: Optional[int] = None  # Max tokens
    capabilities: frozenset[Capability] = frozenset()
    priority: int = 100

    # TODO(phase-2): Add validation for context_window > 0
    # TODO(phase-2): Add validation for model_id uniqueness per provider
