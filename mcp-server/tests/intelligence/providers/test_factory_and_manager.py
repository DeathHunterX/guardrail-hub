"""Unit tests for the Provider lifecycle — factory and manager."""

import unittest

from app.intelligence.exceptions import LLMConfigurationError
from app.intelligence.ports.base import BaseProvider
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.providers.provider_manager import ProviderManager
from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.models.provider import AuthConfig, ConnectionConfig, ProviderRecord
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


class MockProvider(BaseProvider):
    """Mock provider implementing the full BaseProviderRuntime lifecycle for testing."""

    def __init__(self, record: ProviderRecord) -> None:
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_started", False)

    @property
    def provider_id(self) -> str:
        return self._record.provider_id

    @property
    def provider_type(self) -> str:
        return self._record.provider_type.value

    @property
    def capabilities(self) -> frozenset[Capability]:
        return self._record.capabilities

    def initialize(self) -> None:
        pass

    def validate_configuration(self) -> None:
        pass

    async def start(self) -> None:
        object.__setattr__(self, "_started", True)

    async def close(self) -> None:
        object.__setattr__(self, "_started", False)

    @property
    def is_started(self) -> bool:
        return self._started


class ProviderFactoryTests(unittest.TestCase):
    """Tests for the ProviderFactory."""

    def test_register_and_create(self):
        factory = ProviderFactory()
        factory.register(
            ProviderType.OPENAI_COMPATIBLE.value,
            MockProvider,
        )

        record = ProviderRecord(
            provider_id="test-provider",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="https://api.test.com"),
        )

        provider = factory.create(record)
        self.assertIsInstance(provider, MockProvider)
        self.assertEqual(provider.provider_id, "test-provider")

    def test_create_unregistered_type_raises(self):
        factory = ProviderFactory()

        record = ProviderRecord(
            provider_id="test-provider",
            provider_type=ProviderType.ANTHROPIC,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="https://api.anthropic.com"),
        )

        with self.assertRaises(LLMConfigurationError):
            factory.create(record)

    def test_is_registered(self):
        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, MockProvider)

        self.assertTrue(factory.is_registered(ProviderType.OPENAI_COMPATIBLE.value))
        self.assertFalse(factory.is_registered(ProviderType.ANTHROPIC.value))

    def test_registered_types(self):
        factory = ProviderFactory()
        factory.register("type1", MockProvider)
        factory.register("type2", MockProvider)

        self.assertEqual(len(factory.registered_types), 2)

    def test_register_capabilities(self):
        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, MockProvider)
        factory.register_capabilities(
            ProviderType.OPENAI_COMPATIBLE.value,
            {Capability.CHAT, Capability.EMBEDDING},
        )

        caps = factory.get_capabilities(ProviderType.OPENAI_COMPATIBLE.value)
        self.assertIn(Capability.CHAT, caps)
        self.assertIn(Capability.EMBEDDING, caps)

    def test_register_capabilities_unregistered_raises(self):
        factory = ProviderFactory()

        with self.assertRaises(LLMConfigurationError):
            factory.register_capabilities(
                ProviderType.OPENAI_COMPATIBLE.value,
                {Capability.CHAT},
            )

    def test_find_by_capability(self):
        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, MockProvider)
        factory.register_capabilities(
            ProviderType.OPENAI_COMPATIBLE.value,
            {Capability.CHAT, Capability.EMBEDDING},
        )
        factory.register(ProviderType.ANTHROPIC.value, MockProvider)
        factory.register_capabilities(
            ProviderType.ANTHROPIC.value,
            {Capability.CHAT},
        )

        chat_providers = factory.find_by_capability(Capability.CHAT)
        self.assertEqual(len(chat_providers), 2)
        self.assertIn(ProviderType.OPENAI_COMPATIBLE.value, chat_providers)
        self.assertIn(ProviderType.ANTHROPIC.value, chat_providers)

        embedding_providers = factory.find_by_capability(Capability.EMBEDDING)
        self.assertEqual(len(embedding_providers), 1)
        self.assertIn(ProviderType.OPENAI_COMPATIBLE.value, embedding_providers)

    def test_unregister(self):
        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, MockProvider)

        self.assertTrue(factory.is_registered(ProviderType.OPENAI_COMPATIBLE.value))
        result = factory.unregister(ProviderType.OPENAI_COMPATIBLE.value)
        self.assertTrue(result)
        self.assertFalse(factory.is_registered(ProviderType.OPENAI_COMPATIBLE.value))

    def test_unregister_not_registered(self):
        factory = ProviderFactory()
        result = factory.unregister(ProviderType.OPENAI_COMPATIBLE.value)
        self.assertFalse(result)

    def test_iter_registrations(self):
        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, MockProvider)
        factory.register_capabilities(
            ProviderType.OPENAI_COMPATIBLE.value,
            {Capability.CHAT},
        )
        factory.register(ProviderType.ANTHROPIC.value, MockProvider)
        factory.register_capabilities(
            ProviderType.ANTHROPIC.value,
            {Capability.CHAT, Capability.VISION},
        )

        all_regs = list(factory.iter_registrations())
        self.assertEqual(len(all_regs), 2)

        chat_only = list(
            factory.iter_registrations(has_capabilities=frozenset({Capability.CHAT}))
        )
        self.assertEqual(len(chat_only), 2)  # Both have CHAT

        vision_only = list(
            factory.iter_registrations(has_capabilities=frozenset({Capability.VISION}))
        )
        self.assertEqual(len(vision_only), 1)


