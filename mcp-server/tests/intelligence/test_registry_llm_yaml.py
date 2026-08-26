"""Integration tests for the unified llm.yaml → catalog → router pipeline.

These tests verify that:
1. RegistryRuntime correctly loads llm.yaml (not split config)
2. The catalog is built with correct provider_id normalization
3. Routing decisions return model_id (not deployment_name)
4. LLMService propagates deployment_name from ModelRecord → ChatOptions
5. PriorityStrategy behavior is preserved with the unified config
"""

import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.intelligence.inference.router.router import Router
from app.intelligence.inference.services.llm_service import LLMService
from app.intelligence.inference.strategies.priority import PriorityStrategy
from app.intelligence.ports.chat import ChatMessage, ChatOptions
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.providers.provider_manager import ProviderManager
from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoader
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
from app.intelligence.runtime import RegistryRuntime, RegistryRuntimeSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_yaml(
    providers: list[dict],
) -> str:
    """Serialize a list of provider dicts to llm.yaml YAML text."""
    import yaml
    return yaml.safe_dump({"llm": {"providers": providers}}, default_flow_style=False)


def _write_llm_yaml(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# RegistryRuntime with llm.yaml
# ---------------------------------------------------------------------------

class TestRegistryRuntimeUnifiedConfig(unittest.TestCase):
    """RegistryRuntime loads llm.yaml (not split config) and builds a frozen catalog."""

    def test_start_with_llm_yaml_builds_catalog(self):
        yaml_content = _make_llm_yaml([
            {
                "id": "test-provider",
                "type": "ollama",
                "deployment": "self_hosted",
                "connection": {"base_url": "http://localhost:11434"},
                "models": [
                    {
                        "id": "llama3",
                        "type": "chat",
                        "capabilities": ["chat"],
                    },
                ],
            },
        ])
        path = _write_llm_yaml(yaml_content)
        self.addCleanup(lambda: path.unlink(missing_ok=True))

        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=path, require_files=True),
        )
        catalog = runtime.start()

        self.assertTrue(runtime.started)
        self.assertTrue(catalog.frozen)
        provider = catalog.get_provider("test-provider")
        self.assertIsNotNone(provider)
        self.assertEqual(provider.provider_id, "test-provider")
        model = catalog.get_model("llama3")
        self.assertIsNotNone(model)
        self.assertEqual(model.provider_id, "test-provider")
        self.assertEqual(model.capabilities, frozenset({Capability.CHAT}))

    def test_start_with_empty_llm_yaml_builds_empty_catalog(self):
        path = _write_llm_yaml(_make_llm_yaml([]))
        self.addCleanup(lambda: path.unlink(missing_ok=True))

        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=path),
        )
        catalog = runtime.start()

        self.assertTrue(catalog.frozen)
        self.assertTrue(catalog.is_empty)

    def test_llm_yaml_missing_raises(self):
        path = Path("/tmp/does-not-exist-xyz.yaml")
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=path, require_files=True),
        )
        with self.assertRaises(FileNotFoundError):
            runtime.start()

    def test_llm_yaml_missing_optional_builds_empty(self):
        path = Path("/tmp/does-not-exist-xyz.yaml")
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=path, require_files=False),
        )
        catalog = runtime.start()
        self.assertTrue(catalog.is_empty)

    def test_invalid_llm_yaml_raises(self):
        path = _write_llm_yaml("llm:\n  providers:\n    - bad: :\n")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        from app.intelligence.registry.exceptions import RegistryLoadError

        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=path),
        )
        with self.assertRaises(RegistryLoadError):
            runtime.start()

    def test_invalid_llm_yaml_structure_raises(self):
        path = _write_llm_yaml(_make_llm_yaml([
            {
                "id": "dup-provider",
                "type": "ollama",
                "deployment": "self_hosted",
                "connection": {"base_url": "http://localhost:11434"},
                "models": [],
            },
            {
                "id": "dup-provider",
                "type": "openai_compatible",
                "deployment": "cloud",
                "connection": {"base_url": "https://api.example.com"},
                "models": [],
            },
        ]))
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        from app.intelligence.registry.exceptions import (
            RegistryLoadError,
            RegistryValidationError,
        )

        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=path),
        )
        with self.assertRaises((RegistryLoadError, RegistryValidationError)):
            runtime.start()

    def test_provider_id_normalized_from_llm_yaml_hierarchy(self):
        path = _write_llm_yaml(_make_llm_yaml([
            {
                "id": "parent-provider",
                "type": "ollama",
                "deployment": "self_hosted",
                "connection": {"base_url": "http://localhost:11434"},
                "models": [
                    {"id": "model-1", "type": "chat", "capabilities": ["chat"]},
                    {"id": "model-2", "type": "chat", "capabilities": ["chat"]},
                ],
            },
        ]))
        self.addCleanup(lambda: path.unlink(missing_ok=True))

        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=path),
        )
        catalog = runtime.start()

        model_1 = catalog.get_model("model-1")
        model_2 = catalog.get_model("model-2")
        self.assertEqual(model_1.provider_id, "parent-provider")
        self.assertEqual(model_2.provider_id, "parent-provider")
        self.assertEqual(model_1.provider_id, model_2.provider_id)


