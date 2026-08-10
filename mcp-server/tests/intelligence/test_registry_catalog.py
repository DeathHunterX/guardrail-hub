"""Unit tests for the Registry Context — catalog, loaders, and validators."""

import unittest

from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.loaders.model_loader import ModelLoader
from app.intelligence.registry.loaders.provider_loader import ProviderLoader
from app.intelligence.registry.loaders.registry_loader import RegistryLoader
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import AuthConfig, ConnectionConfig, ProviderRecord
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.model import ModelType
from app.intelligence.registry.types.provider import ProviderType
from app.intelligence.registry.validators import (
    RegistryValidationError,
    RegistryValidator,
)


class ModelCatalogTests(unittest.TestCase):
    """Tests for the in-memory ModelCatalog."""

    def setUp(self):
        self.catalog = ModelCatalog()

    def test_register_and_get_provider(self):
        provider = ProviderRecord(
            provider_id="test-provider",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(api_key_env="TEST_API_KEY"),
            connection=ConnectionConfig(base_url="https://api.test.com"),
        )
        self.catalog.register_provider(provider)

        result = self.catalog.get_provider("test-provider")
        self.assertIsNotNone(result)
        self.assertEqual(result.provider_id, "test-provider")

    def test_register_and_get_model(self):
        model = ModelRecord(
            model_id="test-model",
            provider_id="test-provider",
            model_type=ModelType.CHAT,
        )
        self.catalog.register_model(model)

        result = self.catalog.get_model("test-model")
        self.assertIsNotNone(result)
        self.assertEqual(result.model_id, "test-model")

    def test_list_providers_enabled_only(self):
        provider1 = ProviderRecord(
            provider_id="enabled-provider",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="https://api.test.com"),
            enabled=True,
        )
        provider2 = ProviderRecord(
            provider_id="disabled-provider",
            provider_type=ProviderType.ANTHROPIC,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="https://api.anthropic.com"),
            enabled=False,
        )
        self.catalog.register_provider(provider1)
        self.catalog.register_provider(provider2)

        enabled = self.catalog.list_providers(enabled_only=True)
        enabled_ids = {p.provider_id for p in enabled}
        self.assertIn("enabled-provider", enabled_ids)
        self.assertNotIn("disabled-provider", enabled_ids)

    def test_find_models_by_capability(self):
        from app.intelligence.registry.models.provider import (
            AuthConfig,
            ConnectionConfig,
            ProviderRecord,
        )
        from app.intelligence.registry.types.deployment import DeploymentType
        from app.intelligence.registry.types.provider import ProviderType

        # Phase 2 catalog: enable_providers_only filter requires providers
        # to be registered first.
        self.catalog.register_provider(
            ProviderRecord(
                provider_id="test-provider",
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                deployment=DeploymentType.CLOUD,
                auth=AuthConfig(),
                connection=ConnectionConfig(base_url="https://api.test.com"),
            )
        )
        model1 = ModelRecord(
            model_id="chat-model",
            provider_id="test-provider",
            model_type=ModelType.CHAT,
            capabilities=frozenset({Capability.CHAT}),
        )
        model2 = ModelRecord(
            model_id="embedding-model",
            provider_id="test-provider",
            model_type=ModelType.EMBEDDING,
            capabilities=frozenset({Capability.EMBEDDING}),
        )
        self.catalog.register_model(model1)
        self.catalog.register_model(model2)

        chat_models = self.catalog.find_models_by_capability(Capability.CHAT)
        self.assertEqual(len(chat_models), 1)
        self.assertEqual(chat_models[0].model_id, "chat-model")

    def test_clear_catalog(self):
        provider = ProviderRecord(
            provider_id="test-provider",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="https://api.test.com"),
        )
        self.catalog.register_provider(provider)

        self.catalog.clear()
        self.assertTrue(self.catalog.is_empty)
        self.assertIsNone(self.catalog.get_provider("test-provider"))


