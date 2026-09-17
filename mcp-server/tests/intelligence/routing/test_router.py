"""Tests for Router and PriorityStrategy."""

import unittest

from app.intelligence.exceptions import LLMModelNotFoundError, LLMProviderError
from app.intelligence.inference.router.router import Router
from app.intelligence.inference.strategies.base import RoutingContext, RoutingDecision
from app.intelligence.inference.strategies.priority import PriorityStrategy
from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.models.model import ModelRecord, ModelType
from app.intelligence.registry.models.provider import (
    AuthConfig,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


def _make_catalog() -> ModelCatalog:
    """Build a test catalog with two providers and four models.

    Provider p_ollama (SELF_HOSTED, priority=10):
      - m_ollama_chat  (CHAT, priority=20)
      - m_ollama_embed (EMBEDDING, priority=20)

    Provider p_cloud (CLOUD, priority=20):
      - m_cloud_chat  (CHAT, priority=5)
      - m_cloud_chat_higher_priority (CHAT, priority=1)

    Provider p_proxy (PROXY, priority=15):
      - m_proxy_chat (CHAT, priority=10)
    """
    cat = ModelCatalog()

    p_ollama = ProviderRecord(
        provider_id="p_ollama",
        provider_type=ProviderType.OLLAMA,
        deployment=DeploymentType.SELF_HOSTED,
        auth=AuthConfig(),
        connection=ConnectionConfig(base_url="http://localhost:11434"),
        capabilities=frozenset({Capability.CHAT, Capability.EMBEDDING}),
        enabled=True,
        priority=10,
    )
    p_cloud = ProviderRecord(
        provider_id="p_cloud",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(),
        connection=ConnectionConfig(base_url="https://api.openai.com/v1"),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=20,
    )
    p_proxy = ProviderRecord(
        provider_id="p_proxy",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.PROXY,
        auth=AuthConfig(),
        connection=ConnectionConfig(base_url="http://proxy:8080/v1"),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=15,
    )
    p_cloud_disabled = ProviderRecord(
        provider_id="p_cloud_disabled",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(),
        connection=ConnectionConfig(base_url="https://disabled.example.com/v1"),
        capabilities=frozenset({Capability.CHAT}),
        enabled=False,
        priority=30,
    )

    m_ollama_chat = ModelRecord(
        provider_id="p_ollama",
        model_id="m_ollama_chat",
        model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}),
        context_window=8192,
        priority=20,
    )
    m_ollama_embed = ModelRecord(
        provider_id="p_ollama",
        model_id="m_ollama_embed",
        model_type=ModelType.EMBEDDING,
        capabilities=frozenset({Capability.EMBEDDING}),
        context_window=None,
        priority=20,
    )
    m_cloud_chat = ModelRecord(
        provider_id="p_cloud",
        model_id="m_cloud_chat",
        model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}),
        context_window=128000,
        priority=5,
    )
    m_cloud_chat_hp = ModelRecord(
        provider_id="p_cloud",
        model_id="m_cloud_chat_hp",
        model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}),
        context_window=128000,
        priority=1,
    )
    m_proxy_chat = ModelRecord(
        provider_id="p_proxy",
        model_id="m_proxy_chat",
        model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}),
        context_window=16384,
        priority=10,
    )
    m_disabled_chat = ModelRecord(
        provider_id="p_cloud_disabled",
        model_id="m_disabled_chat",
        model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}),
        context_window=128000,
        priority=1,
    )

    for p in [p_ollama, p_cloud, p_proxy, p_cloud_disabled]:
        cat.register_provider(p)
    for m in [m_ollama_chat, m_ollama_embed, m_cloud_chat,
              m_cloud_chat_hp, m_proxy_chat, m_disabled_chat]:
        cat.register_model(m)

    cat.freeze()
    return cat


