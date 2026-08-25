"""Windows Credential Manager backend for CredentialStore.

Stores credentials in the Windows Credential Manager (WCM) via the native
advapi32.dll C API, using ctypes for a zero-dependency implementation.

Namespace in WCM: ``GuardrailHub:<provider_id>``
This isolates Guardrail Hub credentials from all other stored credentials.

Windows Credential Manager limits:
- Target name: max 126 wide characters (CRED_MAX_GENERIC_TARGET_NAME_LENGTH - 1)
- Username: max 256 wide characters (CRED_MAX_USERNAME_LENGTH)
- Credential blob: max 512 bytes (CRED_MAX_CREDENTIAL_BLOB_SIZE)
  — sufficient for API keys and bearer tokens; not suitable for certificates.

Raises ``CredentialBackendError`` on any native API failure or when used on
a non-Windows platform.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import sys
from typing import TYPE_CHECKING, ClassVar

from app.intelligence.credentials.base import (
    CredentialBackend,
    CredentialBackendError,
    CredentialNotFoundError,
)

if TYPE_CHECKING:
    pass


# ------------------------------------------------------------------
# Windows type aliases (mirrors the C declarations)
# ------------------------------------------------------------------

PVOID = ctypes.c_void_p
LPWSTR = ctypes.c_wchar_p
LPCWSTR = ctypes.c_wchar_p
DWORD = ctypes.wintypes.DWORD
BOOL = ctypes.wintypes.BOOL

# ------------------------------------------------------------------
# Windows Credential Manager constants
# https://docs.microsoft.com/en-us/windows/win32/api/wincred/
# ------------------------------------------------------------------

CRED_TYPE_GENERIC: int = 1

CRED_PERSIST_LOCAL_MACHINE: int = 2

CRED_MAX_GENERIC_TARGET_NAME_LENGTH: int = 127
CRED_MAX_USERNAME_LENGTH: int = 256
CRED_MAX_CREDENTIAL_BLOB_SIZE: int = 512

ERROR_NOT_FOUND: int = 1168

# ------------------------------------------------------------------
# Windows structures
# ------------------------------------------------------------------


class _CREDENTIAL(ctypes.Structure):
    """ctypes mapping of the CREDENTIAL structure.

    https://docs.microsoft.com/en-us/windows/win32/api/wincred/ns-wincred-credential
    """

    _fields_ = [
        ("Flags", DWORD),
        ("Type", DWORD),
        ("TargetName", LPWSTR),
        ("Comment", LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", DWORD),
        ("CredentialBlob", PVOID),
        ("Persist", DWORD),
        ("AttributeCount", DWORD),
        ("Attributes", PVOID),
        ("TargetAlias", LPWSTR),
        ("UserName", LPWSTR),
    ]


# ------------------------------------------------------------------
# Native function bindings — loaded lazily to avoid AttributeError on
# non-Windows platforms at import time.
# ------------------------------------------------------------------


def _get_advapi32() -> "ctypes._FuncPtr":  # type: ignore[name-defined]
    """Return the advapi32 DLL, raising CredentialBackendError on non-Windows."""
    if sys.platform != "win32":
        raise CredentialBackendError(
            "<windows>",
            "Windows Credential Manager backend is only available on Windows",
        )
    try:
        return ctypes.windll.advapi32
    except AttributeError:
        raise CredentialBackendError(
            "<windows>",
            "Windows Credential Manager backend requires ctypes.windll (not available)",
        )


# ------------------------------------------------------------------
# Credential namespace
# ------------------------------------------------------------------

# Namespace prefix stored in WCM to avoid collisions with other apps.
_TARGET_PREFIX: ClassVar[str] = "GuardrailHub:"


def _make_target(provider_id: str) -> str:
    """Build a WCM target name for a provider.

    The full target name is ``GuardrailHub:<provider_id>``.
    ``provider_id`` is assumed to be a valid non-empty ASCII identifier;
    callers are responsible for validating it before calling this function.
    """
    return f"{_TARGET_PREFIX}{provider_id}"


# ------------------------------------------------------------------
# WindowsCredentialManagerBackend
# ------------------------------------------------------------------


class WindowsCredentialManagerBackend(CredentialBackend):
    """Windows Credential Manager backend for CredentialStore.

    Credentials are stored persistently in the Windows Credential Manager under
    the ``GuardrailHub:`` namespace. They survive process restarts and user
    logouts (subject to the credential's persistence level, which is set to
    ``CRED_PERSIST_LOCAL_MACHINE``).

    **Requirements:** Windows XP or later; advapi32.dll (standard on all Windows).
    No third-party packages needed.

    **Limitations:**
    - Credential blob is capped at 512 bytes. API keys and bearer tokens fit easily.
    - Only available on Windows.
    """

    def _get_last_error(self) -> int:
        return ctypes.get_last_error()

    def _raise_from_win32(self, provider_id: str, action: str) -> None:
        code = self._get_last_error()
        raise CredentialBackendError(
            provider_id,
            f"{action} failed (Windows error {code})",
        )

    def get(self, provider_id: str) -> str:
        advapi32 = _get_advapi32()
        target = _make_target(provider_id)
        p_cred: ctypes.POINTER(_CREDENTIAL) = ctypes.POINTER(_CREDENTIAL)()

        ok = advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(p_cred))
        if not ok:
            code = self._get_last_error()
            if code == ERROR_NOT_FOUND:
                raise CredentialNotFoundError(provider_id)
            raise CredentialBackendError(
                provider_id,
                f"CredReadW failed (Windows error {code})",
            )

        try:
            cred = p_cred.contents
            blob_size = cred.CredentialBlobSize
            blob_ptr = cred.CredentialBlob
            if blob_size == 0 or blob_ptr is None:
                raise CredentialBackendError(
                    provider_id,
                    "stored credential blob is empty",
                )
            raw = ctypes.string_at(blob_ptr, blob_size)
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1")
        finally:
            advapi32.CredFree(p_cred)

    def set(self, provider_id: str, credential: str) -> None:
        advapi32 = _get_advapi32()
        target = _make_target(provider_id)
        if len(target) >= CRED_MAX_GENERIC_TARGET_NAME_LENGTH:
            raise CredentialBackendError(
                provider_id,
                f"provider_id too long (max {CRED_MAX_GENERIC_TARGET_NAME_LENGTH - 1} chars "
                f"including namespace prefix, got {len(target)})",
            )

        blob = credential.encode("utf-8")
        blob_size = len(blob)
        if blob_size > CRED_MAX_CREDENTIAL_BLOB_SIZE:
            raise CredentialBackendError(
                provider_id,
                f"credential exceeds Windows Credential Manager size limit "
                f"({CRED_MAX_CREDENTIAL_BLOB_SIZE} bytes, got {blob_size})",
            )

        blob_buf = ctypes.create_string_buffer(blob, blob_size)

        cred = _CREDENTIAL(
            Flags=0,
            Type=CRED_TYPE_GENERIC,
            TargetName=target,
            Comment="Guardrail Hub LLM credential",
            LastWritten=wintypes.FILETIME(0, 0),
            CredentialBlobSize=blob_size,
            CredentialBlob=ctypes.cast(blob_buf, PVOID),
            Persist=CRED_PERSIST_LOCAL_MACHINE,
            AttributeCount=0,
            Attributes=None,
            TargetAlias=None,
            UserName=None,
        )

        ok = advapi32.CredWriteW(ctypes.byref(cred), 0)
        if not ok:
            self._raise_from_win32(provider_id, "CredWriteW")

    def delete(self, provider_id: str) -> None:
        advapi32 = _get_advapi32()
        target = _make_target(provider_id)
        ok = advapi32.CredDeleteW(target, CRED_TYPE_GENERIC, 0)
        if not ok:
            code = self._get_last_error()
            if code == ERROR_NOT_FOUND:
                return
            raise CredentialBackendError(
                provider_id,
                f"CredDeleteW failed (Windows error {code})",
            )


__all__ = [
    "WindowsCredentialManagerBackend",
]
