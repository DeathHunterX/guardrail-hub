"""Read-only credential backend backed by process environment variables.

This backend satisfies the :class:`CredentialBackend` contract by reading secrets
from ``os.environ``. It receives a provider identity from the caller, projects it
through a pre-composed provider-to-environment-name mapping, then returns the
environment variable's value. It has no knowledge of provider records, auth
configuration, or ``api_key_env`` semantics.

This makes it suitable as a drop-in backend for any deployment where credentials
are injected as environment variables (e.g. systemd unit files, container run
commands, CI/CD pipelines). It is **read-only**: secrets are provisioned by the
deployment platform, not by the application.

Security constraints enforced at this boundary:

* INV-3  read-only: ``get`` is supported; ``set`` / ``delete`` raise
         ``CredentialBackendError``.
* INV-6  the secret value never appears in ``repr`` / ``str``, exceptions,
         or logs. No error raised from this backend carries the secret value.
"""

from __future__ import annotations

import os
from typing import Mapping

from app.intelligence.credentials.base import (
    CredentialBackend,
    CredentialBackendError,
    CredentialNotFoundError,
)


class EnvVarCredentialBackend(CredentialBackend):
    """Read-only credential backend reading secrets from the process environment.

    Each credential is addressed by its provider ID. The backend maps that
    identity to a configured environment-variable name before reading it.

    This backend is **read-only** by design. ``set`` and ``delete`` are
    refused unconditionally because secrets are provisioned by the deployment
    platform, not by the application.

    Args:
        provider_env_names: Non-secret mapping from provider IDs to environment
            variable names. This is composed by bootstrap from the frozen catalog.

    Example::

        backend = EnvVarCredentialBackend({"openai-cloud": "OPENAI_API_KEY"})
        secret = backend.get("openai-cloud")  # reads os.environ["OPENAI_API_KEY"]
    """

    def __init__(self, provider_env_names: Mapping[str, str]) -> None:
        self._provider_env_names = dict(provider_env_names)

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def get(self, provider_id: str) -> str:
        """Retrieve a provider credential from its configured environment variable.

        Args:
            provider_id: The logical credential identity.

        Returns:
            The environment variable's value.

        Raises:
            CredentialNotFoundError: The provider has no configured environment
                variable, the variable is absent, or it is empty.
            CredentialBackendError: The operation failed for a reason other
                than a missing variable.
        """
        try:
            env_name = self._provider_env_names[provider_id]
        except KeyError:
            raise CredentialNotFoundError(provider_id)

        try:
            value = os.environ[env_name]
        except KeyError:
            # Raise a credential-domain exception so callers can handle it
            # uniformly without importing ``os``.
            raise CredentialNotFoundError(provider_id)

        # Treat an empty string as absent: an empty env var is a configuration
        # error (the variable is defined but has no value), not a valid secret.
        if not value:
            raise CredentialNotFoundError(provider_id)

        return value

    # ------------------------------------------------------------------
    # Read-only contract (INV-3)
    # ------------------------------------------------------------------

    def set(self, provider_id: str, credential: str) -> None:
        """Refuse to write credentials.

        This backend is read-only because secrets are provisioned by the
        deployment platform, not by the application. ``CredentialBackendError``
        is raised unconditionally; the ``credential`` argument is never
        inspected, logged, or written.

        The refusal's traceback spans this frame, so the ``credential`` local
        would be reachable through ``exc.__traceback__`` after the exception
        leaves this function. ``finally: del credential`` scrubs this frame
        only. The originating caller's frame is outside this module entirely.
        """
        try:
            raise CredentialBackendError(
                provider_id,
                "credentials are managed by the deployment platform; "
                "this backend is read-only",
            )
        finally:
            del credential

    def delete(self, provider_id: str) -> None:
        """Refuse to delete credentials.

        Raises:
            CredentialBackendError: always, because this backend is read-only.
        """
        raise CredentialBackendError(
            provider_id,
            "credentials are managed by the deployment platform; "
            "this backend is read-only",
        )

    # ------------------------------------------------------------------
    # Diagnostics — never expose secret values (INV-6)
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        """Show the backend type only; no secret values or variable names."""
        return "EnvVarCredentialBackend()"


__all__ = [
    "EnvVarCredentialBackend",
]