class ProviderManagerTests(unittest.TestCase):
    """Tests for the ProviderManager — catalog-driven lifecycle.

    Phase 3 contract: the frozen ModelCatalog is the single source of
    truth. ProviderManager requires a catalog at construction; there is
    no manual add_provider() path.
    """

    def test_requires_catalog(self):
        """ProviderManager raises if constructed without a catalog."""
        factory = ProviderFactory()
        with self.assertRaises(LLMConfigurationError):
            ProviderManager(factory, catalog=None)  # type: ignore[arg-type]

    def test_get_provider_returns_none_for_unknown_id(self):
        """get_provider returns None for an ID that was never started."""
        factory = ProviderFactory()
        catalog = ModelCatalog()
        catalog.freeze()
        manager = ProviderManager(factory, catalog=catalog)
        self.assertIsNone(manager.get_provider("does-not-exist"))

    def test_get_provider_or_raise_raises_for_unknown_id(self):
        """get_provider_or_raise raises LLMProviderError for unknown IDs."""
        factory = ProviderFactory()
        catalog = ModelCatalog()
        catalog.freeze()
        manager = ProviderManager(factory, catalog=catalog)
        from app.intelligence.exceptions import LLMProviderError
        with self.assertRaises(LLMProviderError):
            manager.get_provider_or_raise("does-not-exist")

    def test_start_requires_frozen_catalog(self):
        """start() raises if the catalog is not frozen."""
        import asyncio
        factory = ProviderFactory()
        catalog = ModelCatalog()
        # intentionally not frozen
        manager = ProviderManager(factory, catalog=catalog)
        with self.assertRaises(LLMConfigurationError):
            asyncio.run(manager.start())

    def test_provider_count_after_start(self):
        """provider_count tracks initialized instances from the catalog."""
        import asyncio
        from app.intelligence.registry.catalog.catalog import ModelCatalog

        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, MockProvider)

        record = ProviderRecord(
            provider_id="test-provider",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="https://api.test.com"),
            capabilities=frozenset({Capability.CHAT}),
        )

        catalog = ModelCatalog()
        catalog.register_provider(record)
        catalog.freeze()

        manager = ProviderManager(factory, catalog=catalog)

        asyncio.run(manager.start())

        self.assertEqual(manager.provider_count, 1)
        self.assertEqual(manager.list_providers(), ["test-provider"])

    def test_lifespan_context_manager(self):
        """lifespan() calls start(), yields self, then calls stop()."""
        import asyncio
        from app.intelligence.registry.catalog.catalog import ModelCatalog

        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, MockProvider)

        record = ProviderRecord(
            provider_id="test-provider",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="https://api.test.com"),
            capabilities=frozenset({Capability.CHAT}),
        )

        catalog = ModelCatalog()
        catalog.register_provider(record)
        catalog.freeze()

        manager = ProviderManager(factory, catalog=catalog)

        async def check_lifespan():
            async with manager.lifespan() as m:
                self.assertTrue(m.initialized)
                self.assertEqual(m.provider_count, 1)
                return True

        result = asyncio.run(check_lifespan())
        self.assertTrue(result)
        self.assertFalse(manager.initialized)

    def test_stop_clears_provider_pool(self):
        """stop() removes all providers from the manager."""
        import asyncio
        from app.intelligence.registry.catalog.catalog import ModelCatalog

        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, MockProvider)

        record = ProviderRecord(
            provider_id="p1",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="https://api.test.com"),
            capabilities=frozenset({Capability.CHAT}),
        )

        catalog = ModelCatalog()
        catalog.register_provider(record)
        catalog.freeze()

        manager = ProviderManager(factory, catalog=catalog)

        asyncio.run(manager.start())
        self.assertEqual(manager.provider_count, 1)

        asyncio.run(manager.stop())
        self.assertEqual(manager.provider_count, 0)
        self.assertFalse(manager.initialized)

    def test_start_twice_is_idempotent(self):
        """Calling start() twice is a no-op on the second call."""
        import asyncio
        from app.intelligence.registry.catalog.catalog import ModelCatalog

        factory = ProviderFactory()
        factory.register(ProviderType.OPENAI_COMPATIBLE.value, MockProvider)

        record = ProviderRecord(
            provider_id="p1",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="https://api.test.com"),
            capabilities=frozenset({Capability.CHAT}),
        )

        catalog = ModelCatalog()
        catalog.register_provider(record)
        catalog.freeze()

        manager = ProviderManager(factory, catalog=catalog)

        asyncio.run(manager.start())
        first_count = manager.provider_count

        asyncio.run(manager.start())  # must not raise
        self.assertEqual(manager.provider_count, first_count)


if __name__ == "__main__":
    unittest.main()
