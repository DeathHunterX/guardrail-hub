"""Provider loader — loads and validates provider registry data.

Phase 2 additions over Phase 1:

- Loads from a file path (YAML) in addition to a dict.
- Resolves ``${ENV_VAR}`` placeholders through :class:`EnvironmentResolver`.
- Emits structured :class:`LoadIssue` records so failures can be rendered
  with file paths and positions.

The loader still consumes already-parsed data via :meth:`load_from_dict` so
tests can drive it without disk I/O.

Authority: Decision 0014 §3 — the loader does not interpret credentials,
it only parses and resolves them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.intelligence.registry.exceptions import LoadIssue
from app.intelligence.registry.models.provider import (
    AuthConfig,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.resolver import EnvironmentResolver
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType

try:  # PyYAML is the only runtime YAML dependency.
    import yaml as _yaml
    _YAML_LOAD_SAFE = _yaml.safe_load
except ImportError:  # pragma: no cover - YAML is always available
    _YAML_LOAD_SAFE = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class ProviderLoadResult:
    """Result of loading provider data."""

    providers: Sequence[ProviderRecord]
    errors: Sequence[str]


class ProviderLoader:
    """Loads provider records from a dict or YAML file.

    Both methods return a :class:`ProviderLoadResult` so the caller can
    decide whether ``errors`` is fatal. ``load_from_yaml`` is a thin
    wrapper around ``load_from_dict`` plus ``EnvironmentResolver``.
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
    ) -> ProviderLoadResult:
        """Load providers from a YAML file.

        Args:
            path: File to read. Must exist and be readable.
            env: Optional environment mapping (defaults to ``os.environ``).

        Raises:
            RegistryLoadError: when PyYAML is unavailable, the file cannot
                be read, or the YAML is malformed.

        Returns:
            ProviderLoadResult with any errors aggregated.
        """
        # Imported here to avoid a circular import at module load time.
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

        # Resolve env placeholders. Unresolved names become load issues.
        try:
            resolved, unresolved = self._resolver.resolve(data, env=env)
        except Exception as exc:  # defensive: resolver should not raise
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

        # Re-tag load errors with the source path so diagnostics stay
        # attached to the file even when the underlying data is structured.
        errors = list(result.errors)
        for issue in issues:
            errors.append(f"{issue.file_path}::{issue.position}: {issue.message}")

        return ProviderLoadResult(providers=result.providers, errors=errors)

    # ------------------------------------------------------------------
    # Dict / already-parsed input
    # ------------------------------------------------------------------

    def load_from_dict(
        self,
        data: dict[str, Any],
    ) -> ProviderLoadResult:
        """Load providers from a dictionary (e.g., parsed YAML).

        Args:
            data: Dictionary with 'providers' key containing provider list.

        Returns:
            ProviderLoadResult with validated records and any errors.
        """
        providers: list[ProviderRecord] = []
        errors: list[str] = []

        providers_data = data.get("providers", [])
        if not isinstance(providers_data, list):
            errors.append("'providers' must be a list")
            return ProviderLoadResult(providers=[], errors=errors)

        for i, item in enumerate(providers_data):
            try:
                providers.append(self._parse_provider(item))
            except (ValueError, TypeError) as exc:
                errors.append(f"providers[{i}]: {exc}")

        return ProviderLoadResult(providers=providers, errors=errors)

    # ------------------------------------------------------------------
    # Internal parsing
    # ------------------------------------------------------------------

    def _parse_provider(self, data: Any) -> ProviderRecord:
        if not isinstance(data, dict):
            raise TypeError("provider must be a dictionary")

        provider_id = data.get("provider_id")
        if not provider_id or not isinstance(provider_id, str):
            raise ValueError("provider_id is required and must be a string")

        provider_type_str = data.get("provider_type")
        if not provider_type_str:
            raise ValueError("provider_type is required")
        try:
            provider_type = ProviderType(str(provider_type_str).strip().lower())
        except ValueError:
            raise ValueError(
                f"invalid provider_type '{provider_type_str}', "
                f"expected one of: {[e.value for e in ProviderType]}"
            )

        deployment_str = data.get("deployment", "cloud")
        try:
            deployment = DeploymentType(str(deployment_str).strip().lower())
        except ValueError:
            raise ValueError(
                f"invalid deployment '{deployment_str}', "
                f"expected one of: {[e.value for e in DeploymentType]}"
            )

        connection_data = data.get("connection", {})
        if not isinstance(connection_data, dict):
            raise TypeError("connection must be a dictionary")
        connection = ConnectionConfig(
            base_url=connection_data.get("base_url", ""),
            timeout_seconds=float(connection_data.get("timeout_seconds", 60.0)),
            max_retries=int(connection_data.get("max_retries", 3)),
            verify_ssl=bool(connection_data.get("verify_ssl", True)),
            proxy_url=connection_data.get("proxy_url"),
            ca_bundle=connection_data.get("ca_bundle"),
        )

        auth_data = data.get("auth", {})
        if not isinstance(auth_data, dict):
            raise TypeError("auth must be a dictionary")
        additional = auth_data.get("additional_headers", {})
        if not isinstance(additional, dict):
            additional = {}
        auth = AuthConfig(
            api_key_env=auth_data.get("api_key_env"),
            api_key=auth_data.get("api_key"),
            auth_header=auth_data.get("auth_header"),
            additional_headers=dict(additional),
        )

        capabilities = _parse_capabilities(data.get("capabilities", []))

        # Required field checks are collected here so we can surface all
        # structural problems in one pass when a structured validator
        # is not in use.
        if not connection.base_url:
            raise ValueError("connection.base_url is required")
        if not (
            connection.base_url.startswith("http://")
            or connection.base_url.startswith("https://")
        ):
            raise ValueError(
                "connection.base_url must start with http:// or https://, "
                f"got '{connection.base_url}'"
            )

        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        return ProviderRecord(
            provider_id=provider_id,
            provider_type=provider_type,
            deployment=deployment,
            auth=auth,
            connection=connection,
            capabilities=capabilities,
            enabled=bool(data.get("enabled", True)),
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
    "ProviderLoader",
    "ProviderLoadResult",
]