# ---------------------------------------------------------------------------
# Routing with deployment_name
# ---------------------------------------------------------------------------

class TestRouterWithDeploymentName(unittest.TestCase):
    """Router.route() returns RoutingDecision with model_id (not deployment_name).

    The LLMService is responsible for resolving deployment_name from the
    ModelRecord and injecting it into ChatOptions.
    """

    def setUp(self):
        # Build a catalog that includes deployment_name.
        self.catalog = ModelCatalog()

        p_bedrock = ProviderRecord(
            provider_id="bedrock",
            provider_type=ProviderType.BEDROCK,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url=""),
            capabilities=frozenset({Capability.CHAT}),
        )
        p_ollama = ProviderRecord(
            provider_id="ollama",
            provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="http://localhost:11434"),
            capabilities=frozenset({Capability.CHAT}),
        )

        # ModelRecord with deployment_name != model_id (Bedrock pattern).
        m_bedrock = ModelRecord(
            model_id="claude-sonnet",
            provider_id="bedrock",
            model_type=ModelType.CHAT,
            deployment_name="anthropic.claude-3-sonnet-20240229-v1:0",
            capabilities=frozenset({Capability.CHAT}),
            priority=10,
        )
        # ModelRecord with deployment_name == model_id (Ollama pattern).
        m_ollama = ModelRecord(
            model_id="llama3",
            provider_id="ollama",
            model_type=ModelType.CHAT,
            deployment_name="llama3",
            capabilities=frozenset({Capability.CHAT}),
            priority=10,
        )
        # ModelRecord with no deployment_name (defaults to None).
        m_ollama_no_dn = ModelRecord(
            model_id="mistral",
            provider_id="ollama",
            model_type=ModelType.CHAT,
            deployment_name=None,
            capabilities=frozenset({Capability.CHAT}),
            priority=20,
        )

        for p in [p_bedrock, p_ollama]:
            self.catalog.register_provider(p)
        for m in [m_bedrock, m_ollama, m_ollama_no_dn]:
            self.catalog.register_model(m)

        self.catalog.freeze()
        self.router = Router(self.catalog, PriorityStrategy(self.catalog))

    def test_route_returns_model_id_not_deployment_name(self):
        decision = self.router.route(Capability.CHAT, model="claude-sonnet")
        # RoutingDecision carries the logical model_id.
        self.assertEqual(decision.model_id, "claude-sonnet")
        self.assertEqual(decision.provider_id, "bedrock")

    def test_route_explicit_model_with_deployment_name(self):
        # The catalog has a model with deployment_name != model_id.
        # The router should still find it by model_id.
        decision = self.router.route(Capability.CHAT, model="claude-sonnet")
        self.assertEqual(decision.model_id, "claude-sonnet")
        self.assertIsNotNone(decision.provider_id)

    def test_route_capability_only_returns_best_model_by_priority(self):
        # SELF_HOSTED (ollama) is selected before CLOUD (bedrock).
        decision = self.router.route(Capability.CHAT)
        # m_ollama has priority=10 and is SELF_HOSTED.
        self.assertEqual(decision.model_id, "llama3")
        self.assertEqual(decision.provider_id, "ollama")

    def test_catalog_get_model_returns_deployment_name(self):
        model = self.catalog.get_model("claude-sonnet")
        self.assertIsNotNone(model)
        self.assertEqual(model.deployment_name, "anthropic.claude-3-sonnet-20240229-v1:0")
        self.assertNotEqual(model.model_id, model.deployment_name)

    def test_catalog_get_model_deployment_name_none(self):
        model = self.catalog.get_model("mistral")
        self.assertIsNotNone(model)
        self.assertIsNone(model.deployment_name)


