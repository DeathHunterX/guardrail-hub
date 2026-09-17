"""Registry Runtime — owns the in-memory catalog after startup.

The runtime is the single boundary between the unified llm.yaml on disk and
the Intelligence Layer at runtime. It is constructed during application
bootstrap and exposed as a process-lifetime singleton. Consumers (the
Provider Manager, the Health Monitor, future routing layers) read the
catalog through ``runtime.catalog`` and never touch the YAML directly.

Contract:

- :meth:`start` is idempotent. Calling it twice raises :class:`RuntimeError`.
- After :meth:`start`, the catalog is frozen.
- :meth:`stop` releases no resources — there are none. It exists for
  parity with other runtime owners (start/stop symmetric).
- The runtime is constructed with :class:`RegistryRuntimeSettings` so
  tests can inject an in-memory builder result.

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
    variant by passing a pre-built catalog to the runtime directly.
    """

    # Path to the unified llm.yaml configuration file.
    llm_config_path: Path

    # When True (default), the runtime fails fast at startup if the
    # config file is missing. When False, an empty catalog is built
    # (useful for local dev where LLM work isn't enabled yet).
    require_files: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RegistryRuntimeSettings":
        """Construct from a settings dict.

        Recognised keys:
        - ``registry_llm_config_path``: Path to unified llm.yaml (required).
        - ``registry_require_files``: Whether to fail fast on missing file.

        Args:
            data: Settings dict.

        Returns:
            RegistryRuntimeSettings.

        Raises:
            ValueError: if ``registry_llm_config_path`` is not provided.
        """
        llm_path = data.get("registry_llm_config_path")
        if not llm_path:
            raise ValueError(
                "registry_llm_config_path is required; "
                "the unified llm.yaml is the single source of truth"
            )
        return cls(
            llm_config_path=Path(llm_path),
            require_files=bool(data.get("registry_require_files", True)),
        )

    @classmethod
    def from_llm_yaml(cls, path: Path | str, *, require_files: bool = True) -> "RegistryRuntimeSettings":
        """Convenience constructor for the common case: load one llm.yaml path.

        Args:
            path: Path to llm.yaml.
            require_files: Whether to fail fast when the file is absent.

        Returns:
            RegistryRuntimeSettings.
        """
        return cls(
            llm_config_path=Path(path),
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
        catalog: Optional[ModelCatalog] = None,
    ) -> None:
        self._settings = settings
        # Optional pre-built catalog (injected by tests; None in production).
        self._injected_catalog: Optional[ModelCatalog] = catalog
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
        """Build the catalog from disk and freeze it.

        Idempotent only in the sense that double-start raises. The catalog
        is built exactly once per process.

        Raises:
            RuntimeError: when called twice.
            RegistryLoadError: when the YAML cannot be read or parsed.
            RegistryValidationError: when the records fail validation.
            FileNotFoundError: when ``require_files`` is True and the
                path is missing.

        Returns:
            The built and frozen catalog.
        """
        if self._started:
            raise RuntimeError(
                "RegistryRuntime is already started; the catalog is immutable"
            )

        # Test injection path: pre-built catalog supplied at construction time.
        if self._injected_catalog is not None:
            self._catalog = self._injected_catalog
            self._started = True
            return self._catalog

        # Production path: load from llm.yaml.
        self._catalog = self._load_from_llm_yaml()
        self._started = True
        return self._catalog

    # ------------------------------------------------------------------
    # Internal — load
    # ------------------------------------------------------------------

    def _load_from_llm_yaml(self) -> ModelCatalog:
        """Load the unified llm.yaml and build the frozen catalog.

        Raises:
            FileNotFoundError: when require_files is True and the path is missing.
            RegistryLoadError: when YAML parsing or env-var resolution fails.
            RegistryValidationError: when records fail validation.
        """
        path = self._settings.llm_config_path

        if not path.exists():
            if self._settings.require_files:
                raise FileNotFoundError(f"Registry config file not found: {path}")
            catalog = ModelCatalog()
            catalog.freeze()
            return catalog

        # Import here to avoid circular imports at module load time.
        from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoader
        from app.intelligence.registry.exceptions import (
            LoadIssue,
            LoadReport,
            RegistryLoadError,
        )

        loader = LLmConfigLoader()
        result = loader.load(path)

        if result.errors:
            raise RegistryLoadError(
                LoadReport(
                    issues=tuple(
                        LoadIssue(
                            file_path=str(path),
                            position="(root)",
                            message=e,
                        )
                        for e in result.errors
                    )
                )
            )

        # Always use CatalogBuilder so validation runs.
        builder = CatalogBuilder()
        catalog, _, _ = builder.build_from_llm_config_result(result)
        return catalog

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Release any held resources (none, in Phase 2).

        Provided for parity with the rest of the application runtime
        (start/stop symmetric). Currently a no-op.
        """
        return None


__all__ = [
    "RegistryRuntime",
    "RegistryRuntimeSettings",
]
