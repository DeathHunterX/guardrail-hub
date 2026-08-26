"""Registry Context — static metadata for providers and models.

Contains:
- Provider Registry: Provider connection configuration and metadata
- Model Registry: Model capabilities, context windows, and priorities
- Registry Loader: Loads registry data from configuration sources
- Registry Validator: Validates registry data (separate from loading)
- Catalog Builder: Builds the in-memory query layer
- Model Catalog: In-memory query interface for providers and models

Model Registry MUST NOT duplicate provider connection configuration.
Model Catalog is NOT storage — it is an in-memory query layer.
"""

from app.intelligence.registry.builders import CatalogBuilder
from app.intelligence.registry.catalog import ModelCatalog
from app.intelligence.registry.exceptions import (
    LoadIssue,
    LoadReport,
    RegistryLoadError,
    RegistryValidationError,
    ValidationIssue,
    ValidationReport,
)
from app.intelligence.registry.loaders import (
    LLmConfigLoader,
    LLmConfigLoadResult,
)
from app.intelligence.registry.models import ModelRecord, ProviderRecord
from app.intelligence.registry.resolver import EnvironmentResolver, ResolvedString
from app.intelligence.registry.types import (
    Capability,
    DeploymentType,
    ModelType,
    ProviderType,
)
from app.intelligence.registry.validators import (
    RegistryValidator,
)

__all__ = [
    # Types
    "Capability",
    "DeploymentType",
    "ModelType",
    "ProviderType",
    # Models
    "ModelRecord",
    "ProviderRecord",
    # Catalog
    "ModelCatalog",
    # Loaders
    "LLmConfigLoader",
    "LLmConfigLoadResult",
    # Builders
    "CatalogBuilder",
    # Validators
    "RegistryValidator",
    # Exceptions
    "LoadIssue",
    "LoadReport",
    "ValidationIssue",
    "ValidationReport",
    "RegistryLoadError",
    "RegistryValidationError",
    # Resolver
    "EnvironmentResolver",
    "ResolvedString",
]
