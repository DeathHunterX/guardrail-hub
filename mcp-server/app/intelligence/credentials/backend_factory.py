"""Default credential backend selection for the setup command.

The ``guardrail-hub setup`` command needs a *persistent* secure backend so that
stored credentials survive process restarts. This factory selects one based on
the host platform.

Design decision (fail-closed): the only persistent secure backend implemented
today is the Windows Credential Manager. On any other platform this factory
raises rather than silently falling back to a plaintext file store — a security
product must not persist secrets in the clear without an explicit, ratified
decision (ADR). Callers that have their own secure backend (or tests) inject it
directly and never reach this factory.
"""

from __future__ import annotations

import sys
from typing import Optional

from app.intelligence.credentials import CredentialBackend, CredentialBackendError


def build_default_credential_backend(
    platform: Optional[str] = None,
) -> CredentialBackend:
    """Return the default persistent secure credential backend for this host.

    Args:
        platform: Platform identifier to select on. Defaults to ``sys.platform``.
            Exposed for testability.

    Returns:
        A persistent, secure :class:`CredentialBackend` for the platform.

    Raises:
        CredentialBackendError: If no persistent secure backend is available for
            the platform. The caller should surface this as a clear setup error
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
    "build_default_credential_backend",
]
