"""Unit tests for the default credential backend factory.

The factory selects a persistent secure backend by platform and fails closed
where none exists (no plaintext fallback without a ratified decision).
"""

import unittest

from app.intelligence.credentials import CredentialBackendError
from app.intelligence.credentials.backend_factory import (
    build_default_credential_backend,
)
from app.intelligence.credentials.windows_backend import (
    WindowsCredentialManagerBackend,
)


class BackendFactoryTests(unittest.TestCase):
    def test_win32_returns_windows_credential_manager(self):
        backend = build_default_credential_backend(platform="win32")
        self.assertIsInstance(backend, WindowsCredentialManagerBackend)

    def test_non_windows_fails_closed(self):
        with self.assertRaises(CredentialBackendError) as ctx:
            build_default_credential_backend(platform="linux")
        message = str(ctx.exception)
        # The error names the platform and points at the resolution.
        self.assertIn("linux", message)
        self.assertIn("Inject", message)

    def test_darwin_fails_closed(self):
        with self.assertRaises(CredentialBackendError):
            build_default_credential_backend(platform="darwin")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
