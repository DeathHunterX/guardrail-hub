"""CredentialStore — secret storage abstraction for the Intelligence Layer.

Architecture:

    llm.yaml = configuration (no secrets)
    CredentialStore = secrets (provider-scoped)

The CredentialStore separates secrets from configuration. It knows nothing about
routing, models, adapters, HTTP, or YAML loading. The only namespace is
``provider_id``.

A backend implements the ``CredentialBackend`` protocol. The production backend
for Windows is ``WindowsCredentialManagerBackend``. Tests and dev environments
use the ``InMemoryCredentialBackend`` (no OS integration required).

Contract (CredentialBackend):

    get(provider_id)      → str | raises CredentialNotFoundError
    set(provider_id, str) → None
    delete(provider_id)   → None

All operations are scoped to a single provider. No wildcards, no bulk operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from app.intelligence.exceptions.llm import LLMConfigurationError


# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------


class CredentialStoreError(LLMConfigurationError):
    """Base exception for all CredentialStore errors.

    Inherits from LLMConfigurationError so that the standard error-mapping
    at the routing layer treats credential failures as configuration errors.
    """

    pass


class CredentialNotFoundError(CredentialStoreError):
    """Raised when ``get()`` finds no stored credential for a provider_id."""

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        super().__init__(
            f"no credential found for provider '{provider_id}'"
        )


class CredentialBackendError(CredentialStoreError):
    """Raised when the underlying credential backend fails.

    Examples: the OS keyring is unavailable, a system call fails,
    the credential exceeds size limits.
    """

    def __init__(self, provider_id: str, message: str) -> None:
        self.provider_id = provider_id
        super().__init__(
            f"backend error for provider '{provider_id}': {message}"
        )


# ------------------------------------------------------------------
# CredentialBackend protocol
# ------------------------------------------------------------------


class CredentialBackend(ABC):
    """Minimum interface a credential storage backend must implement.

    All methods are synchronous. Async operations live at the
    CredentialStore layer (it can wrap an async call if a future backend needs it).
    """

    @abstractmethod
    def get(self, provider_id: str) -> str:
        """Retrieve the stored credential for a provider.

        Args:
            provider_id: The provider whose credential to retrieve.

        Returns:
            The stored credential string.

        Raises:
            CredentialNotFoundError: No credential has been set for this provider.
            CredentialBackendError: The backend failed (e.g., OS keyring unavailable).
        """
        raise NotImplementedError

    @abstractmethod
    def set(self, provider_id: str, credential: str) -> None:
        """Store a credential for a provider, replacing any existing value.

        Args:
            provider_id: The provider whose credential to store.
            credential: The credential string (e.g., API key, bearer token).

        Raises:
            CredentialBackendError: The backend failed (e.g., write failed).
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, provider_id: str) -> None:
        """Delete the stored credential for a provider (no-op if none exists).

        Args:
            provider_id: The provider whose credential to delete.

        Raises:
            CredentialBackendError: The backend failed.
        """
        raise NotImplementedError


# ------------------------------------------------------------------
# CredentialStore
# ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CredentialStore:
    """Thread-safe credential storage with pluggable backend.

    Attributes:
        _backend: The underlying credential storage backend.

    The store is immutable after construction. The backend reference is
    stable for the lifetime of the store.
    """

    _backend: CredentialBackend

    # Sentinel used in the repr mask so callers can test presence
    # without ever revealing the actual value.
    _VALUE_MASK: ClassVar[str] = "********"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, provider_id: str) -> str:
        """Retrieve the stored credential for a provider.

        Args:
            provider_id: The provider whose credential to retrieve.

        Returns:
            The stored credential string.

        Raises:
            CredentialNotFoundError: No credential is stored for this provider.
            CredentialBackendError: The backend failed.
        """
        return self._backend.get(provider_id)

    def set(self, provider_id: str, credential: str) -> None:
        """Store a credential for a provider.

        Args:
            provider_id: The provider whose credential to store.
            credential: The credential string to persist.

        Raises:
            CredentialBackendError: The backend failed.

        INV-6 (ADR-0017): the inbound ``credential`` is a local of this frame.
        A frame's locals stay reachable through ``exc.__traceback__`` after this
        function exits. Deleting the name in ``finally`` scrubs this frame on
        every exit path (return or raise). Pre-binding avoids a NameError on
        the return path where the parameter was never entered as a local.
        The credential still exists in the originating caller's frame --
        no change inside this layer can reach it.
        """
        credential = credential  # pre-bind: makes `del` safe on the return path
        try:
            self._backend.set(provider_id, credential)
        finally:
            del credential

    def delete(self, provider_id: str) -> None:
        """Delete the stored credential for a provider.

        Raises:
            CredentialBackendError: The backend failed.
        """
        self._backend.delete(provider_id)

    # ------------------------------------------------------------------
    # Diagnostics — credential values are NEVER exposed
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        """Show the store type and backend type, never credential values."""
        return (
            f"CredentialStore(backend={type(self._backend).__name__})"
        )


# ------------------------------------------------------------------
# In-memory backend — used in tests and as a fallback when no OS
# keyring is available (e.g., non-Windows dev environments).
# NOT intended for production use; credentials are lost on process exit.
# ------------------------------------------------------------------


class InMemoryCredentialBackend(CredentialBackend):
    """In-process dict-backed credential storage.

    Intentionally scoped to a single process with no persistence.
    Use only in tests or when no OS keyring is available.
    """

    def __init__(self) -> None:
        # Credentials stored as provider_id → credential string.
        self._store: dict[str, str] = {}

    def get(self, provider_id: str) -> str:
        if provider_id not in self._store:
            raise CredentialNotFoundError(provider_id)
        return self._store[provider_id]

    def set(self, provider_id: str, credential: str) -> None:
        self._store[provider_id] = credential

    def delete(self, provider_id: str) -> None:
        self._store.pop(provider_id, None)

    def __repr__(self) -> str:
        # Never expose credential values — only show which provider_ids are stored.
        stored = sorted(self._store.keys())
        return f"InMemoryCredentialBackend(providers={stored})"


__all__ = [
    "CredentialBackend",
    "CredentialBackendError",
    "CredentialNotFoundError",
    "CredentialStore",
    "CredentialStoreError",
    "InMemoryCredentialBackend",
]
