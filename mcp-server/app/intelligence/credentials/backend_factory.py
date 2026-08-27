"""Credential backend selection for the application runtime and the setup command.

This module provides two entry points:

``build_credential_backend()``
    Selects the runtime credential backend based on the host platform and the
    ``GUARDRAILHUB_CREDENTIAL_BACKEND`` environment variable. Used by
    application bootstrap to wire the CredentialStore into ProviderManager.

``build_default_credential_backend(platform)``
    (Phase 5B legacy API.) Returns the default persistent secure backend for
    the setup command. On Windows this is Windows Credential Manager; on all
    other platforms it raises ``CredentialBackendError``. Retained for
    backward compatibility with the setup command's direct call path.

Design principle (fail-closed): the application never silently falls back to
an insecure credential store. Every backend selection failure produces a clear
``CredentialBackendError`` that names the failing combination and directs the
operator to a resolution.
"""

from __future__ import annotations

import os
import sys
from typing import Final, Optional

from app.intelligence.credentials import CredentialBackend, CredentialBackendError

# Import the constants from container_backend to avoid duplication.
# container_backend.py is Phase 5C and must not be modified.
from app.intelligence.credentials.container_backend import (
    ContainerFileCredentialBackend,
    DEFAULT_SECRETS_DIR,
)

# Supported mode values after normalisation.
_VALID_MODES: Final[frozenset[str]] = frozenset({"windows", "wincm", "file", "env"})


# ----------------------------------------------------------------------
# Public API — application runtime bootstrap
# ----------------------------------------------------------------------


def build_credential_backend(
    platform: Optional[str] = None,
) -> CredentialBackend:
    """Select and return the credential backend for this runtime environment.

    The backend is selected from the ``GUARDRAILHUB_CREDENTIAL_BACKEND``
    environment variable, normalised to lowercase with surrounding whitespace
    removed. All comparison is case-insensitive.

    Behaviour matrix:

    ============  =========================  =====================================
    Platform      GUARDRAILHUB_CREDENTIAL_    Result
                  BACKEND
    ============  =========================  =====================================
    Windows       unset / windows / wincm     WindowsCredentialManagerBackend()
    Windows       file                       CredentialBackendError
    Windows       env                        CredentialBackendError
    Windows       unknown                    CredentialBackendError
    non-Windows   unset                     CredentialBackendError
    non-Windows   windows / wincm            CredentialBackendError
    non-Windows   file                       ContainerFileCredentialBackend(secrets_dir)
    non-Windows   env                        EnvVarCredentialBackend()
    non-Windows   unknown                    CredentialBackendError
    ============  =========================  =====================================

    ``GUARDRAILHUB_SECRETS_DIR`` controls the directory passed to
    ``ContainerFileCredentialBackend``:

    =============================  ============================================
    Value                         Behaviour
    =============================  ============================================
    unset                         Use ``/run/secrets`` (Docker/K8s default)
    empty string (``""``)         ``CredentialBackendError``
    whitespace-only               ``CredentialBackendError``
    valid non-empty path          Passed verbatim as ``secrets_dir``
    =============================  ============================================

    Args:
        platform: Platform identifier (``sys.platform``). Defaults to the
            running platform. Exposed for testability so tests can exercise
            Windows and non-Windows branches on a single machine.

    Returns:
        A configured :class:`CredentialBackend` for this environment.

    Raises:
        CredentialBackendError: No supported backend for this platform+mode
            combination, or an invalid ``GUARDRAILHUB_SECRETS_DIR`` value.
    """
    resolved_platform = platform if platform is not None else sys.platform

    # 1. Read and normalise the backend mode.
    raw_mode = os.environ.get("GUARDRAILHUB_CREDENTIAL_BACKEND", "")
    mode = raw_mode.strip().lower()

    # 2. Select by platform + mode.
    if resolved_platform == "win32":
        if mode in ("windows", "wincm", ""):
            from app.intelligence.credentials.windows_backend import (
                WindowsCredentialManagerBackend,
            )
            return WindowsCredentialManagerBackend()

        # file / env / unknown → fail closed
        _raise_unsupported(resolved_platform, raw_mode or "<unset>")

    # non-Windows (linux, darwin, ...)
    if mode == "file":
        # Validate GUARDRAILHUB_SECRETS_DIR: empty or whitespace → error.
        # Unset → use DEFAULT_SECRETS_DIR (/run/secrets).
        _raw_secrets_dir = os.environ.get("GUARDRAILHUB_SECRETS_DIR", "")
        if _raw_secrets_dir.strip() == "":
            # Either unset (→ use default) or empty/whitespace (→ error).
            if _raw_secrets_dir == "" and "GUARDRAILHUB_SECRETS_DIR" not in os.environ:
                secrets_dir = DEFAULT_SECRETS_DIR
            else:
                # Set but empty or whitespace-only → configuration error.
                raise CredentialBackendError(
                    "<runtime-backend>",
                    "GUARDRAILHUB_SECRETS_DIR is set but empty or whitespace-only; "
                    "set it to a valid directory path.",
                )
        else:
            secrets_dir = _raw_secrets_dir
        return ContainerFileCredentialBackend(secrets_dir=secrets_dir)

    if mode == "env":
        from app.intelligence.credentials.env_backend import (
            EnvVarCredentialBackend,
        )
        return EnvVarCredentialBackend()

    # unset, windows, wincm, or unknown → fail closed
    _raise_unsupported(resolved_platform, raw_mode or "<unset>")


