"""Intelligence Layer runtime package.

Phase 2 introduces the :class:`RegistryRuntime` — the process-lifetime
owner of the in-memory :class:`ModelCatalog`. The runtime is constructed
during application bootstrap and exposes a read-only view of the catalog
to the rest of the Intelligence Layer.

Authority: Decision 0014 §4 — the catalog is a derived view; the runtime
is its owner; mutations are forbidden after ``start()``.
"""

from app.intelligence.runtime.registry_runtime import (
    RegistryRuntime,
    RegistryRuntimeSettings,
)

__all__ = [
    "RegistryRuntime",
    "RegistryRuntimeSettings",
]