"""Catalog Builder — builds the in-memory ModelCatalog from registry data.

The builder is the single entry point for constructing a catalog. It:

1. Loads providers and models from an ``LLmConfigLoadResult``.
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
from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoadResult
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import ProviderRecord


class CatalogBuilder:
    """Builds a ModelCatalog from the unified llm.yaml configuration.

    The builder owns no loader — it accepts an :class:`LLmConfigLoadResult`
    which is produced by :class:`LLmConfigLoader`. Wiring them separately keeps
    each class focused: the loader parses YAML, the builder assembles the catalog.

    The ``build_from_llm_config_result`` method is the single canonical path
    for catalog construction. All other build paths have been removed.
    """

    def build_from_llm_config_result(
        self,
        llm_config_result: LLmConfigLoadResult,
    ) -> tuple[ModelCatalog, tuple[str, ...], tuple[str, ...]]:
        """Build a ModelCatalog from a unified LLmConfigLoadResult.

        The result already contains normalized ProviderRecord[] + ModelRecord[].
        This method runs the validator and builds the catalog.

        Args:
            llm_config_result: Result from LLmConfigLoader.load() or load_from_dict().

        Returns:
            Tuple of (built catalog, errors tuple, warnings tuple).
            The catalog is frozen.

        Raises:
            RegistryValidationError: When the records fail validation.
            RegistryLoadError: When the loader collected structural errors.
        """
        from app.intelligence.registry.exceptions import (
            LoadIssue,
            LoadReport,
            ValidationIssue,
            ValidationReport,
        )
        from app.intelligence.registry.validators.registry_validator import (
            RegistryValidator,
        )

        # Run semantic validation.
        validator = RegistryValidator()
        validation_result = validator.validate(
            providers=llm_config_result.providers,
            models=llm_config_result.models,
        )

        all_errors: list[str] = list(llm_config_result.errors)
        validation_issues: list[ValidationIssue] = []
        warnings: list[str] = list(validation_result.warnings)

        for error in validation_result.errors:
            validation_issues.append(
                ValidationIssue(
                    entity_type=error.entity_type,
                    entity_id=error.entity_id,
                    field=error.field,
                    message=error.message,
                )
            )
            all_errors.append(
                f"{error.entity_type}/{error.entity_id}: {error.message}"
            )

        if validation_issues:
            raise RegistryValidationError(
                ValidationReport(
                    issues=tuple(validation_issues),
                    warnings=tuple(warnings),
                )
            )

        if all_errors:
            raise RegistryLoadError(
                LoadReport(
                    issues=tuple(
                        LoadIssue(
                            file_path="llm.yaml",
                            position="(root)",
                            message=e,
                        )
                        for e in all_errors
                    )
                )
            )

        catalog = ModelCatalog()

        # Register providers first so the catalog's deployment index is
        # populated before the models reference it.
        for provider in llm_config_result.providers:
            catalog.register_provider(provider)

        for model in llm_config_result.models:
            catalog.register_model(model)

        catalog.freeze()

        return catalog, tuple(all_errors), tuple(warnings)


__all__ = ["CatalogBuilder"]
