"""Registry loader — coordinating loader for provider and model registries.

Orchestrates loading from multiple sources.
Validation is delegated to RegistryValidator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from app.intelligence.registry.loaders.model_loader import ModelLoader, ModelLoadResult
from app.intelligence.registry.loaders.provider_loader import ProviderLoader, ProviderLoadResult
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import ProviderRecord
from app.intelligence.registry.validators import RegistryValidator


@dataclass(frozen=True, slots=True)
class RegistryLoadResult:
    """Result of loading the complete registry."""

    providers: Sequence[ProviderRecord]
    models: Sequence[ModelRecord]
    errors: Sequence[str]
    warnings: Sequence[str]


class RegistryLoader:
    """Coordinates loading of provider and model registry data.

    Flow:
        YAML
            ↓
        Registry Loader (loads data from sources)
            ↓
        Registry Validator (validates records and cross-references)
            ↓
        Registry Objects (validated records)
            ↓
        Catalog Builder (builds in-memory catalog)
            ↓
        In-Memory Catalog

    TODO(phase-2): Add support for multiple configuration sources
    TODO(phase-2): Implement hot-reload with change detection
    TODO(phase-2): Add support for environment variable substitution
    """

    def __init__(
        self,
        provider_loader: Optional[ProviderLoader] = None,
        model_loader: Optional[ModelLoader] = None,
        validator: Optional[RegistryValidator] = None,
    ) -> None:
        self._provider_loader = provider_loader or ProviderLoader()
        self._model_loader = model_loader or ModelLoader()
        self._validator = validator or RegistryValidator()

    def load(
        self,
        providers_data: dict[str, Any],
        models_data: dict[str, Any],
    ) -> RegistryLoadResult:
        """Load and validate all registry data.

        Args:
            providers_data: Provider configuration data.
            models_data: Model configuration data.

        Returns:
            RegistryLoadResult with loaded records and any errors/warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Load providers (syntax/type validation happens here)
        provider_result = self._provider_loader.load_from_dict(providers_data)
        errors.extend(provider_result.errors)

        # Load models (syntax/type validation happens here)
        model_result = self._model_loader.load_from_dict(models_data)
        errors.extend(model_result.errors)

        # If there are load errors, skip validation (can't validate broken data)
        if errors:
            return RegistryLoadResult(
                providers=provider_result.providers,
                models=model_result.models,
                errors=errors,
                warnings=warnings,
            )

        # Semantic validation via RegistryValidator
        validation_result = self._validator.validate(
            providers=provider_result.providers,
            models=model_result.models,
        )

        # Convert validation errors to strings
        for error in validation_result.errors:
            errors.append(f"{error.entity_type}/{error.entity_id}: {error.message}")

        warnings.extend(validation_result.warnings)

        return RegistryLoadResult(
            providers=provider_result.providers,
            models=model_result.models,
            errors=errors,
            warnings=warnings,
        )

    def load_from_paths(
        self,
        providers_path,
        models_path,
        *,
        env=None,
    ) -> RegistryLoadResult:
        """Load both registries from on-disk YAML files.

        Args:
            providers_path: Path to ``providers.yaml``.
            models_path: Path to ``models.yaml``.
            env: Optional environment mapping (defaults to ``os.environ``).

        Returns:
            RegistryLoadResult with loaded records and any errors/warnings.

        Raises:
            RegistryLoadError: when either file cannot be read or the YAML
                is malformed. The error is propagated so the bootstrap
                layer can fail fast.
        """
        provider_result = self._provider_loader.load_from_yaml(providers_path, env=env)
        model_result = self._model_loader.load_from_yaml(models_path, env=env)

        errors: list[str] = list(provider_result.errors) + list(model_result.errors)
        warnings: list[str] = []

        if errors:
            return RegistryLoadResult(
                providers=provider_result.providers,
                models=model_result.models,
                errors=errors,
                warnings=warnings,
            )

        validation_result = self._validator.validate(
            providers=provider_result.providers,
            models=model_result.models,
        )

        for error in validation_result.errors:
            errors.append(f"{error.entity_type}/{error.entity_id}: {error.message}")

        warnings.extend(validation_result.warnings)

        return RegistryLoadResult(
            providers=provider_result.providers,
            models=model_result.models,
            errors=errors,
            warnings=warnings,
        )

    def load_combined(
        self,
        data: dict[str, Any],
    ) -> RegistryLoadResult:
        """Load registry data from a combined configuration.

        Args:
            data: Combined configuration with 'providers' and 'models' keys.

        Returns:
            RegistryLoadResult with loaded records.
        """
        providers_data = {"providers": data.get("providers", [])}
        models_data = {"models": data.get("models", [])}
        return self.load(providers_data, models_data)

    def validate_only(
        self,
        providers: Sequence[ProviderRecord],
        models: Sequence[ModelRecord],
    ) -> "RegistryLoadResult":
        """Validate already-loaded records without loading from source.

        Args:
            providers: Already-loaded provider records.
            models: Already-loaded model records.

        Returns:
            RegistryLoadResult with validation errors/warnings.
        """
        validation_result = self._validator.validate(
            providers=providers,
            models=models,
        )

        errors = [
            f"{error.entity_type}/{error.entity_id}: {error.message}"
            for error in validation_result.errors
        ]

        return RegistryLoadResult(
            providers=providers,
            models=models,
            errors=errors,
            warnings=list(validation_result.warnings),
        )
