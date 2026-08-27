"""Read-only credential backend backed by process environment variables.

This backend satisfies the :class:`CredentialBackend` contract by reading secrets
from ``os.environ``. It is intentionally a thin, generic adapter: it receives a
pre-computed ``lookup_key`` (an environment variable name) from the caller and
returns the variable's value. It has no knowledge of provider records, auth
configuration, ``api_key_env`` semantics, or any other application-level concept.

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

from app.intelligence.credentials.base import (
    CredentialBackend,
    CredentialBackendError,
    CredentialNotFoundError,
)


class EnvVarCredentialBackend(CredentialBackend):
    """Read-only credential backend reading secrets from the process environment.

    Each credential is a single environment variable whose name is the
    ``lookup_key`` passed to :meth:`get`. The backend treats ``lookup_key``
    as a pure string and is unaware of how it was derived.

    This backend is **read-only** by design. ``set`` and ``delete`` are
    refused unconditionally because secrets are provisioned by the deployment
    platform, not by the application.

    Args:
        No constructor arguments. The backend is stateless — all state lives
        in ``os.environ``.

    Example::

        # ProviderManager computes the lookup key; the backend receives it.
        backend = EnvVarCredentialBackend()
        secret = backend.get("OPENAI_API_KEY")        # reads os.environ["OPENAI_API_KEY"]
        secret = backend.get("GUARDRAILHUB_CREDENTIAL__OPENAI")  # same pattern
    """

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def get(self, lookup_key: str) -> str:
        """Retrieve the value of the environment variable named ``lookup_key``.

        Args:
            lookup_key: The exact name of the environment variable to read.

        Returns:
            The environment variable's value.

        Raises:
            CredentialNotFoundError: No variable with this name exists in
                ``os.environ``, or the variable exists but is set to an empty
                string.
            CredentialBackendError: The operation failed for a reason other
                than a missing variable.
        """
        try:
            value = os.environ[lookup_key]
        except KeyError:
            # Raise a credential-domain exception so callers can handle it
            # uniformly without importing ``os``.
            raise CredentialNotFoundError(lookup_key)

        # Treat an empty string as absent: an empty env var is a configuration
        # error (the variable is defined but has no value), not a valid secret.
        if not value:
            raise CredentialNotFoundError(lookup_key)

        return value

    # ------------------------------------------------------------------
    # Read-only contract (INV-3)
    # ------------------------------------------------------------------

    def set(self, lookup_key: str, credential: str) -> None:
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
                lookup_key,
                "credentials are managed by the deployment platform; "
                "this backend is read-only",
            )
        finally:
            del credential

    def delete(self, lookup_key: str) -> None:
        """Refuse to delete credentials.

        Raises:
            CredentialBackendError: always, because this backend is read-only.
        """
        raise CredentialBackendError(
            lookup_key,
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
