"""Unified LLM configuration loader — loads llm.yaml into ProviderRecord[] + ModelRecord[].

This loader replaces the split providers.yaml / models.yaml model with a single
llm.yaml file. The loader normalizes the hierarchical YAML into the existing
runtime domain records (ProviderRecord, ModelRecord) so that:

- ProviderRegistry and ModelRegistry remain separate runtime concepts.
- The YAML is a single source of truth.
- provider_id is injected into ModelRecord during normalization.
- Provider capabilities are derived from the union of their models' capabilities.

Flow:
    llm.yaml
        ↓
    LLmConfigLoader
        ↓
    validated ProviderRecord[] + ModelRecord[]
        ↓
    CatalogBuilder
        ↓
    ProviderRegistry + ModelRegistry (separate runtime concepts)
        ↓
    ProviderFactory / ProviderManager
        ↓
    Router
        ↓
    LLM adapters

Authority: Decision 0014, architectural review 2025.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.intelligence.registry.exceptions import LoadIssue
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import (
    AUTH_TYPE_DEFAULT_SENTINEL,
    AuthConfig,
    AuthType,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.resolver import EnvironmentResolver
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.model import ModelType
from app.intelligence.registry.types.provider import ProviderType

try:
    import yaml as _yaml
    _YAML_LOAD_SAFE = _yaml.safe_load
except ImportError:
    _YAML_LOAD_SAFE = None  # type: ignore[assignment]


# ------------------------------------------------------------------
# Public types
# ------------------------------------------------------------------

LLmConfigResult = "LLmConfigResult"


@dataclass(frozen=True, slots=True)
class LLmConfigLoadResult:
    """Result of loading the unified LLM configuration.

    Attributes:
        providers: Normalized provider records. Empty if load failed.
        models: Normalized model records. Empty if load failed.
        errors: Human-readable error messages. Empty on success.
    """

    providers: Sequence[ProviderRecord] = field(default_factory=list)
    models: Sequence[ModelRecord] = field(default_factory=list)
    errors: Sequence[str] = field(default_factory=list)


# ------------------------------------------------------------------
# Loader
# ------------------------------------------------------------------

class LLmConfigLoader:
    """Loads the unified llm.yaml and produces normalized ProviderRecord + ModelRecord lists.

    The loader handles:
    - Parsing llm.yaml (YAML syntax + env-var resolution).
    - Validating the structural shape of the configuration.
    - Normalizing providers and their nested models into separate flat lists.
    - Injecting provider_id into each ModelRecord during normalization.
    - Deriving provider capabilities from their models (no independent config).

    Both file-based and dict-based loading are supported.
    """

    def __init__(
        self,
        resolver: EnvironmentResolver | None = None,
    ) -> None:
        self._resolver = resolver or EnvironmentResolver()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(
        self,
        path: str | Path,
        *,
        env: Mapping[str, str] | None = None,
        strict: bool = False,
    ) -> LLmConfigLoadResult:
        """Load and normalize llm.yaml from a file path.

        Args:
            path: Path to llm.yaml.
            env: Optional environment mapping (defaults to os.environ).

        Returns:
            LLmConfigLoadResult with loaded records and any errors.

        Raises:
            RegistryLoadError: When the file cannot be read, YAML is malformed,
                or env-var resolution fails.
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

        # Read file.
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

        return self.load_text(raw_text, file_path=file_path, env=env, strict=strict)

    def load_text(
        self,
        raw_text: str,
        *,
        file_path: str = "llm.yaml",
        env: Mapping[str, str] | None = None,
        strict: bool = False,
    ) -> LLmConfigLoadResult:
        """Load one already-read YAML snapshot.

        ``config apply`` uses this entry point so the validated snapshot is the
        exact snapshot later written atomically. Runtime callers retain the
        permissive default for backward compatibility; candidate commands opt
        into strict schema validation.
        """
        from app.intelligence.registry.exceptions import LoadReport, RegistryLoadError

        if _YAML_LOAD_SAFE is None:
            raise RegistryLoadError(
                LoadReport(
                    issues=(LoadIssue(file_path=file_path, position="(root)", message="PyYAML is required for YAML registry loading"),)
                )
            )

        # Parse YAML.
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

        if strict:
            strict_errors = _strict_schema_errors(data)
            if strict_errors:
                return LLmConfigLoadResult(errors=tuple(strict_errors))

        # Resolve environment variables.
        try:
            resolved, unresolved = self._resolver.resolve(data, env=env)
        except Exception as exc:
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

        # Collect unresolved env-var issues.
        issues: list[str] = []
        for position, name in unresolved:
            issues.append(
                f"{file_path}::{position}: environment variable '{name}' is not set"
            )

        # Normalize and validate.
        result = self.load_from_dict(resolved)
        errors = list(issues) + list(result.errors)

        return LLmConfigLoadResult(
            providers=result.providers,
            models=result.models,
            errors=errors,
        )

    def load_from_dict(
        self,
        data: dict[str, Any],
    ) -> LLmConfigLoadResult:
        """Load and normalize from a pre-parsed dict (e.g., parsed YAML or test fixture).

        Args:
            data: Dictionary with 'llm' key containing 'providers' list.

        Returns:
            LLmConfigLoadResult with loaded records and any errors.
        """
        errors: list[str] = []
        providers: list[ProviderRecord] = []
        models: list[ModelRecord] = []

        llm_data = data.get("llm")
        if llm_data is None:
            errors.append("top-level 'llm' key is required")
            return LLmConfigLoadResult(providers=[], models=[], errors=errors)

        if not isinstance(llm_data, dict):
            errors.append("'llm' must be a dictionary")
            return LLmConfigLoadResult(providers=[], models=[], errors=errors)

        providers_data = llm_data.get("providers")
        if providers_data is None:
            errors.append("'llm.providers' is required")
            return LLmConfigLoadResult(providers=[], models=[], errors=errors)

        if not isinstance(providers_data, list):
            errors.append("'llm.providers' must be a list")
            return LLmConfigLoadResult(providers=[], models=[], errors=errors)

        # Pass 1: parse all providers and models, collecting ALL errors.
        raw_provider_records: list[tuple[int, str, _RawProviderRecord]] = []

        for i, item in enumerate(providers_data):
            try:
                provider_record = self._parse_provider(item)
                raw_provider_records.append((i, item.get("id", "?"), provider_record))
            except (ValueError, TypeError) as exc:
                errors.append(f"llm.providers[{i}]: {exc}")

        # Pass 2: collect all provider IDs for duplicate detection.
        seen_provider_ids: set[str] = set()
        for i, provider_id, _record in raw_provider_records:
            if provider_id in seen_provider_ids:
                errors.append(
                    f"llm.providers[{i}]: duplicate provider id '{provider_id}'"
                )
            seen_provider_ids.add(provider_id)

        # Pass 3: collect all model IDs for duplicate detection.
        seen_model_ids: set[str] = set()
        for i, _provider_id, provider_record in raw_provider_records:
            for j, model_entry in enumerate(provider_record.raw_models):
                model_id = model_entry.get("id") or model_entry.get("model_id") or ""
                if model_id in seen_model_ids:
                    errors.append(
                        f"llm.providers[{i}].models[{j}]: "
                        f"duplicate model id '{model_id}'"
                    )
                seen_model_ids.add(model_id)

        # Pass 4: finalize only providers that parsed without structural errors.
        for i, provider_id, raw in raw_provider_records:
            try:
                provider, provider_models = self._finalize_provider(provider_id, raw)
                providers.append(provider)
                models.extend(provider_models)
            except (ValueError, TypeError) as exc:
                errors.append(f"llm.providers[{i}]: {exc}")

        return LLmConfigLoadResult(
            providers=providers,
            models=models,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Internal — parsing
    # ------------------------------------------------------------------

    def _parse_provider(
        self,
        data: Any,
    ) -> "_RawProviderRecord":
        """Parse one provider entry from the YAML dict.

        Raises:
            ValueError / TypeError for structural errors (surfaced as load errors).
        """
        if not isinstance(data, dict):
            raise TypeError("provider entry must be a dictionary")

        # Provider ID: support both 'id' and 'provider_id' for migration flexibility.
        provider_id = data.get("id") or data.get("provider_id")
        if not provider_id or not isinstance(provider_id, str):
            raise ValueError("provider 'id' is required and must be a string")

        # Provider type.
        type_str = data.get("type") or data.get("provider_type")
        if not type_str:
            raise ValueError("provider 'type' is required")
        try:
            provider_type = ProviderType(str(type_str).strip().lower())
        except ValueError:
            raise ValueError(
                f"invalid provider type '{type_str}', "
                f"expected one of: {[e.value for e in ProviderType]}"
            )

        # Deployment.
        deployment_str = data.get("deployment", "cloud")
        try:
            deployment = DeploymentType(str(deployment_str).strip().lower())
        except ValueError:
            raise ValueError(
                f"invalid deployment '{deployment_str}', "
                f"expected one of: {[e.value for e in DeploymentType]}"
            )

        # Connection config.
        conn_data = data.get("connection", {})
        if not isinstance(conn_data, dict):
            raise TypeError("connection must be a dictionary")

        base_url = conn_data.get("base_url", "")
        region = conn_data.get("region")
        if region is not None and not isinstance(region, str):
            raise TypeError("connection.region must be a string")
        auth_probe_model = conn_data.get("auth_probe_model")
        if auth_probe_model is not None:
            if not isinstance(auth_probe_model, str):
                raise TypeError("connection.auth_probe_model must be a string")
            auth_probe_model = auth_probe_model.strip()
            if not auth_probe_model:
                raise ValueError("connection.auth_probe_model must not be empty")

        # Auth config.
        auth_data = data.get("auth", {})
        if not isinstance(auth_data, dict):
            raise TypeError("auth must be a dictionary")

        # Parse auth.type — the primary auth declaration.
        # If absent, store the sentinel so the validator can distinguish
        # "type omitted" (backward-compat) from "type explicitly api_key".
        auth_type_value = self._parse_auth_type(auth_data.get("type"))

        # api_key_env is still accepted (names the env var that holds the secret).
        api_key_env = auth_data.get("api_key_env")
        if api_key_env is not None and not isinstance(api_key_env, str):
            raise TypeError("auth.api_key_env must be a string when provided")

        # NOTE: auth.api_key (the actual secret value) is intentionally rejected.
        # Secrets MUST NOT be stored in llm.yaml.
        if auth_data.get("api_key") is not None:
            raise TypeError(
                "auth.api_key is not permitted in llm.yaml; "
                "declare auth.type instead and supply the secret via an "
                "environment variable named in auth.api_key_env"
            )

        auth_header = auth_data.get("auth_header")
        if auth_header is not None and not isinstance(auth_header, str):
            raise TypeError("auth.auth_header must be a string when provided")

        # Models: required, may be empty list.
        models_data = data.get("models")
        if models_data is None:
            raise ValueError("provider must have a 'models' list (may be empty)")
        if not isinstance(models_data, list):
            raise TypeError("'models' must be a list")

        return _RawProviderRecord(
            provider_id=provider_id,
            provider_type=provider_type,
            deployment=deployment,
            base_url=base_url,
            region=region,
            auth_probe_model=auth_probe_model,
            auth=AuthConfig(
                type=auth_type_value,  # may be the sentinel when type is absent
                api_key_env=api_key_env,
                auth_header=auth_header,
            ),
            enabled=bool(data.get("enabled", True)),
            priority=int(data.get("priority", 100)),
            raw_models=models_data,
        )

    def _parse_auth_type(self, raw_type: Any) -> AuthType | object:
        """Parse auth.type from YAML into an AuthType enum or AUTH_TYPE_DEFAULT_SENTINEL.

        When the field is absent from the YAML (raw_type is None), the sentinel
        is returned so the validator knows auth.type was not explicitly declared.
        When auth.type is explicitly set, returns the corresponding AuthType value.

        Raises:
            TypeError: if the field is present but not a string.
            ValueError: if the string is not a recognised auth type.
        """
        if raw_type is None:
            # auth.type was not declared in the YAML.
            # Return the sentinel so the validator can skip api_key_env enforcement.
            return AUTH_TYPE_DEFAULT_SENTINEL
        if not isinstance(raw_type, str):
            raise TypeError("auth.type must be a string")
        normalized = str(raw_type).strip().lower()
        try:
            return AuthType(normalized)
        except ValueError:
            valid = [e.value for e in AuthType]
            raise ValueError(
                f"invalid auth.type '{raw_type}', expected one of: {valid}"
            )

    def _parse_model(
        self,
        data: Any,
        provider_id: str,
        provider_base_url: str,
    ) -> ModelRecord:
        """Parse one model entry within a provider.

        Raises:
            ValueError / TypeError for structural errors.
        """
        if not isinstance(data, dict):
            raise TypeError("model entry must be a dictionary")

        model_id = data.get("id") or data.get("model_id")
        if not model_id or not isinstance(model_id, str):
            raise ValueError("model 'id' is required and must be a string")

        model_type_str = data.get("type") or data.get("model_type")
        if not model_type_str:
            raise ValueError("model 'type' is required")
        try:
            model_type = ModelType(str(model_type_str).strip().lower())
        except ValueError:
            raise ValueError(
                f"invalid model type '{model_type_str}', "
                f"expected one of: {[e.value for e in ModelType]}"
            )

        # deployment_name: optional, may differ from model_id.
        deployment_name = data.get("deployment_name")
        if deployment_name is not None and not isinstance(deployment_name, str):
            raise ValueError("deployment_name must be a string when provided")

        # context_window.
        context_window = data.get("context_window")
        if context_window is not None:
            if not isinstance(context_window, int) or isinstance(context_window, bool):
                raise ValueError("context_window must be an integer when provided")
            if context_window <= 0:
                raise ValueError("context_window must be positive when provided")

        # Capabilities: required.
        capabilities = _parse_capabilities(data.get("capabilities", []))
        if not capabilities:
            raise ValueError("at least one capability is required")

        # priority.
        priority = int(data.get("priority", 100))

        # Validate base_url (derived from provider if model doesn't override).
        model_base_url = data.get("base_url", provider_base_url)
        if model_base_url:
            if not (
                model_base_url.startswith("http://")
                or model_base_url.startswith("https://")
            ):
                raise ValueError(
                    f"connection base_url must start with http:// or https://, "
                    f"got '{model_base_url}'"
                )

        return ModelRecord(
            model_id=model_id,
            provider_id=provider_id,
            model_type=model_type,
            deployment_name=deployment_name,
            context_window=context_window,
            capabilities=capabilities,
            priority=priority,
        )

    # ------------------------------------------------------------------
    # Internal — finalization
    # ------------------------------------------------------------------

    def _finalize_provider(
        self,
        provider_id: str,
        raw: "_RawProviderRecord",
    ) -> tuple[ProviderRecord, list[ModelRecord]]:
        """Finalize one provider: derive capabilities from models, build records.

        Returns the ProviderRecord and its list of ModelRecords.

        Raises:
            ValueError: if any model entry is invalid.
        """
        models: list[ModelRecord] = []
        model_errors: list[str] = []

        for j, model_entry in enumerate(raw.raw_models):
            try:
                model_record = self._parse_model(
                    model_entry,
                    provider_id=provider_id,
                    provider_base_url=raw.base_url,
                )
                models.append(model_record)
            except (ValueError, TypeError) as exc:
                model_errors.append(
                    f"llm.providers['{provider_id}'].models[{j}]: {exc}"
                )

        if model_errors:
            raise ValueError("; ".join(model_errors))

        if raw.auth_probe_model is not None:
            usable_chat_models = {
                model.deployment_name or model.model_id
                for model in models
                if Capability.CHAT in model.capabilities
            }
            if raw.auth_probe_model not in usable_chat_models:
                raise ValueError(
                    "connection.auth_probe_model must identify a declared "
                    "chat-capable model for this provider"
                )

        # Derive provider capabilities as the union of its models' capabilities.
        # This prevents configuration drift: provider capabilities are NOT
        # independently configured in the YAML — they are derived.
        provider_capabilities: frozenset[Capability] = frozenset()
        for m in models:
            provider_capabilities = provider_capabilities | m.capabilities

        # Build ConnectionConfig.
        connection = ConnectionConfig(
            base_url=raw.base_url,
            region=raw.region,
            auth_probe_model=raw.auth_probe_model,
        )

        provider_record = ProviderRecord(
            provider_id=raw.provider_id,
            provider_type=raw.provider_type,
            deployment=raw.deployment,
            auth=raw.auth,
            connection=connection,
            capabilities=provider_capabilities,
            enabled=raw.enabled,
            priority=raw.priority,
        )

        return provider_record, models


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _strict_schema_errors(data: Any) -> list[str]:
    """Reject keys the normalizer would otherwise silently discard.

    This is deliberately a small allow-list over the supported llm.yaml shape,
    not a second schema framework. It is used only for operator-supplied
    candidates so legacy runtime loading remains compatible.
    """
    errors: list[str] = []

    def reject_unknown(value: Any, allowed: set[str], location: str) -> None:
        if not isinstance(value, dict):
            return
        for key in value:
            if key not in allowed:
                if location.endswith("auth") and key == "api_key":
                    errors.append("auth.api_key is not permitted in llm.yaml")
                else:
                    errors.append(f"{location}: unsupported field '{key}'")

    reject_unknown(data, {"llm"}, "root")
    if not isinstance(data, dict):
        return errors
    llm = data.get("llm")
    reject_unknown(llm, {"providers"}, "llm")
    if not isinstance(llm, dict) or not isinstance(llm.get("providers"), list):
        return errors
    provider_fields = {
        "id", "type", "deployment", "enabled", "priority", "connection", "auth", "models"
    }
    model_fields = {
        "id", "type", "deployment_name", "context_window", "capabilities", "priority", "base_url"
    }
    for index, provider in enumerate(llm["providers"]):
        location = f"llm.providers[{index}]"
        reject_unknown(provider, provider_fields, location)
        if not isinstance(provider, dict):
            continue
        reject_unknown(
            provider.get("connection"),
            {"base_url", "region", "auth_probe_model"},
            f"{location}.connection",
        )
        reject_unknown(provider.get("auth"), {"type", "api_key_env", "auth_header"}, f"{location}.auth")
        models = provider.get("models")
        if isinstance(models, list):
            for model_index, model in enumerate(models):
                reject_unknown(model, model_fields, f"{location}.models[{model_index}]")
    return errors

def _parse_capabilities(caps: Any) -> frozenset[Capability]:
    """Parse capability input into ``frozenset[Capability]``.

    Handles:
    - A single string: "chat"  → frozenset({Capability.CHAT})
    - A list of strings: ["chat", "embedding"]
    - A YAML boolean (bool): silently ignored (fails the "at least one
      capability required" check downstream with a clear error)
    - None or other types: returns empty frozenset
    """
    # Guard: YAML booleans (True/False) are not valid capability values.
    if isinstance(caps, bool):
        return frozenset()
    if isinstance(caps, str):
        caps = [caps]
    if not isinstance(caps, list):
        return frozenset()

    result: list[Capability] = []
    for cap_value in caps:
        # Skip YAML booleans that appear inside a list.
        if isinstance(cap_value, bool):
            continue
        normalized = str(cap_value).strip().lower()
        for capability in Capability:
            if capability.value == normalized:
                result.append(capability)
                break
    return frozenset(result)


@dataclass(frozen=True, slots=True)
class _RawProviderRecord:
    """Intermediate parsed provider before finalization (not a runtime record)."""

    provider_id: str
    provider_type: ProviderType
    deployment: DeploymentType
    base_url: str
    region: str | None
    auth_probe_model: str | None
    auth: AuthConfig
    enabled: bool
    priority: int
    raw_models: list[dict[str, Any]]


__all__ = [
    "LLmConfigLoader",
    "LLmConfigLoadResult",
]