class ProviderLoaderTests(unittest.TestCase):
    """Tests for the ProviderLoader."""

    def setUp(self):
        self.loader = ProviderLoader()

    def test_load_valid_provider(self):
        data = {
            "providers": [
                {
                    "provider_id": "test-provider",
                    "provider_type": "openai_compatible",
                    "deployment": "cloud",
                    "connection": {
                        "base_url": "https://api.test.com",
                        "timeout_seconds": 30.0,
                    },
                    "auth": {
                        "api_key_env": "TEST_API_KEY",
                    },
                }
            ]
        }

        result = self.loader.load_from_dict(data)
        self.assertEqual(len(result.providers), 1)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.providers[0].provider_id, "test-provider")

    def test_load_missing_provider_id(self):
        data = {
            "providers": [
                {
                    "provider_type": "openai_compatible",
                    "connection": {"base_url": "https://api.test.com"},
                }
            ]
        }

        result = self.loader.load_from_dict(data)
        self.assertEqual(len(result.providers), 0)
        self.assertEqual(len(result.errors), 1)

    def test_load_invalid_provider_type(self):
        data = {
            "providers": [
                {
                    "provider_id": "test",
                    "provider_type": "invalid_type",
                    "connection": {"base_url": "https://api.test.com"},
                }
            ]
        }

        result = self.loader.load_from_dict(data)
        self.assertEqual(len(result.providers), 0)
        self.assertEqual(len(result.errors), 1)

    def test_load_provider_with_capabilities(self):
        data = {
            "providers": [
                {
                    "provider_id": "multimodal-provider",
                    "provider_type": "openai_compatible",
                    "deployment": "cloud",
                    "connection": {"base_url": "https://api.test.com"},
                    "capabilities": ["chat", "vision"],
                }
            ]
        }

        result = self.loader.load_from_dict(data)
        self.assertEqual(len(result.providers), 1)
        provider = result.providers[0]
        self.assertIn(Capability.CHAT, provider.capabilities)
        self.assertIn(Capability.VISION, provider.capabilities)


class ModelLoaderTests(unittest.TestCase):
    """Tests for the ModelLoader."""

    def setUp(self):
        self.loader = ModelLoader()

    def test_load_valid_model(self):
        data = {
            "models": [
                {
                    "model_id": "gpt-4",
                    "provider_id": "openai",
                    "model_type": "chat",
                    "context_window": 128000,
                    "capabilities": ["chat"],
                }
            ]
        }

        result = self.loader.load_from_dict(data)
        self.assertEqual(len(result.models), 1)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.models[0].model_id, "gpt-4")

    def test_load_missing_model_id(self):
        data = {
            "models": [
                {
                    "provider_id": "openai",
                    "model_type": "chat",
                }
            ]
        }

        result = self.loader.load_from_dict(data)
        self.assertEqual(len(result.models), 0)
        self.assertEqual(len(result.errors), 1)

    def test_load_capabilities_as_list(self):
        data = {
            "models": [
                {
                    "model_id": "multimodal-model",
                    "provider_id": "openai",
                    "model_type": "multimodal",
                    "capabilities": ["chat", "vision"],
                }
            ]
        }

        result = self.loader.load_from_dict(data)
        self.assertEqual(len(result.models), 1)
        model = result.models[0]
        self.assertIn(Capability.CHAT, model.capabilities)
        self.assertIn(Capability.VISION, model.capabilities)

    def test_load_capabilities_as_string(self):
        data = {
            "models": [
                {
                    "model_id": "single-cap-model",
                    "provider_id": "openai",
                    "model_type": "embedding",
                    "capabilities": "embedding",
                }
            ]
        }

        result = self.loader.load_from_dict(data)
        self.assertEqual(len(result.models), 1)
        model = result.models[0]
        self.assertIn(Capability.EMBEDDING, model.capabilities)


class RegistryLoaderTests(unittest.TestCase):
    """Tests for the coordinating RegistryLoader."""

    def setUp(self):
        self.loader = RegistryLoader()

    def test_load_combined_registry(self):
        data = {
            "providers": [
                {
                    "provider_id": "test-provider",
                    "provider_type": "openai_compatible",
                    "deployment": "cloud",
                    "connection": {"base_url": "https://api.test.com"},
                }
            ],
            "models": [
                {
                    "model_id": "test-model",
                    "provider_id": "test-provider",
                    "model_type": "chat",
                    "capabilities": ["chat"],
                }
            ],
        }

        result = self.loader.load_combined(data)
        self.assertEqual(len(result.providers), 1)
        self.assertEqual(len(result.models), 1)
        self.assertEqual(len(result.errors), 0)

    def test_warns_on_unknown_provider_reference(self):
        data = {
            "providers": [
                {
                    "provider_id": "known-provider",
                    "provider_type": "openai_compatible",
                    "deployment": "cloud",
                    "connection": {"base_url": "https://api.test.com"},
                    "capabilities": ["chat"],
                }
            ],
            "models": [
                {
                    "model_id": "orphan-model",
                    "provider_id": "unknown-provider",
                    "model_type": "chat",
                    "capabilities": ["chat"],
                }
            ],
        }

        result = self.loader.load_combined(data)
        # Phase 2: unknown provider reference is a validation ERROR, not a
        # warning. The error message must mention the missing provider.
        self.assertTrue(
            any("unknown-provider" in e for e in result.errors),
            f"Expected 'unknown-provider' in errors, got: {result.errors}",
        )


