"""Registry catalog — in-memory query layer over provider and model registries.

The catalog is NOT storage. It is built from Registry objects at startup
and provides query capabilities for the Inference Service.
"""

from app.intelligence.registry.catalog.catalog import (
    MAX_PRIORITY,
    CatalogFrozenError,
    ModelCatalog,
    ModelSummary,
    ProviderSummary,
)

__all__ = [
    "ModelCatalog",
    "ModelSummary",
    "ProviderSummary",
    "CatalogFrozenError",
    "MAX_PRIORITY",
]