# ---------------------------------------------------------------------------
# LLMService deployment_name propagation
# ---------------------------------------------------------------------------

class TestLLMServiceDeploymentNamePropagation(unittest.IsolatedAsyncioTestCase):
    """LLMService resolves deployment_name from ModelRecord and passes it to adapters."""

    async def test_chat_propagates_deployment_name_to_adapter(self):
        catalog = ModelCatalog()

        p_ollama = ProviderRecord(
            provider_id="ollama",
            provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="http://localhost:11434"),
            capabilities=frozenset({Capability.CHAT}),
        )
        m_model = ModelRecord(
            model_id="llama3",
            provider_id="ollama",
            model_type=ModelType.CHAT,
            deployment_name="llama3:latest",
            capabilities=frozenset({Capability.CHAT}),
            priority=10,
        )

        catalog.register_provider(p_ollama)
        catalog.register_model(m_model)
        catalog.freeze()

        # Build a mock adapter.
        mock_provider = MagicMock()
        mock_provider._check_started = MagicMock()
        mock_provider.chat = AsyncMock(
            return_value=MagicMock(
                content="hello",
                model="llama3",
                finish_reason="stop",
                usage=None,
            )
        )

        # Patch ProviderManager to return our mock.
        pm = ProviderManager(MagicMock(), catalog)
        pm._providers = {"ollama": mock_provider}
        pm._initialized = True

        service = LLMService(pm, catalog)
        response = await service.chat(
            [ChatMessage(role="user", content="hi")],
            model="llama3",
        )

        # Verify chat was called with the correct ChatOptions.
        call_args = mock_provider.chat.call_args
        opts = call_args[0][1]  # second positional arg = ChatOptions
        self.assertIsInstance(opts, ChatOptions)
        self.assertEqual(opts.model, "llama3")
        self.assertEqual(opts.deployment_name, "llama3:latest")

    async def test_chat_with_no_deployment_name_in_record(self):
        catalog = ModelCatalog()

        p_ollama = ProviderRecord(
            provider_id="ollama",
            provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED,
            auth=AuthConfig(),
            connection=ConnectionConfig(base_url="http://localhost:11434"),
            capabilities=frozenset({Capability.CHAT}),
        )
        m_model = ModelRecord(
            model_id="mistral",
            provider_id="ollama",
            model_type=ModelType.CHAT,
            deployment_name=None,
            capabilities=frozenset({Capability.CHAT}),
            priority=10,
        )

        catalog.register_provider(p_ollama)
        catalog.register_model(m_model)
        catalog.freeze()

        mock_provider = MagicMock()
        mock_provider._check_started = MagicMock()
        mock_provider.chat = AsyncMock(
            return_value=MagicMock(
                content="hello",
                model="mistral",
                finish_reason="stop",
                usage=None,
            )
        )

        pm = ProviderManager(MagicMock(), catalog)
        pm._providers = {"ollama": mock_provider}
        pm._initialized = True

        service = LLMService(pm, catalog)
        response = await service.chat(
            [ChatMessage(role="user", content="hi")],
            model="mistral",
        )

        call_args = mock_provider.chat.call_args
        opts = call_args[0][1]
        self.assertIsInstance(opts, ChatOptions)
        self.assertEqual(opts.model, "mistral")
        self.assertIsNone(opts.deployment_name)


