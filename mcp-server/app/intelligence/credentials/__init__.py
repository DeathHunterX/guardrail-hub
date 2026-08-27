"""CredentialStore — secret storage abstraction for the Intelligence Layer.

Public API:

    CredentialStore(backend)      — thread-safe credential storage
    InMemoryCredentialBackend()   — in-process dict backend (tests/dev)
    EnvVarCredentialBackend()     — read-only environment-variable backend (prod Linux/env)
    WindowsCredentialManagerBackend() — Windows Credential Manager (prod Windows)

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
from app.intelligence.credentials.env_backend import EnvVarCredentialBackend

__all__ = [
    "CredentialBackend",
    "CredentialBackendError",
    "CredentialNotFoundError",
    "CredentialStore",
    "CredentialStoreError",
    "EnvVarCredentialBackend",
    "InMemoryCredentialBackend",
]
