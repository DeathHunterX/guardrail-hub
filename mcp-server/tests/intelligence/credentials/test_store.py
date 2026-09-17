"""Unit tests for the CredentialStore abstraction.

Covers:
- set/get round-trip
- get missing credential raises CredentialNotFoundError
- delete
- provider isolation (each provider_id is independent)
- backend failure behavior
- credential values are not exposed through repr
- CredentialStoreError is-a LLMConfigurationError
"""

import sys
import uuid
from pathlib import Path
from unittest import mock
import unittest

from app.intelligence.credentials import (
    CredentialBackend,
    CredentialBackendError,
    CredentialNotFoundError,
    CredentialStore,
    CredentialStoreError,
    InMemoryCredentialBackend,
)
from app.intelligence.exceptions.llm import LLMConfigurationError

# Sentinel used in INV-6 tests. Must be longer than any size cap that could
# truncate it in a test buffer.
TEST_SECRET_DO_NOT_LEAK = "SECRET-DO-NOT-LEAK-0123456789abcdefghij"


# ------------------------------------------------------------------
# Stub backend used to test CredentialStore forwarding and error behaviour
# without relying on the InMemory backend's own implementation.
# ------------------------------------------------------------------


class _StubFailingBackend(CredentialBackend):
    """Backend that always raises CredentialBackendError — used to test failure paths."""

    def get(self, provider_id: str) -> str:
        raise CredentialBackendError(provider_id, "stub get failed")

    def set(self, provider_id: str, credential: str) -> None:
        raise CredentialBackendError(provider_id, "stub set failed")

    def delete(self, provider_id: str) -> None:
        raise CredentialBackendError(provider_id, "stub delete failed")


# ------------------------------------------------------------------
# INV-6 regression helper
# ------------------------------------------------------------------

# Python's `finally` machinery can unbind named `as` targets after certain
# exception-handling sequences (POP_EXCEPT + END_FINALLY). Using a class
# attribute sidesteps this.
class _Capture:
    exception: BaseException | None = None


# ------------------------------------------------------------------
# CredentialStore unit tests
# ------------------------------------------------------------------

class CredentialStoreGetSetTests(unittest.TestCase):
    """Tests for set/get round-trip."""

    def setUp(self):
        self.backend = InMemoryCredentialBackend()
        self.store = CredentialStore(self.backend)

    def test_set_and_get_returns_value(self):
        self.store.set("openai-cloud", "sk-test-12345")
        result = self.store.get("openai-cloud")
        self.assertEqual(result, "sk-test-12345")

    def test_set_twice_replaces_previous_value(self):
        self.store.set("openai-cloud", "first")
        self.store.set("openai-cloud", "second")
        self.assertEqual(self.store.get("openai-cloud"), "second")

    def test_get_unknown_provider_raises_not_found(self):
        with self.assertRaises(CredentialNotFoundError) as ctx:
            self.store.get("nonexistent-provider")
        self.assertEqual(ctx.exception.provider_id, "nonexistent-provider")

    def test_get_unknown_provider_error_message_mentions_provider_id(self):
        with self.assertRaises(CredentialNotFoundError) as ctx:
            self.store.get("i-do-not-exist")
        self.assertIn("i-do-not-exist", str(ctx.exception))


class CredentialStoreDeleteTests(unittest.TestCase):
    """Tests for delete behaviour."""

    def setUp(self):
        self.backend = InMemoryCredentialBackend()
        self.store = CredentialStore(self.backend)

    def test_delete_removes_credential(self):
        self.store.set("openai-cloud", "sk-test")
        self.store.delete("openai-cloud")
        with self.assertRaises(CredentialNotFoundError):
            self.store.get("openai-cloud")

    def test_delete_nonexistent_is_idempotent(self):
        # Must not raise.
        self.store.delete("never-existed")

    def test_delete_one_provider_does_not_affect_others(self):
        self.store.set("openai-cloud", "sk-openai")
        self.store.set("ollama-local", "sk-ollama")
        self.store.delete("ollama-local")
        self.assertEqual(self.store.get("openai-cloud"), "sk-openai")
        with self.assertRaises(CredentialNotFoundError):
            self.store.get("ollama-local")


class CredentialStoreProviderIsolationTests(unittest.TestCase):
    """Tests that each provider_id is handled independently."""

    def setUp(self):
        self.backend = InMemoryCredentialBackend()
        self.store = CredentialStore(self.backend)

    def test_multiple_providers_stored_independently(self):
        providers = [
            ("openai", "sk-openai"),
            ("anthropic", "sk-ant"),
            ("ollama", "sk-local"),
        ]
        for pid, cred in providers:
            self.store.set(pid, cred)
        for pid, cred in providers:
            self.assertEqual(self.store.get(pid), cred)

    def test_provider_id_case_is_respected(self):
        self.store.set("OpenAI", "value-upper")
        self.store.set("openai", "value-lower")
        self.assertEqual(self.store.get("OpenAI"), "value-upper")
        self.assertEqual(self.store.get("openai"), "value-lower")


