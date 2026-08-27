"""Behavioral integration tests for Phase 5D bootstrap credential wiring."""

from types import SimpleNamespace
import unittest
from unittest import mock
from unittest.mock import MagicMock

from app.bootstrap import build_conversation_service
from app.intelligence.credentials import CredentialStore, InMemoryCredentialBackend
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.providers.provider_manager import ProviderManager
from app.intelligence.registry.catalog.catalog import ModelCatalog


class TestBootstrapCredentialWiring(unittest.TestCase):
    """Verify the actual bootstrap composition root, without full app startup."""

    def test_build_conversation_service_wires_credential_runtime(self):
        """Build the real composition graph with only backend selection patched."""
        catalog = ModelCatalog()
        catalog.freeze()
        registry_runtime = SimpleNamespace(catalog=catalog)
        backend = InMemoryCredentialBackend()

        with mock.patch(
            "app.intelligence.credentials.backend_factory.build_credential_backend",
            return_value=backend,
        ) as build_backend:
            _, _, provider_manager = build_conversation_service(
                registry_runtime=registry_runtime,
                event_dispatcher=MagicMock(),
            )

        build_backend.assert_called_once_with()
        self.assertIsInstance(provider_manager, ProviderManager)
        self.assertIsInstance(provider_manager._factory, ProviderFactory)
        self.assertEqual(
            set(provider_manager._factory.registered_types),
            {"ollama", "openai_compatible", "bedrock"},
        )
        self.assertIs(provider_manager._catalog, catalog)
        self.assertIsInstance(provider_manager._credential_store, CredentialStore)
        self.assertIs(provider_manager._credential_store._backend, backend)


if __name__ == "__main__":
    unittest.main()
