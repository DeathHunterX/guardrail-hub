"""Registry Validator — validates provider and model records.

Validation is separate from loading to ensure:
1. Load errors (syntax, type) are distinct from validation errors
2. Validation can be run independently of loading
3. Different validators can be composed for different contexts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Sequence

from app.intelligence.registry.exceptions import ValidationIssue, ValidationReport
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import ProviderRecord


@dataclass(frozen=True, slots=True)
class ValidationError:
    """A single validation error."""

    entity_type: str  # 'provider' or 'model'
    entity_id: str
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class RegistryValidationResult:
    """Result of registry validation."""

    valid: bool
    errors: Sequence[ValidationError] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


class RegistryValidationError(Exception):
    """Raised when registry validation fails."""

    def __init__(self, result: RegistryValidationResult) -> None:
        self.result = result
        messages = [f"{e.entity_type}/{e.entity_id}: {e.message}" for e in result.errors]
        super().__init__(f"Registry validation failed with {len(messages)} error(s):\n" + "\n".join(f"  - {m}" for m in messages))


class RegistryValidator:
    """Validates provider and model records.

    Performs cross-reference validation between providers and models.
    Validation is separate from loading - load errors are syntax/type errors,
    validation errors are semantic/business rule errors.

    TODO(phase-2): Add schema validation against JSON Schema
    TODO(phase-2): Add custom validator plugin support
    TODO(phase-2): Add validation for pricing/cost metadata
    """

    def validate_providers(
        self,
        providers: Sequence[ProviderRecord],
    ) -> Iterator[ValidationError]:
        """Validate provider records.

        Args:
            providers: Provider records to validate.

        Yields:
            ValidationError for each invalid record.
        """
        seen_ids: set[str] = set()
        for provider in providers:
            # Check for duplicate IDs
            if provider.provider_id in seen_ids:
                yield ValidationError(
                    entity_type="provider",
                    entity_id=provider.provider_id,
                    field="provider_id",
                    message=f"duplicate provider_id '{provider.provider_id}'",
                )
            seen_ids.add(provider.provider_id)

            # Validate priority
            if provider.priority < 0:
                yield ValidationError(
                    entity_type="provider",
                    entity_id=provider.provider_id,
                    field="priority",
                    message=f"priority must be non-negative, got {provider.priority}",
                )

            # Validate timeout
            if provider.connection.timeout_seconds <= 0:
                yield ValidationError(
                    entity_type="provider",
                    entity_id=provider.provider_id,
                    field="connection.timeout_seconds",
                    message=f"timeout must be positive, got {provider.connection.timeout_seconds}",
                )

            # Validate base_url format (basic check)
            if not provider.connection.base_url:
                yield ValidationError(
                    entity_type="provider",
                    entity_id=provider.provider_id,
                    field="connection.base_url",
                    message="base_url is required",
                )
            elif not (
                provider.connection.base_url.startswith("http://")
                or provider.connection.base_url.startswith("https://")
            ):
                yield ValidationError(
                    entity_type="provider",
                    entity_id=provider.provider_id,
                    field="connection.base_url",
                    message=f"base_url must start with http:// or https://, got '{provider.connection.base_url}'",
                )

    def validate_models(
        self,
        models: Sequence[ModelRecord],
    ) -> Iterator[ValidationError]:
        """Validate model records.

        Args:
            models: Model records to validate.

        Yields:
            ValidationError for each invalid record.
        """
        seen_ids: set[str] = set()
        for model in models:
            # Check for duplicate IDs
            if model.model_id in seen_ids:
                yield ValidationError(
                    entity_type="model",
                    entity_id=model.model_id,
                    field="model_id",
                    message=f"duplicate model_id '{model.model_id}'",
                )
            seen_ids.add(model.model_id)

            # Validate priority
            if model.priority < 0:
                yield ValidationError(
                    entity_type="model",
                    entity_id=model.model_id,
                    field="priority",
                    message=f"priority must be non-negative, got {model.priority}",
                )

            # Validate context_window if provided
            if model.context_window is not None and model.context_window <= 0:
                yield ValidationError(
                    entity_type="model",
                    entity_id=model.model_id,
                    field="context_window",
                    message=f"context_window must be positive if provided, got {model.context_window}",
                )

            # Validate capabilities
            if not model.capabilities:
                yield ValidationError(
                    entity_type="model",
                    entity_id=model.model_id,
                    field="capabilities",
                    message="at least one capability is required",
                )

    def validate_cross_references(
        self,
        providers: Sequence[ProviderRecord],
        models: Sequence[ModelRecord],
    ) -> Iterator[ValidationError]:
        """Validate cross-references between providers and models.

        Args:
            providers: Provider records.
            models: Model records.

        Yields:
            ValidationError for each invalid reference.
        """
        provider_ids = {p.provider_id for p in providers}
        model_provider_ids = {m.provider_id for m in models}

        # Check for models referencing unknown providers
        unknown_providers = model_provider_ids - provider_ids
        for provider_id in unknown_providers:
            for model in models:
                if model.provider_id == provider_id:
                    yield ValidationError(
                        entity_type="model",
                        entity_id=model.model_id,
                        field="provider_id",
                        message=f"references unknown provider '{provider_id}'",
                    )

    def validate(
        self,
        providers: Sequence[ProviderRecord],
        models: Sequence[ModelRecord],
    ) -> RegistryValidationResult:
        """Validate all registry data.

        Args:
            providers: Provider records to validate.
            models: Model records to validate.

        Returns:
            RegistryValidationResult with any errors or warnings.
        """
        errors: list[ValidationError] = []
        warnings: list[str] = []

        # Validate providers
        errors.extend(self.validate_providers(providers))

        # Validate models
        errors.extend(self.validate_models(models))

        # Validate cross-references
        errors.extend(self.validate_cross_references(providers, models))

        # Generate warnings
        provider_ids = {p.provider_id for p in providers}
        model_provider_ids = {m.provider_id for m in models}

        # Warn about providers with no models
        for provider in providers:
            if provider.provider_id not in model_provider_ids:
                warnings.append(
                    f"provider '{provider.provider_id}' has no models registered"
                )

        # Warn about providers with no declared capabilities
        for provider in providers:
            if not provider.capabilities:
                warnings.append(
                    f"provider '{provider.provider_id}' has no declared capabilities"
                )

        return RegistryValidationResult(
            valid=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def validate_with_report(
        self,
        providers: Sequence[ProviderRecord],
        models: Sequence[ModelRecord],
    ) -> ValidationReport:
        """Validate records and return a structured :class:`ValidationReport`.

        The structured form is the Phase 2 contract: each issue carries an
        ``entity_type``, ``entity_id``, ``field``, and message, suitable
        for emitting through :class:`RegistryValidationError`.

        Args:
            providers: Provider records to validate.
            models: Model records to validate.

        Returns:
            ValidationReport with issues and warnings.
        """
        result = self.validate(providers, models)

        issues = tuple(
            ValidationIssue(
                entity_type=error.entity_type,
                entity_id=error.entity_id,
                field=error.field,
                message=error.message,
            )
            for error in result.errors
        )
        return ValidationReport(issues=issues, warnings=result.warnings)