class CredentialStoreBackendFailureTests(unittest.TestCase):
    """Tests that CredentialStore propagates backend failures correctly."""

    def test_get_failure_propagates_credential_backend_error(self):
        store = CredentialStore(_StubFailingBackend())
        with self.assertRaises(CredentialBackendError) as ctx:
            store.get("stub-provider")
        self.assertEqual(ctx.exception.provider_id, "stub-provider")
        self.assertIn("stub get failed", str(ctx.exception))

    def test_set_failure_propagates_credential_backend_error(self):
        store = CredentialStore(_StubFailingBackend())
        with self.assertRaises(CredentialBackendError) as ctx:
            store.set("stub-provider", "any-value")
        self.assertEqual(ctx.exception.provider_id, "stub-provider")

    def test_delete_failure_propagates_credential_backend_error(self):
        store = CredentialStore(_StubFailingBackend())
        with self.assertRaises(CredentialBackendError) as ctx:
            store.delete("stub-provider")
        self.assertEqual(ctx.exception.provider_id, "stub-provider")

    def test_credential_backend_error_mentions_provider_id(self):
        store = CredentialStore(_StubFailingBackend())
        with self.assertRaises(CredentialBackendError) as ctx:
            store.get("my-provider")
        self.assertIn("my-provider", str(ctx.exception))

    def test_set_leaves_no_credential_in_store_frame(self) -> None:
        # INV-6 regression: the inbound credential is a local of
        # CredentialStore.set's frame. After this method exits, the frame's
        # locals stay reachable through exc.__traceback__, so any error reporter
        # that walks frames can recover the plaintext unless the name is deleted.
        #
        # `assertRaises` cannot be used here -- it calls
        # traceback.clear_frames() and stores exc.with_traceback(None), which
        # makes frame-locals assertions vacuous.
        _Capture.exception = None
        store = CredentialStore(_StubFailingBackend())
        try:
            store.set("stub-provider", TEST_SECRET_DO_NOT_LEAK)
        except BaseException:
            _Capture.exception = sys.exc_info()[1]

        exc = _Capture.exception
        self.assertIsNotNone(exc)
        self.assertIsInstance(exc, CredentialBackendError)
        self.assertIsNotNone(exc.__traceback__)

        # Walk the traceback and assert the store frame has no 'credential' local.
        tb = exc.__traceback__
        found = False
        while tb is not None:
            frame = tb.tb_frame
            if Path(frame.f_code.co_filename).parts[-4:] == (
                "app",
                "intelligence",
                "credentials",
                "base.py",
            ):
                found = True
                self.assertNotIn(
                    "credential",
                    frame.f_locals,
                    msg=(
                        "CredentialStore.set still holds 'credential' in its "
                        "frame locals. Verify the finally: del credential "
                        "change was applied to base.py."
                    ),
                )
                self.assertNotIn(
                    TEST_SECRET_DO_NOT_LEAK,
                    str(frame.f_locals),
                )
                break
            tb = tb.tb_next

        self.assertTrue(found, "CredentialStore.set frame not found in traceback")


class CredentialStoreReprSecurityTests(unittest.TestCase):
    """Tests that credential values are never exposed in diagnostics."""

    def setUp(self):
        self.backend = InMemoryCredentialBackend()
        self.store = CredentialStore(self.backend)

    def test_store_repr_contains_no_credential_values(self):
        self.store.set("openai-cloud", "sk-super-secret-key-12345")
        self.store.set("bedrock", "AKIAIOSFODNN7EXAMPLE")
        repr_str = repr(self.store)
        self.assertNotIn("sk-super-secret", repr_str)
        self.assertNotIn("AKIAIOSFODNN7", repr_str)
        self.assertNotIn("12345", repr_str)

    def test_store_repr_contains_backend_name(self):
        self.store.set("openai-cloud", "any-value")
        repr_str = repr(self.store)
        self.assertIn("CredentialStore", repr_str)
        self.assertIn("InMemory", repr_str)

    def test_inmemory_backend_repr_contains_no_values(self):
        self.backend.set("openai-cloud", "sk-another-secret")
        repr_str = repr(self.backend)
        self.assertNotIn("sk-another", repr_str)
        self.assertIn("openai-cloud", repr_str)