class RegistryValidatorTests(unittest.TestCase):
    """Tests for the RegistryValidator."""

    def setUp(self):
        self.validator = RegistryValidator()

    def test_validate_valid_records(self):
        providers = [
            ProviderRecord(
                provider_id="test-provider",
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                deployment=DeploymentType.CLOUD,
                auth=AuthConfig(),
                connection=ConnectionConfig(base_url="https://api.test.com"),
                capabilities=frozenset({Capability.CHAT}),
            )
        ]
        models = [
            ModelRecord(
                model_id="test-model",
                provider_id="test-provider",
                model_type=ModelType.CHAT,
                capabilities=frozenset({Capability.CHAT}),
            )
        ]

        result = self.validator.validate(providers, models)
        self.assertTrue(result.valid)
        self.assertEqual(result.error_count, 0)

    def test_validate_duplicate_provider_id(self):
        providers = [
            ProviderRecord(
                provider_id="duplicate",
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                deployment=DeploymentType.CLOUD,
                auth=AuthConfig(),
                connection=ConnectionConfig(base_url="https://api.test1.com"),
            ),
            ProviderRecord(
                provider_id="duplicate",
                provider_type=ProviderType.ANTHROPIC,
                deployment=DeploymentType.CLOUD,
                auth=AuthConfig(),
                connection=ConnectionConfig(base_url="https://api.test2.com"),
            ),
        ]

        result = self.validator.validate(providers, [])
        self.assertFalse(result.valid)
        self.assertGreater(result.error_count, 0)

    def test_validate_invalid_priority(self):
        providers = [
            ProviderRecord(
                provider_id="test-provider",
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                deployment=DeploymentType.CLOUD,
                auth=AuthConfig(),
                connection=ConnectionConfig(base_url="https://api.test.com"),
                priority=-1,
            ),
        ]

        result = self.validator.validate(providers, [])
        self.assertFalse(result.valid)
        self.assertGreater(result.error_count, 0)

    def test_validate_invalid_context_window(self):
        models = [
            ModelRecord(
                model_id="test-model",
                provider_id="test-provider",
                model_type=ModelType.CHAT,
                context_window=0,
                capabilities=frozenset({Capability.CHAT}),
            ),
        ]

        result = self.validator.validate([], models)
        self.assertFalse(result.valid)
        self.assertGreater(result.error_count, 0)

    def test_validate_model_without_capabilities(self):
        models = [
            ModelRecord(
                model_id="test-model",
                provider_id="test-provider",
                model_type=ModelType.CHAT,
                capabilities=frozenset(),
            ),
        ]

        result = self.validator.validate([], models)
        self.assertFalse(result.valid)
        self.assertGreater(result.error_count, 0)

    def test_validate_unknown_provider_reference(self):
        providers = [
            ProviderRecord(
                provider_id="test-provider",
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                deployment=DeploymentType.CLOUD,
                auth=AuthConfig(),
                connection=ConnectionConfig(base_url="https://api.test.com"),
            ),
        ]
        models = [
            ModelRecord(
                model_id="orphan-model",
                provider_id="unknown-provider",
                model_type=ModelType.CHAT,
                capabilities=frozenset({Capability.CHAT}),
            ),
        ]

        result = self.validator.validate(providers, models)
        self.assertFalse(result.valid)
        errors = list(result.errors)
        unknown_ref_errors = [
            e for e in errors
            if "unknown provider" in e.message.lower()
        ]
        self.assertGreater(len(unknown_ref_errors), 0)

    def test_warns_on_provider_without_capabilities(self):
        providers = [
            ProviderRecord(
                provider_id="no-caps-provider",
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                deployment=DeploymentType.CLOUD,
                auth=AuthConfig(),
                connection=ConnectionConfig(base_url="https://api.test.com"),
                capabilities=frozenset(),
            ),
        ]

        result = self.validator.validate(providers, [])
        self.assertTrue(result.valid)  # Still valid, just warning
        self.assertGreater(result.warning_count, 0)


if __name__ == "__main__":
    unittest.main()
