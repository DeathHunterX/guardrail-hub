"""Tests for LLMService."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.intelligence.exceptions import (
    LLMConfigurationError,
    LLMModelNotFoundError,
    LLMProviderError,
)
from app.intelligence.inference.router.router import Router
from app.intelligence.inference.services.llm_service import LLMService
from app.intelligence.inference.strategies.priority import PriorityStrategy
from app.intelligence.ports.chat import ChatCapable, ChatMessage, ChatOptions, ChatResponse
from app.intelligence.ports.embedding import EmbeddingCapable, EmbeddingOptions, EmbeddingResponse
from app.intelligence.ports.rerank import RerankCapable, RerankDocument, RerankOptions, RerankResponse
from app.intelligence.ports.vision import VisionCapable, VisionOptions, VisionResponse
from app.intelligence.providers.base_provider import BaseProviderRuntime
from app.intelligence.providers.provider_manager import ProviderManager
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


def _make_catalog_and_router():
    """Build a frozen catalog and router for testing."""
    cat = ModelCatalog()

    p_ollama = ProviderRecord(
        provider_id="p_ollama",
        provider_type=ProviderType.OLLAMA,
        deployment=DeploymentType.SELF_HOSTED,
        auth=AuthConfig(),
        connection=ConnectionConfig(base_url="http://localhost:11434"),
        capabilities=frozenset({Capability.CHAT, Capability.EMBEDDING, Capability.VISION}),
        enabled=True,
        priority=10,
    )
    p_cloud = ProviderRecord(
        provider_id="p_cloud",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(api_key="key"),
        connection=ConnectionConfig(base_url="https://api.openai.com/v1"),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=20,
    )
    p_rerank = ProviderRecord(
        provider_id="p_rerank",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(api_key="key"),
        connection=ConnectionConfig(base_url="https://api.rerank.com/v1"),
        capabilities=frozenset({Capability.RERANK}),
        enabled=True,
        priority=20,
    )

    m_chat = ModelRecord(
        provider_id="p_ollama", model_id="m_chat", model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}), context_window=8192, priority=10,
    )
    m_embed = ModelRecord(
        provider_id="p_ollama", model_id="m_embed", model_type=ModelType.EMBEDDING,
        capabilities=frozenset({Capability.EMBEDDING}), context_window=None, priority=10,
    )
    m_vision = ModelRecord(
        provider_id="p_ollama", model_id="m_vision", model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.VISION, Capability.CHAT}), context_window=8192, priority=10,
    )
    m_cloud_chat = ModelRecord(
        provider_id="p_cloud", model_id="m_cloud_chat", model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}), context_window=128000, priority=5,
    )
    m_rerank = ModelRecord(
        provider_id="p_rerank", model_id="m_rerank", model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.RERANK}), context_window=None, priority=10,
    )

    for p in [p_ollama, p_cloud, p_rerank]:
        cat.register_provider(p)
    for m in [m_chat, m_embed, m_vision, m_cloud_chat, m_rerank]:
        cat.register_model(m)

    cat.freeze()
    router = Router(cat, PriorityStrategy(cat))
    return cat, router


def _make_started_adapter(capabilities):
    """Return a mock adapter that has _started=True and implements the given capability."""
    adapter = MagicMock(spec=BaseProviderRuntime)
    adapter._started = True
    adapter._check_started = MagicMock()
    adapter.capabilities = frozenset(capabilities)
    adapter.provider_id = "p_ollama"
    return adapter


class MockChatAdapter(BaseProviderRuntime):
    """A started, chat-only mock for integration testing."""

    def __init__(self):
        object.__setattr__(self, "_started", True)
        object.__setattr__(self, "_record", MagicMock(provider_id="p_ollama"))

    @property
    def provider_id(self):
        return "p_ollama"

    @property
    def provider_type(self):
        return ProviderType.OLLAMA.value

    @property
    def capabilities(self):
        return frozenset({Capability.CHAT})

    async def chat(self, messages, options):
        return ChatResponse(content="hello", model=options.model, finish_reason="stop")

    async def chat_stream(self, messages, options):
        for chunk in ["hel", "lo"]:
            yield chunk

    def validate_configuration(self):
        pass


class MockEmbeddingAdapter(BaseProviderRuntime):
    def __init__(self):
        object.__setattr__(self, "_started", True)
        object.__setattr__(self, "_record", MagicMock(provider_id="p_ollama"))

    @property
    def provider_id(self):
        return "p_ollama"

    @property
    def provider_type(self):
        return ProviderType.OLLAMA.value

    @property
    def capabilities(self):
        return frozenset({Capability.EMBEDDING})

    async def embed(self, texts, options):
        return EmbeddingResponse(
            embeddings=[[0.1, 0.2] for _ in texts],
            model=options.model,
        )

    def validate_configuration(self):
        pass


class MockVisionAdapter(BaseProviderRuntime):
    def __init__(self):
        object.__setattr__(self, "_started", True)
        object.__setattr__(self, "_record", MagicMock(provider_id="p_ollama"))

    @property
    def provider_id(self):
        return "p_ollama"

    @property
    def provider_type(self):
        return ProviderType.OLLAMA.value

    @property
    def capabilities(self):
        return frozenset({Capability.VISION})

    async def vision(self, messages, options):
        return VisionResponse(content="a cat sitting on a mat", model=options.model)

    def validate_configuration(self):
        pass


class MockRerankAdapter(BaseProviderRuntime):
    def __init__(self):
        object.__setattr__(self, "_started", True)
        object.__setattr__(self, "_record", MagicMock(provider_id="p_rerank"))

    @property
    def provider_id(self):
        return "p_rerank"

    @property
    def provider_type(self):
        return ProviderType.OPENAI_COMPATIBLE.value

    @property
    def capabilities(self):
        return frozenset({Capability.RERANK})

    async def rerank(self, documents, options):
        return RerankResponse(
            results=[],
            model=options.model,
        )

    def validate_configuration(self):
        pass


class TestLLMServiceConstruction(unittest.TestCase):
    def test_constructs_with_explicit_router(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        svc = LLMService(mgr, cat, router=router)
        self.assertIs(svc._router, router)

    def test_constructs_with_default_strategy_when_no_router(self):
        cat, _ = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        svc = LLMService(mgr, cat)
        # Router should be auto-constructed with PriorityStrategy
        self.assertIsInstance(svc._router, Router)
        self.assertEqual(svc._router._default_strategy.name, "priority")

    def test_constructs_with_given_strategy(self):
        cat, _ = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        strategy = MagicMock()
        strategy.name = "custom"
        svc = LLMService(mgr, cat, default_strategy=strategy)
        self.assertEqual(svc._router._default_strategy.name, "custom")


class TestLLMServiceChat(unittest.IsolatedAsyncioTestCase):
    async def test_chat_routes_to_correct_provider(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        mock_adapter = _make_started_adapter([Capability.CHAT])
        mgr.get_provider.return_value = mock_adapter
        mock_adapter.chat = AsyncMock(return_value=ChatResponse(
            content="test response", model="m_chat",
        ))

        svc = LLMService(mgr, cat, router=router)
        messages = [ChatMessage(role="user", content="hello")]
        response = await svc.chat(messages)

        mgr.get_provider.assert_called_once_with("p_ollama")
        mock_adapter._check_started.assert_called_once()
        mock_adapter.chat.assert_awaited_once()
        self.assertEqual(response.content, "test response")

    async def test_chat_with_explicit_model(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        mock_adapter = _make_started_adapter([Capability.CHAT])
        mgr.get_provider.return_value = mock_adapter
        mock_adapter.chat = AsyncMock(return_value=ChatResponse(
            content="cloud", model="m_cloud_chat",
        ))

        svc = LLMService(mgr, cat, router=router)
        response = await svc.chat(
            [ChatMessage(role="user", content="hello")],
            model="m_cloud_chat",
        )

        mgr.get_provider.assert_called_once_with("p_cloud")
        self.assertEqual(response.content, "cloud")

    async def test_chat_with_explicit_provider(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        mock_adapter = _make_started_adapter([Capability.CHAT])
        mgr.get_provider.return_value = mock_adapter
        mock_adapter.chat = AsyncMock(return_value=ChatResponse(
            content="cloud", model="m_cloud_chat",
        ))

        svc = LLMService(mgr, cat, router=router)
        response = await svc.chat(
            [ChatMessage(role="user", content="hello")],
            provider="p_cloud",
        )

        mgr.get_provider.assert_called_once_with("p_cloud")

    async def test_chat_no_capable_model_raises(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        svc = LLMService(mgr, cat, router=router)

        with self.assertRaises(LLMModelNotFoundError):
            await svc.chat([ChatMessage(role="user", content="hello")], model="nonexistent")

    async def test_chat_provider_not_started_raises(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        mgr.get_provider.return_value = None  # not started
        svc = LLMService(mgr, cat, router=router)

        with self.assertRaises(LLMProviderError) as ctx:
            await svc.chat([ChatMessage(role="user", content="hello")])
        self.assertIn("not started", str(ctx.exception))

    async def test_chat_passes_options_to_adapter(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        adapter = _make_started_adapter([Capability.CHAT])
        mgr.get_provider.return_value = adapter
        captured_opts: list[ChatOptions] = []

        async def capture_chat(msgs, opts):
            captured_opts.append(opts)

        adapter.chat = AsyncMock(side_effect=capture_chat)
        svc = LLMService(mgr, cat, router=router)

        await svc.chat(
            [ChatMessage(role="user", content="hi")],
            model="m_cloud_chat",
            temperature=0.9,
            max_tokens=100,
        )

        self.assertEqual(len(captured_opts), 1)
        self.assertEqual(captured_opts[0].model, "m_cloud_chat")
        self.assertEqual(captured_opts[0].temperature, 0.9)
        self.assertEqual(captured_opts[0].max_tokens, 100)


class TestLLMServiceChatStream(unittest.IsolatedAsyncioTestCase):
    async def test_chat_stream_returns_async_iterator(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        adapter = MockChatAdapter()
        mgr.get_provider.return_value = adapter

        svc = LLMService(mgr, cat, router=router)
        # Phase 7: chat_stream() returns tuple[str, AsyncIterator[str]].
        resolved_model, stream = await svc.chat_stream([ChatMessage(role="user", content="hi")])
        self.assertEqual(resolved_model, "m_chat")
        chunks = [c async for c in stream]
        self.assertEqual(chunks, ["hel", "lo"])


class TestLLMServiceEmbed(unittest.IsolatedAsyncioTestCase):
    async def test_embed_routes_to_embedding_capable(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        adapter = MockEmbeddingAdapter()
        mgr.get_provider.return_value = adapter

        svc = LLMService(mgr, cat, router=router)
        response = await svc.embed(["hello", "world"])

        self.assertEqual(len(response.embeddings), 2)
        self.assertEqual(response.model, "m_embed")

    async def test_embed_with_explicit_model(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        adapter = _make_started_adapter([Capability.EMBEDDING])
        mgr.get_provider.return_value = adapter
        captured_opts: list[EmbeddingOptions] = []

        async def capture_embed(texts, opts):
            captured_opts.append(opts)

        adapter.embed = AsyncMock(side_effect=capture_embed)
        svc = LLMService(mgr, cat, router=router)

        await svc.embed(["text"], model="m_embed", dimensions=512)

        self.assertEqual(captured_opts[0].dimensions, 512)

    async def test_embed_no_capable_model_raises(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        svc = LLMService(mgr, cat, router=router)

        with self.assertRaises(LLMModelNotFoundError):
            await svc.embed(["text"], model="m_cloud_chat")  # m_cloud_chat has no EMBEDDING


class TestLLMServiceVision(unittest.IsolatedAsyncioTestCase):
    async def test_vision_routes_correctly(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        adapter = MockVisionAdapter()
        mgr.get_provider.return_value = adapter

        svc = LLMService(mgr, cat, router=router)
        response = await svc.vision([("user", "https://example.com/cat.jpg")])

        self.assertIn("cat", response.content.lower())
        self.assertEqual(response.model, "m_vision")

    async def test_vision_passes_options(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        adapter = _make_started_adapter([Capability.VISION])
        mgr.get_provider.return_value = adapter
        captured_opts: list[VisionOptions] = []

        async def capture_vision(msgs, opts):
            captured_opts.append(opts)

        adapter.vision = AsyncMock(side_effect=capture_vision)
        svc = LLMService(mgr, cat, router=router)

        await svc.vision([("user", "img")], model="m_vision", max_tokens=50)

        self.assertEqual(captured_opts[0].max_tokens, 50)


class TestLLMServiceRerank(unittest.IsolatedAsyncioTestCase):
    async def test_rerank_routes_correctly(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        adapter = MockRerankAdapter()
        mgr.get_provider.return_value = adapter

        svc = LLMService(mgr, cat, router=router)
        docs = [RerankDocument(id="1", text="doc one"), RerankDocument(id="2", text="doc two")]
        response = await svc.rerank(docs, query="query")

        self.assertEqual(response.model, "m_rerank")

    async def test_rerank_passes_top_n(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        adapter = _make_started_adapter([Capability.RERANK])
        mgr.get_provider.return_value = adapter
        captured_opts: list[RerankOptions] = []

        async def capture_rerank(docs, opts):
            captured_opts.append(opts)

        adapter.rerank = AsyncMock(side_effect=capture_rerank)
        svc = LLMService(mgr, cat, router=router)

        await svc.rerank(
            [RerankDocument(id="1", text="doc")],
            query="query",
            model="m_rerank",
            top_n=5,
        )

        self.assertEqual(captured_opts[0].top_n, 5)


class TestLLMServiceConvenience(unittest.TestCase):
    def test_get_provider_delegates(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        mgr.get_provider.return_value = "the_adapter"
        svc = LLMService(mgr, cat, router=router)
        self.assertEqual(svc.get_provider("p_ollama"), "the_adapter")
        mgr.get_provider.assert_called_once_with("p_ollama")

    def test_list_available_providers_delegates(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)
        mgr.list_providers.return_value = ["p_ollama", "p_cloud"]
        svc = LLMService(mgr, cat, router=router)
        self.assertEqual(svc.list_available_providers(), ["p_ollama", "p_cloud"])

    def test_list_available_models_delegates(self):
        cat, router = _make_catalog_and_router()
        svc = LLMService(MagicMock(), cat, router=router)
        models = svc.list_available_models(provider_id="p_ollama")
        model_ids = {m.model_id for m in models}
        self.assertIn("m_chat", model_ids)
        self.assertIn("m_embed", model_ids)


class TestLLMServiceUnstartedGuard(unittest.IsolatedAsyncioTestCase):
    async def test_chat_raises_when_unstarted(self):
        cat, router = _make_catalog_and_router()
        mgr = MagicMock(spec=ProviderManager)

        # Use a real BaseProviderRuntime instance so isinstance() passes and
        # _check_started() raises as designed. The guard verifies _started
        # before any inference call is made.
        from unittest.mock import MagicMock as _MagicMock

        class _UnstartedAdapter(BaseProviderRuntime):
            def __init__(self):
                object.__setattr__(self, "_started", False)
                object.__setattr__(self, "_record", _MagicMock(provider_id="p_ollama"))

            @property
            def provider_id(self):
                return "p_ollama"

            @property
            def provider_type(self):
                return ProviderType.OLLAMA.value

            @property
            def capabilities(self):
                return frozenset({Capability.CHAT})

            async def chat(self, messages, options):
                pass  # unreachable — guard fires first

            def validate_configuration(self):
                pass

        adapter = _UnstartedAdapter()
        mgr.get_provider.return_value = adapter

        svc = LLMService(mgr, cat, router=router)
        with self.assertRaises(LLMConfigurationError) as ctx:
            await svc.chat([ChatMessage(role="user", content="hi")])
        self.assertIn("not been started", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