class TestPriorityStrategy(unittest.TestCase):
    """Tests for PriorityStrategy."""

    def setUp(self) -> None:
        self.catalog = _make_catalog()
        self.strategy = PriorityStrategy(self.catalog)

    def test_name(self) -> None:
        self.assertEqual(self.strategy.name, "priority")

    def test_get_candidates_chat_capability(self) -> None:
        context = RoutingContext(
            capability=Capability.CHAT,
            requested_model=None,
            requested_provider=None,
            metadata={},
        )
        decisions = self.strategy.get_candidates(context)
        model_ids = {d.model_id for d in decisions}
        # p_cloud_disabled is not included because enabled_providers_only=True
        self.assertEqual(
            model_ids,
            {"m_ollama_chat", "m_cloud_chat",
             "m_cloud_chat_hp", "m_proxy_chat"},
        )

    def test_get_candidates_embedding_capability(self) -> None:
        context = RoutingContext(
            capability=Capability.EMBEDDING,
            requested_model=None,
            requested_provider=None,
            metadata={},
        )
        decisions = self.strategy.get_candidates(context)
        model_ids = {d.model_id for d in decisions}
        self.assertEqual(model_ids, {"m_ollama_embed"})

    def test_select_deployment_order(self) -> None:
        """Self-hosted is selected before proxy, proxy before cloud."""
        context = RoutingContext(
            capability=Capability.CHAT,
            requested_model=None,
            requested_provider=None,
            metadata={},
        )
        candidates = self.strategy.get_candidates(context)
        decision = self.strategy.select(candidates, context)
        # p_ollama is SELF_HOSTED priority=10 → comes first
        self.assertEqual(decision.provider_id, "p_ollama")
        self.assertEqual(decision.model_id, "m_ollama_chat")
        self.assertEqual(decision.strategy_name, "priority")

    def test_select_model_priority_tiebreak(self) -> None:
        """When two models have the same deployment, lower priority wins."""
        context = RoutingContext(
            capability=Capability.CHAT,
            requested_model=None,
            requested_provider=None,
            metadata={},
        )
        # Only cloud candidates — both CLOUD deployment
        cloud_decisions = [
            RoutingDecision(
                provider_id="p_cloud",
                model_id="m_cloud_chat",
                strategy_name="priority",
                reason="test",
            ),
            RoutingDecision(
                provider_id="p_cloud",
                model_id="m_cloud_chat_hp",
                strategy_name="priority",
                reason="test",
            ),
        ]
        decision = self.strategy.select(cloud_decisions, context)
        # m_cloud_chat_hp has priority=1 (lower than m_cloud_chat priority=5)
        self.assertEqual(decision.model_id, "m_cloud_chat_hp")

    def test_select_stable_tiebreak_by_model_id(self) -> None:
        """When deployment and priority are equal, model_id is the tiebreak."""
        strategy = PriorityStrategy(self.catalog)

        # Two candidates with identical deployment and priority
        tie_decisions = [
            RoutingDecision(
                provider_id="p_ollama",
                model_id="zzz_model",
                strategy_name="priority",
                reason="test",
            ),
            RoutingDecision(
                provider_id="p_ollama",
                model_id="aaa_model",
                strategy_name="priority",
                reason="test",
            ),
        ]
        context = RoutingContext(
            capability=Capability.CHAT,
            requested_model=None,
            requested_provider=None,
            metadata={},
        )
        decision = strategy.select(tie_decisions, context)
        # Lexicographic: "aaa_model" < "zzz_model"
        self.assertEqual(decision.model_id, "aaa_model")

    def test_select_empty_returns_none(self) -> None:
        context = RoutingContext(
            capability=Capability.VISION,
            requested_model=None,
            requested_provider=None,
            metadata={},
        )
        decision = self.strategy.select([], context)
        self.assertIsNone(decision.provider_id)
        self.assertIsNone(decision.model_id)
        self.assertEqual(decision.strategy_name, "priority")
        self.assertIn("no candidate", decision.reason)

    def test_deterministic_no_randomness(self) -> None:
        """Calling select multiple times returns the same result."""
        context = RoutingContext(
            capability=Capability.CHAT,
            requested_model=None,
            requested_provider=None,
            metadata={},
        )
        candidates = self.strategy.get_candidates(context)
        results = [self.strategy.select(candidates, context) for _ in range(10)]
        for r in results:
            self.assertEqual(r.model_id, results[0].model_id)
            self.assertEqual(r.provider_id, results[0].provider_id)


class TestRouterExplicitModel(unittest.TestCase):
    """Tests for Router.route() with an explicit model."""

    def setUp(self) -> None:
        self.catalog = _make_catalog()
        self.router = Router(self.catalog, PriorityStrategy(self.catalog))

    def test_explicit_model_returns_decision(self) -> None:
        decision = self.router.route(Capability.CHAT, model="m_ollama_chat")
        self.assertEqual(decision.provider_id, "p_ollama")
        self.assertEqual(decision.model_id, "m_ollama_chat")
        self.assertEqual(decision.strategy_name, "explicit_model")

    def test_explicit_model_with_provider_hint(self) -> None:
        decision = self.router.route(
            Capability.CHAT,
            model="m_cloud_chat",
            provider="p_cloud",
        )
        self.assertEqual(decision.provider_id, "p_cloud")
        self.assertEqual(decision.model_id, "m_cloud_chat")

    def test_explicit_model_wrong_capability_raises(self) -> None:
        with self.assertRaises(LLMModelNotFoundError) as ctx:
            self.router.route(Capability.VISION, model="m_ollama_chat")
        self.assertIn("does not support capability 'vision'", str(ctx.exception))
        self.assertIn("m_ollama_chat", str(ctx.exception))

    def test_explicit_model_provider_mismatch_raises(self) -> None:
        with self.assertRaises(LLMProviderError) as ctx:
            self.router.route(
                Capability.CHAT,
                model="m_ollama_chat",
                provider="p_cloud",
            )
        self.assertIn("m_ollama_chat", str(ctx.exception))
        self.assertIn("p_ollama", str(ctx.exception))
        self.assertIn("p_cloud", str(ctx.exception))

    def test_explicit_model_not_found_raises(self) -> None:
        with self.assertRaises(LLMModelNotFoundError) as ctx:
            self.router.route(Capability.CHAT, model="nonexistent_model")
        self.assertIn("not found in the catalog", str(ctx.exception))


