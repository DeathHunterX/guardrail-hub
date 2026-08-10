"""Registry Runtime — owns the in-memory catalog after startup.

The runtime is the single boundary between the registry YAML on disk and
the Intelligence Layer at runtime. It is constructed during application
bootstrap and exposed as a process-lifetime singleton. Consumers (the
Provider Manager, the Health Monitor, future routing layers) read the
catalog through ``runtime.catalog`` and never touch the YAML directly.

Contract:

- :meth:`start` is idempotent. Calling it twice raises :class:`RuntimeError`.
- After :meth:`start`, the catalog is frozen.
- :meth:`stop` releases no resources — there are none. It exists for
  parity with other runtime owners (start/stop symmetric).
- The runtime is constructed with :class:`RegistryRuntimeSettings` (paths
  + builder) so tests can inject in-memory builders.

Authority: Decision 0014 §4.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from app.intelligence.registry.builders.catalog_builder import CatalogBuilder
from app.intelligence.registry.catalog.catalog import ModelCatalog


@dataclass(frozen=True, slots=True)
class RegistryRuntimeSettings:
    """Configuration for :class:`RegistryRuntime`.

    The settings object is immutable. Tests can construct an in-memory
    variant by passing a custom ``builder`` to the runtime directly.
    """

    providers_path: Path
    models_path: Path
    require_files: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RegistryRuntimeSettings":
        """Construct from a settings dict.

        Recognised keys: ``registry_providers_path``, ``registry_models_path``,
        ``registry_require_files``. Missing optional keys default to the
        existing registry paths under ``mcp-server/config``; missing
        ``registry_require_files`` defaults to ``True``.

        Args:
            data: Settings dict.

        Returns:
            RegistryRuntimeSettings.
        """
        providers_path = Path(
            data.get("registry_providers_path")
            or "config/providers.yaml"
        )
        models_path = Path(
            data.get("registry_models_path")
            or "config/models.yaml"
        )
        require_files = bool(data.get("registry_require_files", True))
        return cls(
            providers_path=providers_path,
            models_path=models_path,
            require_files=require_files,
        )


class RegistryRuntime:
    """Process-lifetime owner of the in-memory registry catalog.

    The runtime owns exactly one :class:`ModelCatalog`. The catalog is
    constructed once at :meth:`start` and frozen. The runtime itself
    exposes the catalog through ``self.catalog``.

    The runtime does not own provider instances, conversations, or health
    signals — those bounded contexts read the catalog through this runtime
    and never bypass it.
    """

    def __init__(
        self,
        settings: RegistryRuntimeSettings,
        builder: Optional[CatalogBuilder] = None,
    ) -> None:
        self._settings = settings
        self._builder = builder
        self._catalog: Optional[ModelCatalog] = None
        self._started: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def catalog(self) -> ModelCatalog:
        """The in-memory catalog (read-only).

        Raises:
            RuntimeError: if accessed before :meth:`start`.
        """
        if self._catalog is None:
            raise RuntimeError(
                "RegistryRuntime has not been started; call start() first"
            )
        return self._catalog

    @property
    def started(self) -> bool:
        """Whether :meth:`start` has been called."""
        return self._started

    @property
    def settings(self) -> RegistryRuntimeSettings:
        """The runtime's immutable settings."""
        return self._settings

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> ModelCatalog:
        """Build the catalog from disk (or in-memory data) and freeze it.

        Idempotent only in the sense that double-start raises. The catalog
        is built exactly once per process.

        Raises:
            RuntimeError: when called twice.
            RegistryLoadError: when the YAML cannot be read or parsed.
            RegistryValidationError: when the records fail validation.
            FileNotFoundError: when ``require_files`` is True and the
                paths are missing.

        Returns:
            The built and frozen catalog.
        """
        if self._started:
            raise RuntimeError(
                "RegistryRuntime is already started; the catalog is immutable"
            )

        # When a builder is injected (typically by tests), use it
        # unconditionally. This bypasses the file-existence check so a
        # custom builder can supply its own data source.
        if self._builder is not None:
            catalog, _result = self._builder.build_from_paths(
                self._settings.providers_path,
                self._settings.models_path,
            )
            self._catalog = catalog
            self._started = True
            return catalog

        # File-existence fast path (default builder only).
        if not self._settings.providers_path.exists():
            if self._settings.require_files:
                raise FileNotFoundError(
                    f"Registry providers file not found: "
                    f"{self._settings.providers_path}"
                )
            self._catalog = ModelCatalog()
            self._catalog.freeze()
            self._started = True
            return self._catalog

        if not self._settings.models_path.exists():
            if self._settings.require_files:
                raise FileNotFoundError(
                    f"Registry models file not found: "
                    f"{self._settings.models_path}"
                )
            self._catalog = ModelCatalog()
            self._catalog.freeze()
            self._started = True
            return self._catalog

        builder = CatalogBuilder(
            registry_loader=_default_registry_loader()
        )

        catalog, _result = builder.build_from_paths(
            self._settings.providers_path,
            self._settings.models_path,
        )
        self._catalog = catalog
        self._started = True
        return catalog

    def stop(self) -> None:
        """Release any held resources (none, in Phase 2).

        Provided for parity with the rest of the application runtime
        (start/stop symmetric). Currently a no-op.
        """
        # Nothing to release — the catalog is immutable and holds no
        # external resources. Kept for future phases (hot-reload, SDK
        # lifetime, etc.).
        return None


def _default_registry_loader():
    """Construct the default :class:`RegistryLoader`.

    Imported lazily so the runtime module does not pull the registry
    package at import time.
    """
    from app.intelligence.registry.loaders.registry_loader import RegistryLoader

    return RegistryLoader()


__all__ = [
    "RegistryRuntime",
    "RegistryRuntimeSettings",
]