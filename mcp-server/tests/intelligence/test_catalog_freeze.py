"""Unit tests for the frozen catalog and lookup indexes (Phase 2)."""

import unittest

from app.intelligence.registry.catalog.catalog import (
    CatalogFrozenError,
    ModelCatalog,
)
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import (
    AuthConfig,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.model import ModelType
from app.intelligence.registry.types.provider import ProviderType


def _provider(
    provider_id: str,
    *,
    provider_type: ProviderType = ProviderType.OPENAI_COMPATIBLE,
    deployment: DeploymentType = DeploymentType.CLOUD,
    capabilities: frozenset = frozenset({Capability.CHAT}),
    enabled: bool = True,
    priority: int = 100,
) -> ProviderRecord:
    return ProviderRecord(
        provider_id=provider_id,
        provider_type=provider_type,
        deployment=deployment,
        auth=AuthConfig(),
        connection=ConnectionConfig(base_url="https://api.example.com"),
        capabilities=capabilities,
        enabled=enabled,
        priority=priority,
    )


def _model(
    model_id: str,
    provider_id: str,
    *,
    model_type: ModelType = ModelType.CHAT,
    capabilities: frozenset = frozenset({Capability.CHAT}),
    priority: int = 100,
) -> ModelRecord:
    return ModelRecord(
        model_id=model_id,
        provider_id=provider_id,
        model_type=model_type,
        capabilities=capabilities,
        priority=priority,
    )


class CatalogFreezeTests(unittest.TestCase):
    """Catalog mutation must be rejected after :meth:`freeze`."""

    def setUp(self):
        self.catalog = ModelCatalog()
        self.catalog.register_provider(
            _provider("p1", priority=10)
        )
        self.catalog.register_model(_model("m1", "p1"))
        self.catalog.freeze()

    def test_register_provider_after_freeze_raises(self):
        with self.assertRaises(CatalogFrozenError):
            self.catalog.register_provider(_provider("p2"))

    def test_register_model_after_freeze_raises(self):
        with self.assertRaises(CatalogFrozenError):
            self.catalog.register_model(_model("m2", "p1"))

    def test_clear_after_freeze_raises(self):
        with self.assertRaises(CatalogFrozenError):
            self.catalog.clear()

    def test_freeze_is_idempotent(self):
        # Calling freeze again must not raise.
        self.catalog.freeze()
        self.assertTrue(self.catalog.frozen)

    def test_views_are_read_only(self):
        providers_view = self.catalog.providers_view
        with self.assertRaises(TypeError):
            providers_view["mutate"] = "x"  # type: ignore[index]


class CatalogIndexesTests(unittest.TestCase):
    """Secondary indexes must be consistent with the primary keys."""

    def setUp(self):
        self.catalog = ModelCatalog()
        self.catalog.register_provider(
            _provider(
                "cloud-provider",
                deployment=DeploymentType.CLOUD,
                capabilities=frozenset({Capability.CHAT}),
            )
        )
        self.catalog.register_provider(
            _provider(
                "selfhost-provider",
                deployment=DeploymentType.SELF_HOSTED,
                capabilities=frozenset({Capability.CHAT, Capability.EMBEDDING}),
            )
        )
        self.catalog.register_model(_model("chat-a", "cloud-provider"))
        self.catalog.register_model(_model("chat-b", "selfhost-provider"))
        self.catalog.register_model(
            ModelRecord(
                model_id="embed-1",
                provider_id="selfhost-provider",
                model_type=ModelType.EMBEDDING,
                capabilities=frozenset({Capability.EMBEDDING}),
            )
        )

    def test_models_by_provider(self):
        result = self.catalog.models_by_provider("cloud-provider")
        self.assertEqual({m.model_id for m in result}, {"chat-a"})

    def test_models_by_capability_chat(self):
        result = self.catalog.find_models_by_capability(Capability.CHAT)
        ids = {m.model_id for m in result}
        self.assertEqual(ids, {"chat-a", "chat-b"})

    def test_models_by_capability_embedding(self):
        result = self.catalog.find_models_by_capability(Capability.EMBEDDING)
        self.assertEqual({m.model_id for m in result}, {"embed-1"})

    def test_models_by_deployment_index(self):
        # Self-hosted models include both chat-b and embed-1.
        # Use list_models with deployment filter (the deployment index
        # is internal; the public surface is list_models).
        result = self.catalog.list_models(deployment=DeploymentType.SELF_HOSTED)
        ids = {m.model_id for m in result}
        self.assertEqual(ids, {"chat-b", "embed-1"})

    def test_providers_by_capability(self):
        chat_providers = self.catalog.providers_by_capability(Capability.CHAT)
        self.assertEqual(
            {p.provider_id for p in chat_providers},
            {"cloud-provider", "selfhost-provider"},
        )
        emb_providers = self.catalog.providers_by_capability(Capability.EMBEDDING)
        self.assertEqual(
            {p.provider_id for p in emb_providers},
            {"selfhost-provider"},
        )

    def test_providers_by_deployment(self):
        self_hosted = self.catalog.providers_by_deployment(DeploymentType.SELF_HOSTED)
        self.assertEqual(
            {p.provider_id for p in self_hosted},
            {"selfhost-provider"},
        )

    def test_list_providers_with_capability_filter(self):
        result = self.catalog.list_providers(capability=Capability.EMBEDDING)
        self.assertEqual(
            {p.provider_id for p in result},
            {"selfhost-provider"},
        )

    def test_list_models_with_capability_and_deployment(self):
        result = self.catalog.list_models(
            capability=Capability.CHAT,
            deployment=DeploymentType.SELF_HOSTED,
        )
        self.assertEqual({m.model_id for m in result}, {"chat-b"})

    def test_results_are_sorted_by_priority(self):
        self.catalog.register_provider(
            _provider("high-priority", priority=10)
        )
        result = self.catalog.list_providers()
        ids = [p.provider_id for p in result]
        # high-priority (10) before the rest (100).
        self.assertLess(
            ids.index("high-priority"),
            ids.index("cloud-provider"),
        )


class CatalogBuilderFreezeTests(unittest.TestCase):
    """CatalogBuilder must freeze the catalog on build."""

    def test_catalog_is_frozen_after_build(self):
        from app.intelligence.registry.builders.catalog_builder import CatalogBuilder
        from app.intelligence.registry.loaders.registry_loader import RegistryLoader

        builder = CatalogBuilder(RegistryLoader())
        catalog, _ = builder.build_combined(
            {
                "providers": [
                    {
                        "provider_id": "p1",
                        "provider_type": "openai_compatible",
                        "deployment": "cloud",
                        "connection": {"base_url": "https://api.example.com"},
                    }
                ],
                "models": [
                    {
                        "model_id": "m1",
                        "provider_id": "p1",
                        "model_type": "chat",
                        "capabilities": ["chat"],
                    }
                ],
            }
        )
        self.assertTrue(catalog.frozen)
        with self.assertRaises(CatalogFrozenError):
            catalog.register_provider(_provider("p2"))


if __name__ == "__main__":
    unittest.main()