# ---------------------------------------------------------------------------
# CatalogBuilder with unified config
# ---------------------------------------------------------------------------

class TestCatalogBuilderUnifiedConfig(unittest.TestCase):
    """CatalogBuilder.build_from_llm_config_result correctly assembles the catalog."""

    def test_build_from_llm_config_result_registers_providers_first(self):
        loader = LLmConfigLoader()
        yaml_content = _make_llm_yaml([
            {
                "id": "test-provider",
                "type": "ollama",
                "deployment": "self_hosted",
                "connection": {"base_url": "http://localhost:11434"},
                "models": [
                    {"id": "model-a", "type": "chat", "capabilities": ["chat"]},
                    {"id": "model-b", "type": "chat", "capabilities": ["chat"]},
                ],
            },
        ])
        path = _write_llm_yaml(yaml_content)
        self.addCleanup(lambda: path.unlink(missing_ok=True))

        result = loader.load(path)

        from app.intelligence.registry.builders.catalog_builder import CatalogBuilder

        builder = CatalogBuilder()
        catalog, _, _ = builder.build_from_llm_config_result(result)

        self.assertTrue(catalog.frozen)
        self.assertEqual(len(list(catalog.iter_providers())), 1)
        self.assertEqual(len(list(catalog.iter_models())), 2)

        provider = catalog.get_provider("test-provider")
        self.assertEqual(provider.provider_id, "test-provider")
        for model in catalog.iter_models():
            self.assertEqual(model.provider_id, "test-provider")

    def test_build_from_llm_config_result_derives_provider_capabilities(self):
        loader = LLmConfigLoader()
        yaml_content = _make_llm_yaml([
            {
                "id": "multi-cap",
                "type": "openai_compatible",
                "deployment": "cloud",
                "connection": {"base_url": "https://api.example.com"},
                "models": [
                    {"id": "chat-model", "type": "chat", "capabilities": ["chat", "embedding"]},
                ],
            },
        ])
        path = _write_llm_yaml(yaml_content)
        self.addCleanup(lambda: path.unlink(missing_ok=True))

        result = loader.load(path)

        from app.intelligence.registry.builders.catalog_builder import CatalogBuilder

        builder = CatalogBuilder()
        catalog, _, _ = builder.build_from_llm_config_result(result)

        provider = catalog.get_provider("multi-cap")
        self.assertEqual(
            provider.capabilities,
            frozenset({Capability.CHAT, Capability.EMBEDDING}),
        )

    def test_catalog_with_multiple_providers_multiple_models(self):
        loader = LLmConfigLoader()
        yaml_content = _make_llm_yaml([
            {
                "id": "provider-a",
                "type": "ollama",
                "deployment": "self_hosted",
                "connection": {"base_url": "http://localhost:11434"},
                "models": [
                    {"id": "model-a1", "type": "chat", "capabilities": ["chat"]},
                ],
            },
            {
                "id": "provider-b",
                "type": "openai_compatible",
                "deployment": "cloud",
                "connection": {"base_url": "https://api.example.com"},
                "models": [
                    {"id": "model-b1", "type": "chat", "capabilities": ["chat"]},
                    {"id": "model-b2", "type": "embedding", "capabilities": ["embedding"]},
                ],
            },
        ])
        path = _write_llm_yaml(yaml_content)
        self.addCleanup(lambda: path.unlink(missing_ok=True))

        result = loader.load(path)

        from app.intelligence.registry.builders.catalog_builder import CatalogBuilder

        builder = CatalogBuilder()
        catalog, _, _ = builder.build_from_llm_config_result(result)

        providers = list(catalog.iter_providers())
        models = list(catalog.iter_models())
        self.assertEqual(len(providers), 2)
        self.assertEqual(len(models), 3)

        pa_models = catalog.models_by_provider("provider-a")
        pb_models = catalog.models_by_provider("provider-b")
        self.assertEqual(len(pa_models), 1)
        self.assertEqual(len(pb_models), 2)
        self.assertEqual(pa_models[0].model_id, "model-a1")


if __name__ == "__main__":
    unittest.main()
