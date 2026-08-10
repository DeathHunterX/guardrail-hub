"""Model loader — loads and validates model registry data.

Phase 2 additions over Phase 1:

- Loads from a file path (YAML) in addition to a dict.
- Resolves ``${ENV_VAR}`` placeholders through :class:`EnvironmentResolver`.
- Emits structured :class:`LoadIssue` records so failures can be rendered
  with file paths and positions.

Authority: Decision 0014 §3.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.intelligence.registry.exceptions import LoadIssue
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.resolver import EnvironmentResolver
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.model import ModelType

try:
    import yaml as _yaml
    _YAML_LOAD_SAFE = _yaml.safe_load
except ImportError:  # pragma: no cover
    _YAML_LOAD_SAFE = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class ModelLoadResult:
    """Result of loading model data."""

    models: Sequence[ModelRecord]
    errors: Sequence[str]


class ModelLoader:
    """Loads model records from a dict or YAML file.

    The contract mirrors :class:`ProviderLoader`.
    """

    def __init__(
        self,
        resolver: EnvironmentResolver | None = None,
    ) -> None:
        self._resolver = resolver or EnvironmentResolver()

    # ------------------------------------------------------------------
    # File path
    # ------------------------------------------------------------------

    def load_from_yaml(
        self,
        path: str | Path,
        *,
        env: Mapping[str, str] | None = None,
    ) -> ModelLoadResult:
        """Load models from a YAML file.

        Args:
            path: File to read. Must exist and be readable.
            env: Optional environment mapping (defaults to ``os.environ``).

        Raises:
            RegistryLoadError: when PyYAML is unavailable, the file cannot
                be read, or the YAML is malformed.

        Returns:
            ModelLoadResult with any errors aggregated.
        """
        from app.intelligence.registry.exceptions import (
            LoadReport,
            RegistryLoadError,
        )

        if _YAML_LOAD_SAFE is None:
            raise RegistryLoadError(
                LoadReport(
                    issues=(
                        LoadIssue(
                            file_path=str(path),
                            position="(root)",
                            message="PyYAML is required for YAML registry loading",
                        ),
                    )
                )
            )

        file_path = str(path)
        try:
            raw_text = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise RegistryLoadError(
                LoadReport(
                    issues=(
                        LoadIssue(
                            file_path=file_path,
                            position="(root)",
                            message=f"file not found: {exc}",
                        ),
                    )
                )
            ) from exc
        except OSError as exc:
            raise RegistryLoadError(
                LoadReport(
                    issues=(
                        LoadIssue(
                            file_path=file_path,
                            position="(root)",
                            message=f"could not read file: {exc}",
                        ),
                    )
                )
            ) from exc

        try:
            data = _YAML_LOAD_SAFE(raw_text)
        except _yaml.YAMLError as exc:
            raise RegistryLoadError(
                LoadReport(
                    issues=(
                        LoadIssue(
                            file_path=file_path,
                            position="(root)",
                            message=f"YAML syntax error: {exc}",
                        ),
                    )
                )
            ) from exc

        try:
            resolved, unresolved = self._resolver.resolve(data, env=env)
        except Exception as exc:  # defensive
            raise RegistryLoadError(
                LoadReport(
                    issues=(
                        LoadIssue(
                            file_path=file_path,
                            position="(root)",
                            message=f"environment resolution failed: {exc}",
                        ),
                    )
                )
            ) from exc

        issues: list[LoadIssue] = []
        for position, name in unresolved:
            issues.append(
                LoadIssue(
                    file_path=file_path,
                    position=position,
                    message=f"environment variable '{name}' is not set",
                )
            )

        result = self.load_from_dict(resolved)

        errors = list(result.errors)
        for issue in issues:
            errors.append(f"{issue.file_path}::{issue.position}: {issue.message}")

        return ModelLoadResult(models=result.models, errors=errors)

    # ------------------------------------------------------------------
    # Dict / already-parsed input
    # ------------------------------------------------------------------

    def load_from_dict(
        self,
        data: dict[str, Any],
    ) -> ModelLoadResult:
        """Load models from a dictionary (e.g., parsed YAML)."""
        models: list[ModelRecord] = []
        errors: list[str] = []

        models_data = data.get("models", [])
        if not isinstance(models_data, list):
            errors.append("'models' must be a list")
            return ModelLoadResult(models=[], errors=errors)

        for i, item in enumerate(models_data):
            try:
                models.append(self._parse_model(item))
            except (ValueError, TypeError) as exc:
                errors.append(f"models[{i}]: {exc}")

        return ModelLoadResult(models=models, errors=errors)

    # ------------------------------------------------------------------
    # Internal parsing
    # ------------------------------------------------------------------

    def _parse_model(self, data: Any) -> ModelRecord:
        if not isinstance(data, dict):
            raise TypeError("model must be a dictionary")

        model_id = data.get("model_id")
        if not model_id or not isinstance(model_id, str):
            raise ValueError("model_id is required and must be a string")

        provider_id = data.get("provider_id")
        if not provider_id or not isinstance(provider_id, str):
            raise ValueError("provider_id is required and must be a string")

        model_type_str = data.get("model_type")
        if not model_type_str:
            raise ValueError("model_type is required")
        try:
            model_type = ModelType(str(model_type_str).strip().lower())
        except ValueError:
            raise ValueError(
                f"invalid model_type '{model_type_str}', "
                f"expected one of: {[e.value for e in ModelType]}"
            )

        capabilities = _parse_capabilities(data.get("capabilities", []))

        deployment_name = data.get("deployment_name")
        if deployment_name is not None and not isinstance(deployment_name, str):
            raise ValueError("deployment_name must be a string when provided")

        context_window = data.get("context_window")
        if context_window is not None:
            if not isinstance(context_window, int) or isinstance(context_window, bool):
                raise ValueError("context_window must be an integer when provided")
            if context_window <= 0:
                raise ValueError("context_window must be positive when provided")

        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        return ModelRecord(
            model_id=model_id,
            provider_id=provider_id,
            model_type=model_type,
            deployment_name=deployment_name,
            context_window=context_window,
            capabilities=capabilities,
            priority=int(data.get("priority", 100)),
            metadata=dict(metadata),
        )


def _parse_capabilities(caps: Any) -> frozenset[Capability]:
    """Parse capability input into ``frozenset[Capability]``."""
    if isinstance(caps, str):
        caps = [caps]
    if not isinstance(caps, list):
        return frozenset()

    result: list[Capability] = []
    for cap_value in caps:
        normalized = str(cap_value).strip().lower()
        for capability in Capability:
            if capability.value == normalized:
                result.append(capability)
                break
    return frozenset(result)


__all__ = [
    "ModelLoader",
    "ModelLoadResult",
]