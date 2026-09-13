"""Unit tests for EnvVarCredentialBackend.

The backend receives provider identities and projects them to pre-composed,
non-secret environment-variable names.
"""

import os
import unittest

from app.intelligence.credentials import (
    CredentialBackendError,
    CredentialNotFoundError,
)
from app.intelligence.credentials.env_backend import EnvVarCredentialBackend


# Sentinel: a deliberately long secret used only in INV-6 tests.
_TEST_SECRET = "SECRET-DO-NOT-LEAK-0123456789abcdefghijklmnopqrstuvwxyz"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _env(**vars):
    """Context manager: temporarily set/unset environment variables."""
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
# get() tests
# ---------------------------------------------------------------------------


class TestEnvBackendGet(unittest.TestCase):
    """Successful and unsuccessful credential retrieval."""

    def test_get_projects_provider_id_to_configured_env_name(self):
        """A provider ID resolves only through its configured env-name mapping."""
        with _env(OPENAI_API_KEY=_TEST_SECRET):
            backend = EnvVarCredentialBackend({"openai-cloud": "OPENAI_API_KEY"})
            result = backend.get("openai-cloud")
        self.assertEqual(result, _TEST_SECRET)

    def test_get_missing_raises_not_found(self):
        """get() for a non-existent variable raises CredentialNotFoundError."""
        # Ensure it does not exist.
        with _env(NON_EXISTENT_VAR_987654321=None):
            backend = EnvVarCredentialBackend(
                {"missing-provider": "NON_EXISTENT_VAR_987654321"}
            )
            with self.assertRaises(CredentialNotFoundError) as ctx:
                backend.get("missing-provider")
            self.assertEqual(ctx.exception.provider_id, "missing-provider")
            self.assertNotIn(_TEST_SECRET, str(ctx.exception))

    def test_get_empty_string_raises_not_found(self):
        """get() for a variable set to empty string raises CredentialNotFoundError.

        An empty string is a misconfiguration — the variable is defined but has
        no value. It is not a valid credential.
        """
        with _env(EMPTY_SECRET_VAR=""):
            backend = EnvVarCredentialBackend(
                {"empty-provider": "EMPTY_SECRET_VAR"}
            )
            with self.assertRaises(CredentialNotFoundError) as ctx:
                backend.get("empty-provider")
            self.assertEqual(ctx.exception.provider_id, "empty-provider")

    def test_unmapped_provider_is_not_treated_as_raw_environment_name(self):
        """An unmapped provider must fail even if its raw name exists in env."""
        with _env(**{"openai-cloud": _TEST_SECRET}):
            backend = EnvVarCredentialBackend({})
            with self.assertRaises(CredentialNotFoundError) as ctx:
                backend.get("openai-cloud")
        self.assertEqual(ctx.exception.provider_id, "openai-cloud")
        self.assertNotIn(_TEST_SECRET, str(ctx.exception))
        self.assertNotIn(_TEST_SECRET, repr(ctx.exception))

    def test_get_whitespace_value_preserved(self):
        """A variable containing only whitespace (not empty) is returned as-is."""
        with _env(WHITESPACE_SECRET="   \t\n   "):
            backend = EnvVarCredentialBackend(
                {"whitespace-provider": "WHITESPACE_SECRET"}
            )
            result = backend.get("whitespace-provider")
        self.assertEqual(result, "   \t\n   ")


# ---------------------------------------------------------------------------
# INV-6: secret non-disclosure tests
# ---------------------------------------------------------------------------


class TestEnvBackendInv6(unittest.TestCase):
    """INV-6: the secret value must not appear in any diagnostic surface."""

    def test_secret_not_in_exception_message(self):
        """CredentialNotFoundError message does not contain the secret."""
        with _env(INV6_SECRET=_TEST_SECRET):
            backend = EnvVarCredentialBackend({"inv6-provider": "INV6_SECRET"})
            with self.assertRaises(CredentialNotFoundError) as ctx:
                backend.get("unmapped-provider")
        self.assertNotIn(_TEST_SECRET, str(ctx.exception))
        self.assertNotIn(_TEST_SECRET, repr(ctx.exception))

    def test_secret_not_in_repr(self):
        """backend repr contains no secret values or variable names."""
        with _env(SECRET_FOR_REPR="my-secret-value"):
            backend = EnvVarCredentialBackend({"repr-provider": "SECRET_FOR_REPR"})
            r = repr(backend)
            self.assertNotIn("my-secret-value", r)
            self.assertNotIn("SECRET_FOR_REPR", r)
            # The repr must still be informative.
            self.assertIn("EnvVarCredentialBackend", r)


# ---------------------------------------------------------------------------
# set() tests (INV-3: read-only)
# ---------------------------------------------------------------------------


class TestEnvBackendSet(unittest.TestCase):
    """set() is refused because the backend is read-only."""

    def test_set_raises_backend_error(self):
        """set() always raises CredentialBackendError."""
        backend = EnvVarCredentialBackend({})
        with self.assertRaises(CredentialBackendError) as ctx:
            backend.set("SOME_VAR", "any-value")
        self.assertEqual(ctx.exception.provider_id, "SOME_VAR")
        self.assertIn("read-only", str(ctx.exception).lower())

    def test_set_error_message_no_secret(self):
        """CredentialBackendError message does not contain the secret value."""
        backend = EnvVarCredentialBackend({})
        with self.assertRaises(CredentialBackendError) as ctx:
            backend.set("ANOTHER_VAR", _TEST_SECRET)
        self.assertNotIn(_TEST_SECRET, str(ctx.exception))


# ---------------------------------------------------------------------------
# delete() tests (INV-3: read-only)
# ---------------------------------------------------------------------------


class TestEnvBackendDelete(unittest.TestCase):
    """delete() is refused because the backend is read-only."""

    def test_delete_raises_backend_error(self):
        """delete() always raises CredentialBackendError."""
        backend = EnvVarCredentialBackend({})
        with self.assertRaises(CredentialBackendError) as ctx:
            backend.delete("SOME_VAR")
        self.assertEqual(ctx.exception.provider_id, "SOME_VAR")
        self.assertIn("read-only", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# __repr__ tests
# ---------------------------------------------------------------------------


class TestEnvBackendRepr(unittest.TestCase):
    """__repr__ shows only the backend type; no secrets, no variable names."""

    def test_repr_no_secret_no_var_name(self):
        """repr() contains neither the secret value nor the variable name."""
        with _env(SOME_VAR_FOR_REPR="super-secret-value-xyz"):
            backend = EnvVarCredentialBackend({"repr-provider": "SOME_VAR_FOR_REPR"})
            r = repr(backend)
            self.assertIn("EnvVarCredentialBackend", r)
            self.assertNotIn("super-secret-value-xyz", r)
            self.assertNotIn("SOME_VAR_FOR_REPR", r)

    def test_repr_identical_every_time(self):
        """repr() is deterministic (stateless backend)."""
        backend = EnvVarCredentialBackend({})
        self.assertEqual(repr(backend), repr(backend))


if __name__ == "__main__":
    unittest.main()