class TestRouterExplicitProvider(unittest.TestCase):
    """Tests for Router.route() with an explicit provider but no model."""

    def setUp(self) -> None:
        self.catalog = _make_catalog()
        self.router = Router(self.catalog, PriorityStrategy(self.catalog))

    def test_explicit_provider_returns_capable_model(self) -> None:
        # p_proxy has CHAT; strategy picks lowest-priority model on proxy
        decision = self.router.route(Capability.CHAT, provider="p_proxy")
        self.assertEqual(decision.provider_id, "p_proxy")
        self.assertEqual(decision.model_id, "m_proxy_chat")

    def test_explicit_provider_no_capable_model_raises(self) -> None:
        with self.assertRaises(LLMProviderError) as ctx:
            self.router.route(Capability.EMBEDDING, provider="p_proxy")
        self.assertIn("p_proxy", str(ctx.exception))
        self.assertIn("embedding", str(ctx.exception))

    def test_explicit_provider_not_found_raises(self) -> None:
        with self.assertRaises(LLMModelNotFoundError) as ctx:
            self.router.route(Capability.CHAT, provider="nonexistent_provider")
        self.assertIn("not found in the catalog", str(ctx.exception))

    def test_explicit_disabled_provider_raises(self) -> None:
        with self.assertRaises(LLMProviderError) as ctx:
            self.router.route(Capability.CHAT, provider="p_cloud_disabled")
        self.assertIn("p_cloud_disabled", str(ctx.exception))
        self.assertIn("not enabled", str(ctx.exception))


class TestRouterCapabilityOnly(unittest.TestCase):
    """Tests for Router.route() with capability only (strategy-selected)."""

    def setUp(self) -> None:
        self.catalog = _make_catalog()
        self.router = Router(self.catalog, PriorityStrategy(self.catalog))

    def test_capability_only_uses_strategy(self) -> None:
        decision = self.router.route(Capability.CHAT)
        # Priority strategy selects p_ollama (SELF_HOSTED) over p_proxy
        # and p_cloud, even though p_ollama's model has priority=20 vs p_cloud
        # model priority=5 — SELF_HOSTED always wins over CLOUD
        self.assertEqual(decision.provider_id, "p_ollama")
        self.assertEqual(decision.model_id, "m_ollama_chat")
        self.assertEqual(decision.strategy_name, "priority")

    def test_capability_embedding_ollama_selected(self) -> None:
        decision = self.router.route(Capability.EMBEDDING)
        self.assertEqual(decision.provider_id, "p_ollama")
        self.assertEqual(decision.model_id, "m_ollama_embed")

    def test_capability_no_candidates_raises(self) -> None:
        with self.assertRaises(LLMModelNotFoundError) as ctx:
            self.router.route(Capability.VISION)
        self.assertIn("no capable model found", str(ctx.exception))


class TestRouterNoStrategy(unittest.TestCase):
    """Tests for Router when no strategy is configured."""

    def setUp(self) -> None:
        self.catalog = _make_catalog()

    def test_explicit_provider_no_strategy_uses_min_model_id(self) -> None:
        router = Router(self.catalog, default_strategy=None)
        decision = router.route(Capability.CHAT, provider="p_cloud")
        # min() by model_id lexicographic: "m_cloud_chat" < "m_cloud_chat_hp"
        # because "_" (ASCII 95) < end-of-string.
        self.assertEqual(decision.provider_id, "p_cloud")
        self.assertEqual(decision.model_id, "m_cloud_chat")

    def test_explicit_model_no_strategy_works(self) -> None:
        router = Router(self.catalog, default_strategy=None)
        decision = router.route(Capability.CHAT, model="m_proxy_chat")
        self.assertEqual(decision.provider_id, "p_proxy")
        self.assertEqual(decision.model_id, "m_proxy_chat")


class TestValidateModelCapability(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = _make_catalog()
        self.router = Router(self.catalog, PriorityStrategy(self.catalog))

    def test_validate_model_capability_returns_true(self) -> None:
        self.assertTrue(
            self.router.validate_model_capability("m_ollama_chat", Capability.CHAT)
        )
        self.assertTrue(
            self.router.validate_model_capability("m_ollama_embed", Capability.EMBEDDING)
        )

    def test_validate_model_capability_returns_false_wrong_cap(self) -> None:
        self.assertFalse(
            self.router.validate_model_capability("m_ollama_chat", Capability.EMBEDDING)
        )

    def test_validate_model_capability_returns_false_missing_model(self) -> None:
        self.assertFalse(
            self.router.validate_model_capability("nonexistent", Capability.CHAT)
        )


if __name__ == "__main__":
    unittest.main()
