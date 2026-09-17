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
from app.intelligence.registry.models.provider import (
    AuthConfig,
    AuthType,
    Capability,
    ConnectionConfig,
    DeploymentType,
    ProviderRecord,
    ProviderType,
)


class TestBootstrapCredentialWiring(unittest.TestCase):
    """Verify the actual bootstrap composition root, without full app startup."""

    def test_build_conversation_service_wires_credential_runtime(self):
        """Build the real composition graph with only backend selection patched."""
        catalog = ModelCatalog()
        catalog.register_provider(
            ProviderRecord(
                provider_id="openai-cloud",
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                deployment=DeploymentType.CLOUD,
                auth=AuthConfig(type=AuthType.API_KEY, api_key_env="OPENAI_API_KEY"),
                connection=ConnectionConfig(base_url="https://example.com/v1"),
                capabilities=frozenset({Capability.CHAT}),
                enabled=True,
                priority=10,
            )
        )
        catalog.register_provider(
            ProviderRecord(
                provider_id="fallback-cloud",
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                deployment=DeploymentType.CLOUD,
                auth=AuthConfig(type=AuthType.API_KEY),
                connection=ConnectionConfig(base_url="https://example.com/v1"),
                capabilities=frozenset({Capability.CHAT}),
                enabled=True,
                priority=20,
            )
        )
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

        build_backend.assert_called_once_with(
            env_var_names={
                "openai-cloud": "OPENAI_API_KEY",
                "fallback-cloud": "GUARDRAILHUB_CREDENTIAL__FALLBACK-CLOUD",
            }
        )
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
