"""Approved host-side credential provisioning for Guardrail Hub Compose.

This module belongs to the provisioning plane.  It never runs in the MCP
runtime path and does not alter the read-only container credential backend.
It recognizes only the local Guardrail Hub Compose layout anchored by the
project's ``config/llm.yaml`` and writes only ``secrets/<provider_id>`` below
that project root.
"""

from __future__ import annotations

import os
import stat
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Optional

import yaml

from app.intelligence.credentials import (
    CredentialBackendError,
    CredentialNotFoundError,
)
from app.intelligence.credentials.container_backend import (
    MAX_CREDENTIAL_FILE_SIZE_BYTES,
)
from app.intelligence.setup.windows_acl import (
    WindowsAclError,
    protect_windows_path,
)

_COMPOSE_FILE_NAME: Final[str] = "docker-compose.yml"
_CONFIG_FILE_NAME: Final[str] = "llm.yaml"
_SERVICE_NAME: Final[str] = "mcp-server"
_HOST_SECRET_ROOT: Final[str] = "secrets"
_RUNTIME_SECRET_MOUNT: Final[str] = "/run/secrets"
_COMPOSE_PROJECT_NAME: Final[str] = "guardrail-hub"
_PYTHON_PROJECT_NAME: Final[str] = "mcp-server"
_CONSOLE_SCRIPT: Final[str] = "app.cli:main"


@dataclass(frozen=True, slots=True)
class ComposeHostProject:
    """A recognized, approved local Compose provisioning target."""

    root: Path
    secret_root: Path


def recognize_compose_host_project(config_path: str | Path) -> Optional[ComposeHostProject]:
    """Return the approved project only when its Compose contract is present.

    A random directory called ``secrets`` is never sufficient authority.  The
    configuration path must be exactly ``<root>/config/llm.yaml`` beneath a
    project that contains the application package and the ratified Compose
    file-backend/read-only-mount shape.
    """
    try:
        config = Path(config_path).expanduser().resolve(strict=True)
    except (OSError, ValueError):
        return None

    if config.name != _CONFIG_FILE_NAME or config.parent.name != "config":
        return None
    root = config.parent.parent
    if (
        not (root / "app" / "cli.py").is_file()
        or (root / "config" / _CONFIG_FILE_NAME) != config
        or not _has_guardrail_hub_project_identity(root)
    ):
        return None

    compose_path = root / _COMPOSE_FILE_NAME
    try:
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    if not isinstance(compose, dict):
        return None
    if compose.get("name") != _COMPOSE_PROJECT_NAME:
        return None

    services = compose.get("services")
    service = services.get(_SERVICE_NAME) if isinstance(services, dict) else None
    if not isinstance(service, dict):
        return None
    if not _uses_file_backend(service) or not _uses_read_only_secret_mount(service):
        return None

    return ComposeHostProject(root=root, secret_root=root / _HOST_SECRET_ROOT)


def _has_guardrail_hub_project_identity(root: Path) -> bool:
    """Verify stable Python package/entrypoint identity for this checkout."""
    try:
        with (root / "pyproject.toml").open("rb") as handle:
            metadata = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    project = metadata.get("project")
    if not isinstance(project, dict) or project.get("name") != _PYTHON_PROJECT_NAME:
        return False
    scripts = project.get("scripts")
    return (
        isinstance(scripts, dict)
        and scripts.get("guardrail-hub") == _CONSOLE_SCRIPT
    )


def _uses_file_backend(service: dict[str, Any]) -> bool:
    environment = service.get("environment")
    if isinstance(environment, dict):
        return environment.get("GUARDRAILHUB_CREDENTIAL_BACKEND") == "file"
    if isinstance(environment, list):
        return "GUARDRAILHUB_CREDENTIAL_BACKEND=file" in environment
    return False


def _uses_read_only_secret_mount(service: dict[str, Any]) -> bool:
    volumes = service.get("volumes")
    if not isinstance(volumes, list):
        return False
    for volume in volumes:
        if isinstance(volume, str):
            fields = volume.split(":")
            if len(fields) >= 3 and fields[0] == "./secrets" and fields[1] == _RUNTIME_SECRET_MOUNT:
                if "ro" in fields[2:]:
                    return True
        elif isinstance(volume, dict):
            if (
                volume.get("source") == "./secrets"
                and volume.get("target") == _RUNTIME_SECRET_MOUNT
                and volume.get("read_only") is True
            ):
                return True
    return False


