"""Catalog Builder — builds the in-memory ModelCatalog from registry data.

The builder is the single entry point for constructing a catalog. It:

1. Loads providers and models through the registry loader.
2. Runs the validator (cross-references, duplicates, capability checks).
3. Builds the catalog from validated records.
4. Freezes the catalog (post-build, all mutation is rejected).

Authority: Decision 0014 §4.
"""

from __future__ import annotations

from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.exceptions import (
    RegistryLoadError,
    RegistryValidationError,
)
from app.intelligence.registry.loaders.registry_loader import (
    RegistryLoader,
    RegistryLoadResult,
)
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import ProviderRecord


def _extract_field(message: str) -> str:
    """Best-effort extraction of the field name from a validation message.

    The loader formats messages like ``"priority must be non-negative, got -5"``
    without an explicit field. This helper returns ``"unknown"`` for those
    cases; more specific field information is available through
    :meth:`RegistryValidator.validate_with_report`.
    """
    if "." in message:
        # If the message embeds a dotted path, take the first segment.
        return message.split()[0].rstrip(",.") or "unknown"
    return "unknown"


class CatalogBuilder:
    """Builds a ModelCatalog from registry data.

    The builder owns the loader and validator. Wiring them inside the builder
    keeps the construction sequence in one place: load → validate → build →
    freeze. Tests can inject a custom loader/validator through the constructor
    to drive the build from in-memory data.
    """

    def __init__(
        self,
        registry_loader: RegistryLoader,
    ) -> None:
        self._registry_loader = registry_loader

    # ------------------------------------------------------------------
    # Combined registry data
    # ------------------------------------------------------------------

    def build(
        self,
        providers_data: dict,
        models_data: dict,
    ) -> tuple[ModelCatalog, RegistryLoadResult]:
        """Build a ModelCatalog from registry data.

        Args:
            providers_data: Provider configuration data.
            models_data: Model configuration data.

        Raises:
            RegistryLoadError: when the underlying loader raises one. The
                builder propagates rather than swallowing so the bootstrap
                layer can fail fast.
            RegistryValidationError: when the validator finds issues. The
                builder raises the structured error directly when the loader
                did not raise.

        Returns:
            Tuple of (built catalog, load result). The catalog is frozen.
        """
        result = self._registry_loader.load(providers_data, models_data)
        return self._build_from_result(result), result

    def build_combined(
        self,
        data: dict,
    ) -> tuple[ModelCatalog, RegistryLoadResult]:
        """Build a ModelCatalog from combined registry data.

        Args:
            data: Combined configuration with 'providers' and 'models' keys.
        """
        return self.build(
            providers_data={"providers": data.get("providers", [])},
            models_data={"models": data.get("models", [])},
        )

    # ------------------------------------------------------------------
    # File paths (Phase 2 — convenience wrappers)
    # ------------------------------------------------------------------

    def build_from_paths(
        self,
        providers_path,
        models_path,
    ) -> tuple[ModelCatalog, RegistryLoadResult]:
        """Build a ModelCatalog from on-disk YAML files.

        Args:
            providers_path: Path to ``providers.yaml``.
            models_path: Path to ``models.yaml``.

        Raises:
            RegistryLoadError: when either file cannot be read, the YAML is
                malformed, or env-var resolution fails.
            RegistryValidationError: when the records fail validation.

        Returns:
            Tuple of (built catalog, load result). The catalog is frozen.
        """
        result = self._registry_loader.load_from_paths(providers_path, models_path)
        return self._build_from_result(result), result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_from_result(
        self,
        result: RegistryLoadResult,
    ) -> ModelCatalog:
        """Build (and freeze) a catalog from a loader's result.

        Raises :class:`RegistryValidationError` if the loader collected
        validation issues but did not raise. This is the single place where
        structured validation issues are converted into an exception.

        The loader tags each error with a ``<entity>/<id>`` prefix when
        it is a validation issue. That prefix lets us distinguish
        validation errors (raised as ``RegistryValidationError``) from
        load errors (raised as ``RegistryLoadError``) without changing
        the loader's external contract.
        """
        if result.errors:
            from app.intelligence.registry.exceptions import (
                LoadIssue,
                LoadReport,
                ValidationIssue,
                ValidationReport,
            )

            validation_issues: list[ValidationIssue] = []
            load_issues: list[LoadIssue] = []
            for msg in result.errors:
                # Loader-prefixed errors look like "provider/abc: ..."
                # or "model/xyz: ..." — those are validation errors.
                if ":" in msg:
                    prefix, _, rest = msg.partition(":")
                    if "/" in prefix and (
                        prefix.startswith("provider/")
                        or prefix.startswith("model/")
                    ):
                        entity_type, _, entity_id = prefix.partition("/")
                        field = _extract_field(rest)
                        validation_issues.append(
                            ValidationIssue(
                                entity_type=entity_type,
                                entity_id=entity_id,
                                field=field,
                                message=rest.strip(),
                            )
                        )
                        continue
                load_issues.append(
                    LoadIssue(
                        file_path="(unknown)",
                        position="(root)",
                        message=msg,
                    )
                )

            if validation_issues:
                raise RegistryValidationError(
                    ValidationReport(
                        issues=tuple(validation_issues),
                        warnings=tuple(result.warnings),
                    )
                )
            raise RegistryLoadError(LoadReport(issues=tuple(load_issues)))

        catalog = ModelCatalog()

        # Register providers first so the catalog's deployment index is
        # populated before the models reference it.
        for provider in result.providers:
            catalog.register_provider(provider)

        for model in result.models:
            catalog.register_model(model)

        catalog.freeze()
        return catalog


__all__ = ["CatalogBuilder"]