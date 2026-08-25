"""CredentialStore — secret storage abstraction for the Intelligence Layer.

Public API:

    CredentialStore(backend)      — thread-safe credential storage
    InMemoryCredentialBackend()   — in-process dict backend (tests/dev)
    WindowsCredentialManagerBackend() — Windows Credential Manager (production)

Exception hierarchy:

    CredentialStoreError
        CredentialNotFoundError
        CredentialBackendError

All exceptions inherit from ``LLMConfigurationError``.
"""

from app.intelligence.credentials.base import (
    CredentialBackend,
    CredentialBackendError,
    CredentialNotFoundError,
    CredentialStore,
    CredentialStoreError,
    InMemoryCredentialBackend,
)

__all__ = [
    "CredentialBackend",
    "CredentialBackendError",
    "CredentialNotFoundError",
    "CredentialStore",
    "CredentialStoreError",
    "InMemoryCredentialBackend",
]