class ComposeHostCredentialProvisioner:
    """Provision credentials only into a recognized Compose project's host root.

    The implementation deliberately exposes the minimal ``get``/``set`` shape
    used by the setup workflow.  ``get`` is a presence check and returns a
    sentinel rather than reading plaintext from an existing secret file.
    """

    def __init__(self, project: ComposeHostProject) -> None:
        self._project = project
        self._root = project.secret_root

    def get(self, provider_id: str) -> str:
        """Confirm a regular existing target without reading its secret value."""
        target = self._target_for(provider_id)
        self._inspect_existing_secret_root(provider_id)
        try:
            target_stat = os.lstat(target)
        except FileNotFoundError as exc:
            raise CredentialNotFoundError(provider_id) from exc
        except OSError as exc:
            raise CredentialBackendError(provider_id, "cannot inspect host secret") from exc
        if _is_link_or_reparse(target_stat) or not stat.S_ISREG(target_stat.st_mode):
            raise CredentialBackendError(provider_id, "host secret target is not a regular file")
        if os.name == "nt":
            self._apply_host_permissions(provider_id, self._root, is_directory=True)
            self._apply_host_permissions(provider_id, target, is_directory=False)
        return "configured"

    def set(self, provider_id: str, credential: str) -> None:
        """Atomically write a credential with restrictive host permissions."""
        credential = credential
        temporary_path: Optional[Path] = None
        try:
            target = self._target_for(provider_id)
            encoded = credential.encode("utf-8")
            if len(encoded) > MAX_CREDENTIAL_FILE_SIZE_BYTES:
                raise CredentialBackendError(
                    provider_id,
                    "credential exceeds the maximum supported file size",
                )
            self._ensure_secret_root(provider_id)
            self._reject_unsafe_existing_target(provider_id, target)

            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".guardrailhub-", dir=self._root
            )
            temporary_path = Path(temporary_name)
            try:
                if os.name != "nt" and hasattr(os, "fchmod"):
                    os.fchmod(descriptor, 0o600)
                elif os.name != "nt":
                    os.chmod(temporary_path, 0o600)
                with os.fdopen(descriptor, "wb", closefd=True) as handle:
                    descriptor = -1
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                if os.name == "nt":
                    # Apply and verify the protected DACL while the replacement
                    # is still private. The old credential remains untouched if
                    # either operation fails.
                    self._apply_host_permissions(
                        provider_id, temporary_path, is_directory=False
                    )
                os.replace(temporary_path, target)
                temporary_path = None
                _fsync_directory(self._root)
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        except CredentialBackendError:
            self._cleanup_temporary_or_raise(provider_id, temporary_path)
            raise
        except (OSError, UnicodeError, ValueError) as exc:
            self._cleanup_temporary_or_raise(provider_id, temporary_path)
            raise CredentialBackendError(
                provider_id, "unable to provision host secret securely"
            ) from exc
        finally:
            # Cleanup is owned by the exception paths above. Successful replace
            # clears temporary_path only after atomic publication.
            temporary_path = None
            del credential

    def _cleanup_temporary_or_raise(
        self, provider_id: str, temporary_path: Optional[Path]
    ) -> None:
        """Remove a sensitive temp artifact or report required operator action."""
        if temporary_path is None:
            return
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError as exc:
            raise CredentialBackendError(
                provider_id,
                "temporary credential cleanup failed; a temporary artifact "
                f"under '{self._root}' may require operator cleanup",
            ) from exc

    def _target_for(self, provider_id: str) -> Path:
        _validate_provider_id(provider_id)
        try:
            approved_root = self._project.root.resolve(strict=True)
            root_parent = self._root.parent.resolve(strict=True)
        except (OSError, ValueError) as exc:
            raise CredentialBackendError(provider_id, "approved project root is unavailable") from exc
        if root_parent != approved_root:
            raise CredentialBackendError(provider_id, "host secret root is outside the approved project")
        return self._root / provider_id

    def _ensure_secret_root(self, provider_id: str) -> None:
        # Trust boundary: the checkout is operator-controlled and not being
        # concurrently rewritten by a hostile local actor. Static symlink,
        # junction, reparse, traversal, and containment misuse is rejected;
        # this Phase 5 provisioner does not claim race-free defense after an
        # attacker can replace the CLI's own project files and directories.
        try:
            root_stat = os.lstat(self._root)
        except FileNotFoundError:
            try:
                self._root.mkdir(mode=0o700)
            except FileExistsError:
                root_stat = os.lstat(self._root)
            except OSError as exc:
                raise CredentialBackendError(provider_id, "cannot create host secret directory") from exc
            else:
                root_stat = os.lstat(self._root)
        except OSError as exc:
            raise CredentialBackendError(provider_id, "cannot inspect host secret directory") from exc
        if _is_link_or_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
            raise CredentialBackendError(provider_id, "host secret directory is unsafe")
        self._apply_host_permissions(provider_id, self._root, is_directory=True)

    def _inspect_existing_secret_root(self, provider_id: str) -> None:
        """Reject a static link/reparse root without creating a missing root."""
        try:
            root_stat = os.lstat(self._root)
        except FileNotFoundError as exc:
            raise CredentialNotFoundError(provider_id) from exc
        except OSError as exc:
            raise CredentialBackendError(
                provider_id, "cannot inspect host secret directory"
            ) from exc
        if _is_link_or_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
            raise CredentialBackendError(
                provider_id, "host secret directory is unsafe"
            )

    @staticmethod
    def _apply_host_permissions(
        provider_id: str, path: Path, *, is_directory: bool
    ) -> None:
        """Apply POSIX modes or a verified protected Windows DACL."""
        if os.name == "nt":
            try:
                protect_windows_path(path, is_directory=is_directory)
            except WindowsAclError as exc:
                raise CredentialBackendError(
                    provider_id,
                    "unable to establish and verify protected Windows permissions",
                ) from exc
            return
        try:
            os.chmod(path, 0o700 if is_directory else 0o600)
        except OSError as exc:
            raise CredentialBackendError(
                provider_id, "cannot secure host secret permissions"
            ) from exc

    def _reject_unsafe_existing_target(self, provider_id: str, target: Path) -> None:
        try:
            target_stat = os.lstat(target)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise CredentialBackendError(provider_id, "cannot inspect host secret target") from exc
        if _is_link_or_reparse(target_stat) or not stat.S_ISREG(target_stat.st_mode):
            raise CredentialBackendError(provider_id, "host secret target is unsafe")


