"""Unit tests for credential backend factory selection.

Phase 5D tests cover:
- build_credential_backend(): platform/mode matrix (D2, D3)
- GUARDRAILHUB_SECRETS_DIR wiring
- Case normalisation
- Unknown mode rejection

Phase 5B legacy tests cover:
- build_default_credential_backend(): Windows returns WCMB,
  non-Windows fails closed.
"""

import os
import unittest

from app.intelligence.credentials import CredentialBackendError
from app.intelligence.credentials.backend_factory import (
    build_credential_backend,
    build_default_credential_backend,
    build_provider_env_var_names,
)
from app.intelligence.credentials.container_backend import (
    ContainerFileCredentialBackend,
    DEFAULT_SECRETS_DIR,
)
from app.intelligence.credentials.env_backend import EnvVarCredentialBackend
from app.intelligence.credentials.windows_backend import (
    WindowsCredentialManagerBackend,
)
from app.intelligence.registry.models.provider import (
    AuthConfig,
    AuthType,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


# ---------------------------------------------------------------------------
# Helper: temporarily set/unset environment variables.
# ---------------------------------------------------------------------------


def _env(**vars):
    """Context manager: temporarily set/unset environment variables.

    Usage::

        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="env"):
            ...

    Keys set to None are deleted. Keys set to a string are set.
    After the context, the original environment is restored.
    """
    return _EnvPatch(**vars)


class _EnvPatch:
    def __init__(self, **vars):
        self._vars = vars
        self._orig = {}

    def __enter__(self):
        for k, v in self._vars.items():
            self._orig[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return None

    def __exit__(self, *args):
        for k, v in self._orig.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# Phase 5D: build_credential_backend() tests
# ---------------------------------------------------------------------------


class TestBuildCredentialBackend_Windows(unittest.TestCase):
    """Windows platform: mode selection and normalisation."""

    def test_windows_unset_returns_wcmb(self):
        """On Windows with no env var, WindowsCredentialManagerBackend is returned."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND=None):
            backend = build_credential_backend(platform="win32")
        self.assertIsInstance(backend, WindowsCredentialManagerBackend)

    def test_windows_explicit_windows(self):
        """Windows + GUARDRAILHUB_CREDENTIAL_BACKEND=windows -> WCMB."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="windows"):
            backend = build_credential_backend(platform="win32")
        self.assertIsInstance(backend, WindowsCredentialManagerBackend)

    def test_windows_explicit_wincm(self):
        """Windows + GUARDRAILHUB_CREDENTIAL_BACKEND=wincm -> WCMB."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="wincm"):
            backend = build_credential_backend(platform="win32")
        self.assertIsInstance(backend, WindowsCredentialManagerBackend)

    def test_windows_file_rejected(self):
        """Windows + GUARDRAILHUB_CREDENTIAL_BACKEND=file -> CredentialBackendError."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="file"):
            with self.assertRaises(CredentialBackendError):
                build_credential_backend(platform="win32")

    def test_windows_env_rejected(self):
        """Windows + GUARDRAILHUB_CREDENTIAL_BACKEND=env -> CredentialBackendError."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="env"):
            with self.assertRaises(CredentialBackendError):
                build_credential_backend(platform="win32")

    def test_windows_unknown_rejected(self):
        """Windows + unknown mode -> CredentialBackendError."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="foobar"):
            with self.assertRaises(CredentialBackendError):
                build_credential_backend(platform="win32")


class TestBuildCredentialBackend_NonWindows(unittest.TestCase):
    """Non-Windows (Linux/Darwin) platform: mode selection and normalisation."""

    def test_linux_unset_rejected(self):
        """Linux with no env var -> CredentialBackendError (fail-closed)."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND=None):
            with self.assertRaises(CredentialBackendError):
                build_credential_backend(platform="linux")

    def test_linux_windows_rejected(self):
        """Linux + GUARDRAILHUB_CREDENTIAL_BACKEND=windows -> CredentialBackendError."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="windows"):
            with self.assertRaises(CredentialBackendError):
                build_credential_backend(platform="linux")

    def test_linux_wincm_rejected(self):
        """Linux + GUARDRAILHUB_CREDENTIAL_BACKEND=wincm -> CredentialBackendError."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="wincm"):
            with self.assertRaises(CredentialBackendError):
                build_credential_backend(platform="linux")

    def test_linux_file_returns_container_backend(self):
        """Linux + GUARDRAILHUB_CREDENTIAL_BACKEND=file -> ContainerFileCredentialBackend."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="file"):
            backend = build_credential_backend(platform="linux")
        self.assertIsInstance(backend, ContainerFileCredentialBackend)

    def test_linux_env_returns_env_backend(self):
        """Linux + GUARDRAILHUB_CREDENTIAL_BACKEND=env -> EnvVarCredentialBackend."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="env"):
            backend = build_credential_backend(platform="linux")
        self.assertIsInstance(backend, EnvVarCredentialBackend)

    def test_linux_unknown_rejected(self):
        """Linux + unknown mode -> CredentialBackendError."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="randomvalue"):
            with self.assertRaises(CredentialBackendError):
                build_credential_backend(platform="linux")


class TestBuildCredentialBackend_ModeNormalisation(unittest.TestCase):
    """Case-insensitivity and whitespace normalisation."""

    def test_case_insensitive_windows(self):
        """Mode value is case-insensitive (Windows)."""
        for value in ("WINDOWS", "Windows", "WiNdOwS", "  windows  "):
            with self.subTest(value=value):
                with _env(GUARDRAILHUB_CREDENTIAL_BACKEND=value):
                    backend = build_credential_backend(platform="win32")
                self.assertIsInstance(backend, WindowsCredentialManagerBackend)

    def test_case_insensitive_linux_file(self):
        """Mode value is case-insensitive (Linux file mode)."""
        for value in ("FILE", "File", "  file  ", "\tFILE\t"):
            with self.subTest(value=value):
                with _env(GUARDRAILHUB_CREDENTIAL_BACKEND=value):
                    backend = build_credential_backend(platform="linux")
                self.assertIsInstance(backend, ContainerFileCredentialBackend)

    def test_case_insensitive_linux_env(self):
        """Mode value is case-insensitive (Linux env mode)."""
        for value in ("ENV", "Env", "  env  "):
            with self.subTest(value=value):
                with _env(GUARDRAILHUB_CREDENTIAL_BACKEND=value):
                    backend = build_credential_backend(platform="linux")
                self.assertIsInstance(backend, EnvVarCredentialBackend)

    def test_unknown_normalised(self):
        """Unknown mode normalised and rejected (Linux)."""
        # " unknown " -> "unknown" after strip+lower -> unknown -> rejected
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="  unknown_mode  "):
            with self.assertRaises(CredentialBackendError):
                build_credential_backend(platform="linux")


class TestBuildCredentialBackend_SecretsDir(unittest.TestCase):
    """GUARDRAILHUB_SECRETS_DIR wiring to ContainerFileCredentialBackend."""

    def test_secrets_dir_unset_uses_default(self):
        """Unset GUARDRAILHUB_SECRETS_DIR -> /run/secrets."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="file", GUARDRAILHUB_SECRETS_DIR=None):
            backend = build_credential_backend(platform="linux")
        self.assertIsInstance(backend, ContainerFileCredentialBackend)
        self.assertEqual(backend._secrets_dir, DEFAULT_SECRETS_DIR)

    def test_secrets_dir_empty_rejected(self):
        """Empty GUARDRAILHUB_SECRETS_DIR -> CredentialBackendError."""
        with _env(GUARDRAILHUB_CREDENTIAL_BACKEND="file", GUARDRAILHUB_SECRETS_DIR=""):
            with self.assertRaises(CredentialBackendError):
                build_credential_backend(platform="linux")

    def test_secrets_dir_whitespace_only_rejected(self):
        """Whitespace-only GUARDRAILHUB_SECRETS_DIR -> CredentialBackendError."""
        for value in ("  ", "\t", " \t "):
            with self.subTest(value=repr(value)):
                with _env(
                    GUARDRAILHUB_CREDENTIAL_BACKEND="file",
                    GUARDRAILHUB_SECRETS_DIR=value,
                ):
                    with self.assertRaises(CredentialBackendError):
                        build_credential_backend(platform="linux")

    def test_secrets_dir_valid_custom_path(self):
        """Valid custom path is passed through to ContainerFileCredentialBackend."""
        custom_dir = "/etc/guardrail-hub/secrets"
        with _env(
            GUARDRAILHUB_CREDENTIAL_BACKEND="file",
            GUARDRAILHUB_SECRETS_DIR=custom_dir,
        ):
            backend = build_credential_backend(platform="linux")
        self.assertIsInstance(backend, ContainerFileCredentialBackend)
        self.assertEqual(backend._secrets_dir, custom_dir)

    def test_secrets_dir_only_matters_for_file_mode(self):
        """GUARDRAILHUB_SECRETS_DIR is ignored in env mode."""
        custom_dir = "/etc/guardrail-hub/secrets"
        with _env(
            GUARDRAILHUB_CREDENTIAL_BACKEND="env",
            GUARDRAILHUB_SECRETS_DIR=custom_dir,
        ):
            backend = build_credential_backend(platform="linux")
        self.assertIsInstance(backend, EnvVarCredentialBackend)


class TestBuildProviderEnvVarNames(unittest.TestCase):
    """One pure helper owns the runtime and CLI env identity projection."""

    @staticmethod
    def _provider(provider_id, api_key_env=None, auth_type=AuthType.API_KEY):
        return ProviderRecord(
            provider_id=provider_id,
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(type=auth_type, api_key_env=api_key_env),
            connection=ConnectionConfig(base_url="https://example.test/v1"),
        )

    def test_uses_api_key_env_and_approved_fallback_for_api_key_providers(self):
        providers = [
            self._provider("openai-cloud", "OPENAI_API_KEY"),
            self._provider("fallback-cloud"),
            self._provider("ollama-local", auth_type=AuthType.NONE),
        ]

        self.assertEqual(
            build_provider_env_var_names(providers),
            {
                "openai-cloud": "OPENAI_API_KEY",
                "fallback-cloud": "GUARDRAILHUB_CREDENTIAL__FALLBACK-CLOUD",
            },
        )


# ---------------------------------------------------------------------------
# Phase 5B: legacy build_default_credential_backend() tests
# ---------------------------------------------------------------------------


class TestBuildDefaultCredentialBackend(unittest.TestCase):
    """Phase 5B legacy API — retained for backward compatibility."""

    def test_win32_returns_wcmb(self):
        """On win32, build_default_credential_backend returns WCMB."""
        backend = build_default_credential_backend(platform="win32")
        self.assertIsInstance(backend, WindowsCredentialManagerBackend)

    def test_linux_fails_closed(self):
        """On linux, build_default_credential_backend raises CredentialBackendError."""
        with self.assertRaises(CredentialBackendError) as ctx:
            build_default_credential_backend(platform="linux")
        message = str(ctx.exception)
        self.assertIn("linux", message)
        self.assertIn("Inject", message)

    def test_darwin_fails_closed(self):
        """On darwin, build_default_credential_backend raises CredentialBackendError."""
        with self.assertRaises(CredentialBackendError):
            build_default_credential_backend(platform="darwin")


if __name__ == "__main__":
    unittest.main()