class CredentialStoreExceptionHierarchyTests(unittest.TestCase):
    """Tests that exceptions satisfy the required type hierarchy."""

    def test_credential_store_error_is_llm_configuration_error(self):
        self.assertTrue(issubclass(CredentialStoreError, LLMConfigurationError))

    def test_credential_not_found_error_is_credential_store_error(self):
        self.assertTrue(issubclass(CredentialNotFoundError, CredentialStoreError))

    def test_credential_backend_error_is_credential_store_error(self):
        self.assertTrue(issubclass(CredentialBackendError, CredentialStoreError))

    def test_all_three_are_distinct(self):
        self.assertIsNot(CredentialStoreError, CredentialNotFoundError)
        self.assertIsNot(CredentialStoreError, CredentialBackendError)
        self.assertIsNot(CredentialNotFoundError, CredentialBackendError)


# ------------------------------------------------------------------
# In-memory backend direct tests
# ------------------------------------------------------------------

class InMemoryBackendDirectTests(unittest.TestCase):
    """Tests for InMemoryCredentialBackend as a standalone component."""

    def setUp(self):
        self.backend = InMemoryCredentialBackend()

    def test_empty_backend_raises_on_get(self):
        with self.assertRaises(CredentialNotFoundError):
            self.backend.get("any-provider")

    def test_set_and_get(self):
        self.backend.set("test", "credential-value")
        self.assertEqual(self.backend.get("test"), "credential-value")

    def test_delete_clears_value(self):
        self.backend.set("test", "value")
        self.backend.delete("test")
        with self.assertRaises(CredentialNotFoundError):
            self.backend.get("test")

    def test_delete_missing_is_safe(self):
        # Must not raise.
        self.backend.delete("never-existed")

    def test_backend_repr_shows_provider_ids(self):
        self.backend.set("a", "x")
        self.backend.set("b", "y")
        repr_str = repr(self.backend)
        self.assertIn("a", repr_str)
        self.assertIn("b", repr_str)
        # Verify credential values are never exposed (check for the exact stored strings).
        self.assertNotIn("'x'", repr_str)
        self.assertNotIn("'y'", repr_str)


# ------------------------------------------------------------------
# Platform gate: skip tests that require Windows-specific backends
# ------------------------------------------------------------------

class WindowsBackendAvailabilityTests(unittest.TestCase):
    """Tests for Windows Credential Manager backend availability."""

    @unittest.skipIf(
        sys.platform != "win32",
        "Windows Credential Manager backend is Windows-only",
    )
    def test_windows_backend_can_be_instantiated(self):
        from app.intelligence.credentials.windows_backend import (
            WindowsCredentialManagerBackend,
        )
        backend = WindowsCredentialManagerBackend()
        self.assertIsInstance(backend, CredentialBackend)

    @unittest.skipIf(
        sys.platform != "win32",
        "Windows Credential Manager backend is Windows-only",
    )
    def test_nonexistent_windows_credential_is_missing_not_backend_failure(self):
        """A native ERROR_NOT_FOUND must reach setup as a normal missing state."""
        from app.intelligence.credentials.windows_backend import (
            WindowsCredentialManagerBackend,
        )
        backend = WindowsCredentialManagerBackend()
        with self.assertRaises(CredentialNotFoundError):
            backend.get(f"audit-missing-{uuid.uuid4().hex}")

    @unittest.skipIf(
        sys.platform != "win32",
        "Windows Credential Manager backend is Windows-only",
    )
    def test_unexpected_windows_read_error_remains_backend_failure(self):
        """Only ERROR_NOT_FOUND may be translated into CredentialNotFoundError."""
        from app.intelligence.credentials.windows_backend import (
            WindowsCredentialManagerBackend,
        )

        class FailingAdvapi32:
            @staticmethod
            def CredReadW(*_args):
                return 0

        backend = WindowsCredentialManagerBackend()
        with (
            mock.patch(
                "app.intelligence.credentials.windows_backend._get_advapi32",
                return_value=FailingAdvapi32(),
            ),
            mock.patch.object(backend, "_get_last_error", return_value=5),
            self.assertRaises(CredentialBackendError),
        ):
            backend.get("audit-real-read-error")

    @unittest.skipIf(
        sys.platform == "win32",
        "Windows Credential Manager backend is Windows-only",
    )
    def test_windows_backend_raises_on_non_windows(self):
        from app.intelligence.credentials.windows_backend import (
            WindowsCredentialManagerBackend,
        )
        backend = WindowsCredentialManagerBackend()
        with self.assertRaises(CredentialBackendError):
            backend.get("any-provider")


if __name__ == "__main__":
    unittest.main()