def _raise_unsupported(platform: str, mode: str) -> "CredentialBackendError":
    """Raise CredentialBackendError for an unsupported platform+mode combination.

    Args:
        platform: ``sys.platform`` value.
        mode: The raw (un-normalised) GUARDRAILHUB_CREDENTIAL_BACKEND value.
    """
    raise CredentialBackendError(
        "<runtime-backend>",
        (
            f"no credential backend available for platform '{platform}' "
            f"with GUARDRAILHUB_CREDENTIAL_BACKEND='{mode}'. "
            f"Supported modes: {sorted(_VALID_MODES)}. "
            f"On Windows use 'windows'; on Linux/Darwin use 'file' (with "
            f"GUARDRAILHUB_SECRETS_DIR set) or 'env'."
        ),
    )


# ----------------------------------------------------------------------
# Legacy API — setup command (Phase 5B)
# Retained for backward compatibility with direct setup-command calls.
# ----------------------------------------------------------------------


def build_default_credential_backend(
    platform: Optional[str] = None,
) -> CredentialBackend:
    """Return the default persistent secure credential backend for the setup command.

    .. deprecated::
        New application code should use :func:`build_credential_backend` instead.
        This function is retained for the setup command's direct call path.

    Args:
        platform: Platform identifier to select on. Defaults to ``sys.platform``.
            Exposed for testability.

    Returns:
        A persistent, secure :class:`CredentialBackend` for the platform.

    Raises:
        CredentialBackendError: If no persistent secure backend is available for
            the platform. Callers should surface this as a clear setup error
            and suggest injecting a backend explicitly.
    """
    resolved_platform = platform if platform is not None else sys.platform

    if resolved_platform == "win32":
        # Imported lazily: the module binds Windows-only native symbols and
        # should not be imported on platforms where it cannot be used.
        from app.intelligence.credentials.windows_backend import (
            WindowsCredentialManagerBackend,
        )
        return WindowsCredentialManagerBackend()

    # Fail closed: no plaintext fallback without a ratified decision.
    raise CredentialBackendError(
        "<default-backend>",
        (
            f"no persistent secure credential backend is available for platform "
            f"'{resolved_platform}'; Windows Credential Manager is currently the "
            f"only supported store. Inject a CredentialStore backend explicitly "
            f"to run setup on this platform."
        ),
    )


__all__ = [
    "build_credential_backend",
    "build_default_credential_backend",
]
