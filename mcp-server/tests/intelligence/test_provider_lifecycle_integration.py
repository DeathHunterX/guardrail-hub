"""Provider lifecycle integration test — Phase 7.

Verifies the real lifecycle boundary::

    ProviderManager construction
        ↓
    provider_manager.start()
        ↓
    inference
        ↓
    provider_manager.stop()

Uses a real ProviderManager, LLMService, ConversationService, and an
in-memory conversation store. The HTTP layer is faked so no external
LLM API is contacted. Does NOT mock ProviderManager lifecycle itself.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timezone
from typing import AsyncIterator

# Inject fake httpx so adapters can start without a real network.
# Mirrors the pattern in test_integration_verification.py.

class _FakeAsyncClient:
    """Minimal fake httpx.AsyncClient — all methods are real so await works."""

    def __init__(self, **kwargs):
        self.base_url = kwargs.get("base_url", "")
        self.headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout")
        self._closed = False

    async def post(self, path, **kw):
        return _FakeResponse(200, {})

    async def aclose(self):
        self._closed = True

    def stream(self, method, path, **kw):
        return _FakeStreamContext([])


class _FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise Exception(f"HTTP {self.status_code}")


class _FakeStreamContext:
    def __init__(self, lines):
        self._lines = list(lines)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def __aiter__(self):
        for line in self._lines:
            yield line


_fake_httpx = type(sys)("httpx")
_fake_httpx.AsyncClient = _FakeAsyncClient
sys.modules["httpx"] = _fake_httpx  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_frozen_catalog():
    """Build a frozen catalog with one enabled chat provider."""
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

    cat = ModelCatalog()

    p = ProviderRecord(
        provider_id="test_provider",
        provider_type=ProviderType.OLLAMA,
        deployment=DeploymentType.SELF_HOSTED,
        auth=AuthConfig(),
        connection=ConnectionConfig(base_url="http://localhost:11434"),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=10,
    )
    m = ModelRecord(
        provider_id="test_provider",
        model_id="test-model",
        model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}),
        context_window=8192,
        priority=10,
    )

    cat.register_provider(p)
    cat.register_model(m)
    cat.freeze()
    return cat


class FakeStreamChatAdapter:
    """A started chat-only adapter that yields fake streaming chunks."""

    def __init__(self, record):
        self._record = record
        self._started = False
        self._started_called = False
        self._close_called = False

    @property
    def provider_id(self):
        return self._record.provider_id

    @property
    def provider_type(self):
        return "test_provider_type"

    @property
    def capabilities(self):
        from app.intelligence.registry.types.capability import Capability
        return frozenset({Capability.CHAT})

    def initialize(self):
        pass

    def validate_configuration(self):
        pass

    async def start(self):
        self._started = True
        self._started_called = True

    async def close(self):
        self._started = False
        self._close_called = True

    async def chat(self, messages, options):
        return _make_chat_response(options.model, "fake response content")

    async def chat_stream(self, messages, options) -> AsyncIterator[str]:
        for chunk in ["Hel", "lo ", "world"]:
            yield chunk


def _make_chat_response(model, content):
    from app.intelligence.ports.chat import ChatResponse
    return ChatResponse(
        content=content,
        model=model,
        finish_reason="stop",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestProviderLifecycleBoundary(unittest.IsolatedAsyncioTestCase):
    """Verify the lifecycle boundary: start → inference → stop."""

    async def test_provider_not_available_before_start(self):
        """ProviderManager.get_provider returns None before start()."""
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager

        cat = _make_frozen_catalog()
        factory = ProviderFactory()
        factory.register(
            "ollama",
            FakeStreamChatAdapter,
        )

        mgr = ProviderManager(factory=factory, catalog=cat)
        self.assertFalse(mgr.initialized)
        self.assertIsNone(mgr.get_provider("test_provider"))

    async def test_provider_available_after_start(self):
        """ProviderManager.get_provider returns instance after start()."""
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager

        cat = _make_frozen_catalog()
        factory = ProviderFactory()
        factory.register(
            "ollama",
            FakeStreamChatAdapter,
        )

        mgr = ProviderManager(factory=factory, catalog=cat)
        await mgr.start()

        try:
            prov = mgr.get_provider("test_provider")
            self.assertIsNotNone(prov)
            self.assertEqual(prov.provider_id, "test_provider")
            self.assertTrue(mgr.initialized)
        finally:
            await mgr.stop()

    async def test_provider_start_raises_when_catalog_not_frozen(self):
        """ProviderManager.start() raises when catalog is not frozen."""
        from app.intelligence.exceptions import LLMConfigurationError
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager
        from app.intelligence.registry.catalog.catalog import ModelCatalog

        cat = ModelCatalog()  # not frozen
        factory = ProviderFactory()

        mgr = ProviderManager(factory=factory, catalog=cat)
        with self.assertRaises(LLMConfigurationError):
            await mgr.start()

    async def test_sync_inference_raises_without_started_provider(self):
        """LLMService.chat() raises LLMProviderError when provider not started."""
        from app.intelligence.exceptions import LLMProviderError
        from app.intelligence.inference.services.llm_service import LLMService
        from app.intelligence.ports.chat import ChatMessage
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager

        cat = _make_frozen_catalog()
        factory = ProviderFactory()
        factory.register("ollama", FakeStreamChatAdapter)

        mgr = ProviderManager(factory=factory, catalog=cat)
        svc = LLMService(provider_manager=mgr, catalog=cat)

        # No provider started yet — must raise.
        with self.assertRaises(LLMProviderError):
            await svc.chat([ChatMessage(role="user", content="hello")])

    async def test_sync_inference_succeeds_with_started_provider(self):
        """LLMService.chat() succeeds after provider_manager.start()."""
        from app.intelligence.inference.services.llm_service import LLMService
        from app.intelligence.ports.chat import ChatMessage
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager

        cat = _make_frozen_catalog()
        factory = ProviderFactory()
        factory.register("ollama", FakeStreamChatAdapter)

        mgr = ProviderManager(factory=factory, catalog=cat)
        await mgr.start()

        try:
            svc = LLMService(provider_manager=mgr, catalog=cat)
            response = await svc.chat(
                [ChatMessage(role="user", content="hello")],
                model="test-model",
            )
            self.assertEqual(response.content, "fake response content")
            self.assertEqual(response.model, "test-model")
            self.assertEqual(response.finish_reason, "stop")
        finally:
            await mgr.stop()

    async def test_streaming_inference_succeeds_with_started_provider(self):
        """LLMService.chat_stream() yields chunks after provider_manager.start()."""
        from app.intelligence.inference.services.llm_service import LLMService
        from app.intelligence.ports.chat import ChatMessage
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager

        cat = _make_frozen_catalog()
        factory = ProviderFactory()
        factory.register("ollama", FakeStreamChatAdapter)

        mgr = ProviderManager(factory=factory, catalog=cat)
        await mgr.start()

        try:
            svc = LLMService(provider_manager=mgr, catalog=cat)
            stream = await svc.chat_stream(
                [ChatMessage(role="user", content="hello")],
                model="test-model",
            )
            chunks = [c async for c in stream]
            self.assertEqual(chunks, ["Hel", "lo ", "world"])
        finally:
            await mgr.stop()

    async def test_provider_resources_released_after_stop(self):
        """ProviderManager.stop() releases provider instances."""
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager

        cat = _make_frozen_catalog()
        factory = ProviderFactory()
        factory.register("ollama", FakeStreamChatAdapter)

        mgr = ProviderManager(factory=factory, catalog=cat)
        await mgr.start()

        prov = mgr.get_provider("test_provider")
        self.assertIsNotNone(prov)
        self.assertTrue(prov._close_called is False)

        await mgr.stop()

        # After stop, provider should no longer be retrievable.
        self.assertIsNone(mgr.get_provider("test_provider"))
        self.assertEqual(mgr.provider_count, 0)
        self.assertFalse(mgr.initialized)
        # close() was called on the adapter.
        self.assertTrue(prov._close_called)


class TestConversationServiceLifecycleIntegration(unittest.IsolatedAsyncioTestCase):
    """Verify ConversationService works with the real provider lifecycle."""

    async def test_conversation_turn_succeeds_with_started_provider(self):
        """handle_turn() succeeds after provider_manager.start()."""
        from app.intelligence.conversation.infrastructure.in_memory_store import (
            InMemoryConversationStore,
        )
        from app.intelligence.core.events.dispatcher import InProcessEventDispatcher
        from app.intelligence.inference.services.llm_service import LLMService
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager
        from app.services.conversation.conversation_service import ConversationService

        cat = _make_frozen_catalog()
        factory = ProviderFactory()
        factory.register("ollama", FakeStreamChatAdapter)

        mgr = ProviderManager(factory=factory, catalog=cat)
        await mgr.start()

        try:
            llm_svc = LLMService(provider_manager=mgr, catalog=cat)
            store = InMemoryConversationStore()
            pub = InProcessEventDispatcher()
            svc = ConversationService(
                store=store,
                llm_service=llm_svc,
                publisher=pub,
            )

            svc.create_conversation("conv-1")
            response = await svc.handle_turn(
                conversation_id="conv-1",
                user_content="hello",
            )

            self.assertEqual(response.content, "fake response content")
            self.assertEqual(len(svc.get_conversation("conv-1").messages), 2)
        finally:
            await mgr.stop()

    async def test_conversation_stream_succeeds_with_started_provider(self):
        """handle_turn_stream() succeeds after provider_manager.start()."""
        from app.intelligence.conversation.infrastructure.in_memory_store import (
            InMemoryConversationStore,
        )
        from app.intelligence.core.events.dispatcher import InProcessEventDispatcher
        from app.intelligence.inference.services.llm_service import LLMService
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager
        from app.services.conversation.conversation_service import ConversationService

        cat = _make_frozen_catalog()
        factory = ProviderFactory()
        factory.register("ollama", FakeStreamChatAdapter)

        mgr = ProviderManager(factory=factory, catalog=cat)
        await mgr.start()

        try:
            llm_svc = LLMService(provider_manager=mgr, catalog=cat)
            store = InMemoryConversationStore()
            pub = InProcessEventDispatcher()
            svc = ConversationService(
                store=store,
                llm_service=llm_svc,
                publisher=pub,
            )

            svc.create_conversation("conv-2")
            summary, resolved_model, stream = await svc.handle_turn_stream(
                conversation_id="conv-2",
                user_content="hello stream",
            )

            # Phase 7: verify the resolved model ID is propagated through the stream.
            self.assertEqual(resolved_model, "test-model")

            chunks = [c async for c in stream]
            self.assertEqual(chunks, ["Hel", "lo ", "world"])

            final_content = "".join(chunks)
            svc.finalise_stream(
                conversation_id="conv-2",
                prior_summary=summary,
                final_content=final_content,
                model=resolved_model,
            )

            conv = svc.get_conversation("conv-2")
            self.assertEqual(len(conv.messages), 2)
            self.assertEqual(conv.messages[1].content, "Hello world")
        finally:
            await mgr.stop()


class TestProviderManagerLifespan(unittest.IsolatedAsyncioTestCase):
    """Verify the context-manager lifespan helper."""

    async def test_lifespan_context_manager(self):
        """Async context manager starts and stops provider lifecycle."""
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager

        cat = _make_frozen_catalog()
        factory = ProviderFactory()
        factory.register("ollama", FakeStreamChatAdapter)

        mgr = ProviderManager(factory=factory, catalog=cat)

        async with mgr.lifespan() as running_mgr:
            prov = running_mgr.get_provider("test_provider")
            self.assertIsNotNone(prov)
            self.assertTrue(prov._started_called)

        # After context exit, provider is stopped.
        self.assertIsNone(mgr.get_provider("test_provider"))
        self.assertFalse(mgr.initialized)


if __name__ == "__main__":
    unittest.main()