def _validate_provider_id(provider_id: str) -> None:
    """Apply the runtime file identity safety contract before host writes."""
    if not isinstance(provider_id, str) or not provider_id or provider_id.strip() != provider_id:
        raise CredentialBackendError(str(provider_id), "provider id is unsafe for a secret filename")
    if "\x00" in provider_id or provider_id in {".", ".."}:
        raise CredentialBackendError(provider_id, "provider id is unsafe for a secret filename")
    if os.path.isabs(provider_id) or "/" in provider_id or "\\" in provider_id:
        raise CredentialBackendError(provider_id, "provider id is unsafe for a secret filename")
    try:
        if Path(provider_id).name != provider_id or Path(provider_id).is_absolute():
            raise CredentialBackendError(provider_id, "provider id is unsafe for a secret filename")
        provider_id.encode("utf-8")
    except (UnicodeError, ValueError) as exc:
        raise CredentialBackendError(provider_id, "provider id is unsafe for a secret filename") from exc


def _is_link_or_reparse(file_stat: os.stat_result) -> bool:
    """Return True for POSIX links and Windows reparse points."""
    attributes = getattr(file_stat, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(file_stat.st_mode) or bool(attributes & reparse_flag)


def _fsync_directory(directory: Path) -> None:
    """Durably record the rename where directory fsync is supported."""
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "ComposeHostCredentialProvisioner",
    "ComposeHostProject",
    "recognize_compose_host_project",
]
