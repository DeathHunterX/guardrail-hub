"""Integration verification — Phase 4 Commit 5.

Verifies the complete inference pipeline end-to-end.
No test may call real cloud services. No new architecture.
"""

import asyncio
import base64
import json
import os
import re
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

# ── Inject fake boto3/botocore before any adapter import ──────────────────
class _FakeClientError(Exception):
    # botocore ClientError is constructed as: ClientError(error_response, operation_name)
    # error_response must be dict-shaped as {"Error": {"Code": "...", "Message": "..."}}
    def __init__(self, error_response=None, operation_name=""):
        if error_response is None:
            error_response = {}
        msg = error_response.get("Error", {}).get("Message", str(error_response))
        super().__init__(msg)
        self.response = error_response

class _FakeBotocoreExceptions:
    ClientError = _FakeClientError
    EndpointConnectionError = type("ECE", (Exception,), {})
    ConnectTimeoutError = type("CTE", (Exception,), {})
    ResponseStreamingError = type("RSE", (Exception,), {})
    DataNotFoundError = type("DNF", (Exception,), {})
    UnknownServiceError = type("USE", (Exception,), {})
    BotoCoreError = type("BCE", (Exception,), {})
    ReadTimeoutError = type("RTE", (Exception,), {})
    InternalError = type("IE", (Exception,), {})


class _FakeBotocoreModule:
    exceptions = _FakeBotocoreExceptions()
    ClientError = _FakeClientError
    EndpointConnectionError = _FakeBotocoreExceptions.EndpointConnectionError
    ConnectTimeoutError = _FakeBotocoreExceptions.ConnectTimeoutError
    ResponseStreamingError = _FakeBotocoreExceptions.ResponseStreamingError
    DataNotFoundError = _FakeBotocoreExceptions.DataNotFoundError
    UnknownServiceError = _FakeBotocoreExceptions.UnknownServiceError
    BotoCoreError = _FakeBotocoreExceptions.BotoCoreError
    ReadTimeoutError = _FakeBotocoreExceptions.ReadTimeoutError


# boto3.Session is a real class; its __init__ must accept **kwargs and
# .client() must return a synchronous mock so asyncio.to_thread works in tests.
class _FakeBoto3Session:
    def __init__(self, **kwargs):
        pass  # accept all keyword args (aws_access_key_id, region_name, ...)

    def client(self, name, **kw):
        return MagicMock()  # sync mock; invoke_model is called via asyncio.to_thread


class _FakeBoto3SessionConfig:
    def __init__(self, **kwargs): pass


_fake_boto3 = MagicMock()
_fake_boto3.Session = _FakeBoto3Session
_fake_boto3.botocore = _FakeBotocoreModule()
_fake_boto3.session = MagicMock()
_fake_boto3.session.Config = _FakeBoto3SessionConfig
sys.modules["boto3"] = _fake_boto3
sys.modules["botocore"] = _fake_boto3.botocore
sys.modules["botocore.exceptions"] = _fake_boto3.botocore.exceptions
sys.modules["boto3.session"] = _fake_boto3.session
sys.modules["boto3.session.Config"] = _fake_boto3.session.Config

# Keep a reference so adapters can import it directly for isinstance checks.
sys.modules["botocore"].exceptions = _fake_boto3.botocore.exceptions
sys.modules["botocore"].exceptions.ResponseStreamingError = \
    _fake_boto3.botocore.exceptions.ResponseStreamingError

# ── Fake httpx ─────────────────────────────────────────────────────────────
# ── Fake httpx AsyncClient — mirrors the real httpx.AsyncClient interface ──────
# Used so adapter.start() can construct a client without importing real httpx.
# The test fixtures inject their own _FakeAsyncOllamaClient / _FakeAsyncOpenAIClient
# into _client via object.__setattr__, which is preserved by the sticky start() guard.

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
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


_fake_httpx = MagicMock()
_fake_httpx.AsyncClient = _FakeAsyncClient
_fake_httpx.Timeout = type("Timeout", (object,), {"__init__": lambda self, *a, **k: None})
_fake_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
_fake_httpx.ConnectError = type("ConnectError", (Exception,), {})
_fake_httpx.PoolTimeout = type("PoolTimeout", (Exception,), {})
_fake_httpx.ProtocolError = type("ProtocolError", (Exception,), {})
_fake_httpx.HTTPStatusError = type("HTTPStatusError", (Exception,), {})
sys.modules["httpx"] = _fake_httpx

# Import the (now-faked) httpx module so tests can raise its exception types
# exactly as the real transport would (e.g. httpx.TimeoutException on timeout).
import httpx  # noqa: E402  (must follow the sys.modules injection above)

# ── Set env vars before adapter imports ────────────────────────────────────
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")

# ── Imports ────────────────────────────────────────────────────────────────
from app.intelligence.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMValidationError,
)
from app.intelligence.inference.services.llm_service import LLMService
from app.intelligence.ports.chat import ChatMessage, ChatOptions, ChatResponse
from app.intelligence.providers.adapters import (
    BedrockAdapter,
    OllamaAdapter,
    OpenAICompatibleAdapter,
    register_all_adapters,
)
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.providers.provider_manager import ProviderManager
from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.models.provider import AuthConfig, ConnectionConfig, ProviderRecord
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.model import ModelType
from app.intelligence.registry.types.provider import ProviderType


# ── Pre-started adapter helpers ─────────────────────────────────────────────

# ── Realistic async fake clients (support await aclose) ─────────────────────

class _FakeAsyncOllamaResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        pass  # no-op for 2xx responses


class _FakeAsyncOllamaClient:
    """Fake httpx.AsyncClient for Ollama adapter — supports await aclose()."""

    def __init__(self, **kwargs):
        self.base_url = kwargs.get("base_url", "")
        self.headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout")
        self._closed = False
        self._mock_post = None

    def set_mock_post(self, response):
        self._mock_post = response

    async def post(self, path, **kw):
        return self._mock_post or _FakeAsyncOllamaResponse(
            200,
            {"message": {"content": ""}, "done": True},
        )

    async def aclose(self):
        self._closed = True

    async def stream(self, method, path, **kw):
        return _FakeOllamaStreamContext([])


class _FakeOllamaStreamContext:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


def _make_started_ollama(record):
    adapter = OllamaAdapter(record)
    adapter.initialize()
    mc = _FakeAsyncOllamaClient()
    mc.set_mock_post(_FakeAsyncOllamaResponse(
        200,
        {"message": {"content": "hello from ollama"}, "done": True},
    ))
    object.__setattr__(adapter, "_client", mc)
    object.__setattr__(adapter, "_started", True)
    return adapter

class _FakeAsyncOpenAIResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


class _FakeAsyncOpenAIClient:
    """Fake httpx.AsyncClient for OpenAI-compatible adapter — supports await aclose()."""

    def __init__(self, **kwargs):
        self.base_url = kwargs.get("base_url", "")
        self.headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout")
        self._closed = False
        self._mock_post = None

    def set_mock_post(self, response):
        self._mock_post = response

    async def post(self, path, **kw):
        return self._mock_post or _FakeAsyncOpenAIResponse(
            200,
            {"choices": [], "model": ""},
        )

    async def aclose(self):
        self._closed = True

    def stream(self, method, path, **kw):
        return _FakeOpenAIStreamContext([])


class _FakeOpenAIStreamContext:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


def _make_started_openai(record):
    adapter = OpenAICompatibleAdapter(record)
    adapter.initialize()
    mc = _FakeAsyncOpenAIClient()
    mc.set_mock_post(_FakeAsyncOpenAIResponse(
        200,
        {
            "choices": [{"message": {"content": "hello from openai"}, "finish_reason": "stop"}],
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        },
    ))
    object.__setattr__(adapter, "_client", mc)
    object.__setattr__(adapter, "_started", True)
    return adapter

def _make_started_bedrock(record):
    adapter = BedrockAdapter(record)
    adapter.initialize()

    # mock_body.read() must return real bytes for json.loads().
    mock_body = MagicMock()
    mock_body.read = MagicMock(
        return_value=b'{"content":[{"type":"text","text":"hello from bedrock"}],'
                     b'"usage":{"input_tokens":5,"output_tokens":3},"stop_reason":"end_turn"}'
    )

    # Create the mock client explicitly so we control its return values.
    mock_client = MagicMock()
    mock_client.invoke_model = MagicMock(return_value={"body": mock_body})
    mock_client.invoke_model_with_response_stream = MagicMock(return_value={"body": []})

    object.__setattr__(adapter, "_client", mock_client)
    object.__setattr__(adapter, "_started", True)
    return adapter


# ── MockFactory — injects pre-started adapters ─────────────────────────────────

class _MockFactory(ProviderFactory):
    """Subclass that substitutes pre-started adapter constructors.

    Overrides :meth:`create` to return a caller-supplied pre-started adapter
    instead of calling the real constructor. Falls back to the real factory
    for provider types not in the ctor map.
    """

    def __init__(self, ctor_map):
        super().__init__()
        self._ctor_map = ctor_map

    def create(self, record, **kwargs):
        ctor = self._ctor_map.get(record.provider_type.value)
        if ctor:
            return ctor(record, **kwargs)
        return super().create(record, **kwargs)


# ── Catalog fixture ───────────────────────────────────────────────────────

def _make_catalog():
    cat = ModelCatalog()
    cat.register_provider(ProviderRecord(
        provider_id="ollama-local", provider_type=ProviderType.OLLAMA,
        deployment=DeploymentType.SELF_HOSTED, auth=AuthConfig(),
        connection=ConnectionConfig(base_url="http://localhost:11434"),
        capabilities=frozenset({Capability.CHAT, Capability.EMBEDDING}),
        enabled=True, priority=1,
    ))
    cat.register_model(ModelRecord(
        model_id="llama3.1:8b", provider_id="ollama-local",
        model_type=ModelType.CHAT, capabilities=frozenset({Capability.CHAT, Capability.EMBEDDING}),
    ))

    cat.register_provider(ProviderRecord(
        provider_id="openai-cloud", provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD, auth=AuthConfig(api_key="test-key"),
        connection=ConnectionConfig(base_url="https://api.openai.com"),
        capabilities=frozenset({Capability.CHAT, Capability.EMBEDDING}),
        enabled=True, priority=2,
    ))
    cat.register_model(ModelRecord(
        model_id="gpt-4o-mini", provider_id="openai-cloud",
        model_type=ModelType.CHAT, capabilities=frozenset({Capability.CHAT}),
    ))

    cat.register_provider(ProviderRecord(
        provider_id="bedrock-cloud", provider_type=ProviderType.BEDROCK,
        deployment=DeploymentType.CLOUD, auth=AuthConfig(),
        connection=ConnectionConfig(base_url=""),
        capabilities=frozenset({Capability.CHAT, Capability.EMBEDDING}),
        enabled=True, priority=3,
    ))
    cat.register_model(ModelRecord(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        provider_id="bedrock-cloud",
        model_type=ModelType.CHAT, capabilities=frozenset({Capability.CHAT}),
    ))
    cat.register_model(ModelRecord(
        model_id="amazon.titan-embed-text-v2:0",
        provider_id="bedrock-cloud",
        model_type=ModelType.EMBEDDING, capabilities=frozenset({Capability.EMBEDDING}),
    ))
    cat.freeze()
    return cat


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 1 — End-to-End Request Flow
# ═══════════════════════════════════════════════════════════════════════════

class _FakeModuleIsolationMixin:
    """Re-pin this module's fake boto3/botocore/httpx for the duration of a test.

    The Bedrock adapter resolves ``botocore.exceptions`` at call time via
    ``import botocore.exceptions as botocore`` and then runs ``isinstance``
    checks against those classes. When the whole ``tests/intelligence`` package
    is discovered in one process, sibling test modules also install their own
    fake ``botocore`` into ``sys.modules`` at import time. Whichever module was
    imported last wins the shared slot, so an exception constructed from *this*
    module's fake classes would be tested against *another* module's fake
    classes — a different object identity — and every ``isinstance`` check would
    miss, collapsing to a generic error.

    This mixin makes the module hermetic: each test restores this module's fakes
    before running and puts back whatever was there afterwards, so results no
    longer depend on test discovery order. It changes no production behaviour.
    """

    _ISOLATED_MODULES = (
        "httpx",
        "boto3",
        "boto3.session",
        "boto3.session.Config",
        "botocore",
        "botocore.exceptions",
    )

    # Environment the pipeline needs to initialize every adapter. Re-asserted per
    # test because sibling test modules pop these vars in their own tearDown; our
    # module-level setdefault() only runs once at import and would not restore them.
    _REQUIRED_ENV = {
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OPENAI_API_KEY": "test-key",
        "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "test-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret",
    }

    def setUp(self):
        super().setUp()
        self._saved_modules = {
            name: sys.modules.get(name) for name in self._ISOLATED_MODULES
        }
        sys.modules["httpx"] = _fake_httpx
        sys.modules["boto3"] = _fake_boto3
        sys.modules["boto3.session"] = _fake_boto3.session
        sys.modules["boto3.session.Config"] = _fake_boto3.session.Config
        sys.modules["botocore"] = _fake_boto3.botocore
        sys.modules["botocore.exceptions"] = _fake_boto3.botocore.exceptions

        # The httpx adapters bind `httpx` with a module-level import, so their
        # reference is frozen at first import. If a sibling test module imported
        # them first (installing its own fake httpx), their `httpx.TimeoutException`
        # etc. are different class objects than the ones this module raises, and
        # the adapters' isinstance() checks would miss. Rebind the already-imported
        # adapter modules' httpx global to this module's fake for the test's
        # duration (restored in tearDown) — the same swap mock.patch.object makes.
        from app.intelligence.providers.adapters import ollama as _ollama_mod
        from app.intelligence.providers.adapters import (
            openai_compatible as _openai_mod,
        )
        self._httpx_bound_modules = (_ollama_mod, _openai_mod)
        self._saved_httpx = {
            mod: getattr(mod, "httpx", None) for mod in self._httpx_bound_modules
        }
        for mod in self._httpx_bound_modules:
            mod.httpx = _fake_httpx

        self._saved_env = {
            name: os.environ.get(name) for name in self._REQUIRED_ENV
        }
        for name, value in self._REQUIRED_ENV.items():
            os.environ[name] = value

    def tearDown(self):
        for name, value in self._saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        for mod, prior in self._saved_httpx.items():
            if prior is not None:
                mod.httpx = prior
        for name, mod in self._saved_modules.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
        super().tearDown()


class TestEndToEndFlow(_FakeModuleIsolationMixin, unittest.IsolatedAsyncioTestCase):

    async def test_ollama_full_chain(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(
                messages=[ChatMessage(role="user", content="hi")],
                provider="ollama-local",
            )
            self.assertEqual(resp.content, "hello from ollama")
        finally:
            await manager.stop()

    async def test_openai_full_chain(self):
        catalog = _make_catalog()
        factory = _MockFactory({"openai_compatible": _make_started_openai})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(
                messages=[ChatMessage(role="user", content="hi")],
                provider="openai-cloud",
            )
            self.assertEqual(resp.content, "hello from openai")
            self.assertEqual(resp.model, "gpt-4o-mini")
            self.assertIsNotNone(resp.usage)
        finally:
            await manager.stop()

    async def test_bedrock_full_chain(self):
        catalog = _make_catalog()
        factory = _MockFactory({"bedrock": _make_started_bedrock})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(
                messages=[ChatMessage(role="user", content="hi")],
                provider="bedrock-cloud",
            )
            self.assertEqual(resp.content, "hello from bedrock")
            self.assertIsNotNone(resp.usage)
        finally:
            await manager.stop()

    async def test_capability_only_routes_to_highest_priority(self):
        catalog = _make_catalog()
        factory = _MockFactory({
            "ollama": _make_started_ollama,
            "openai_compatible": _make_started_openai,
        })
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(messages=[ChatMessage(role="user", content="hi")])
            # Self-hosted (priority=1) beats cloud (priority=2,3).
            self.assertEqual(resp.content, "hello from ollama")
        finally:
            await manager.stop()


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 2 — Provider Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

class TestProviderLifecycle(_FakeModuleIsolationMixin, unittest.IsolatedAsyncioTestCase):

    async def test_ollama_lifecycle(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            adapter = manager.get_provider("ollama-local")
            self.assertIsNotNone(adapter)
            self.assertTrue(adapter.is_started)
            adapter._client.post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: {"message": {"content": "ok"}, "done": True},
                raise_for_status=MagicMock(),
            ))
            resp = await adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="llama3.1:8b"),
            )
            self.assertEqual(resp.content, "ok")
        finally:
            await manager.stop()
            self.assertFalse(adapter.is_started)

    async def test_openai_lifecycle(self):
        catalog = _make_catalog()
        factory = _MockFactory({"openai_compatible": _make_started_openai})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            adapter = manager.get_provider("openai-cloud")
            self.assertTrue(adapter.is_started)
            adapter._client.post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: {
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "model": "gpt-4o-mini",
                },
                raise_for_status=MagicMock(),
            ))
            resp = await adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="gpt-4o-mini"),
            )
            self.assertEqual(resp.content, "ok")
        finally:
            await manager.stop()
            self.assertFalse(adapter.is_started)

    async def test_bedrock_lifecycle(self):
        catalog = _make_catalog()
        factory = _MockFactory({"bedrock": _make_started_bedrock})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            adapter = manager.get_provider("bedrock-cloud")
            self.assertTrue(adapter.is_started)
            mock_body = MagicMock()
            mock_body.read = MagicMock(return_value=b'{"content":[{"type":"text","text":"ok"}],"usage":{"input_tokens":1,"output_tokens":1},"stop_reason":"end_turn"}')
            adapter._client.invoke_model = MagicMock(return_value={"body": mock_body})
            resp = await adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="anthropic.claude-3-haiku-20240307-v1:0"),
            )
            self.assertEqual(resp.content, "ok")
        finally:
            await manager.stop()
            self.assertFalse(adapter.is_started)

    async def test_start_idempotent(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        first = manager.get_provider("ollama-local")
        await manager.start()
        second = manager.get_provider("ollama-local")
        self.assertIs(first, second)
        await manager.stop()

    async def test_stop_clears_providers(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        self.assertGreater(manager.provider_count, 0)
        await manager.stop()
        self.assertEqual(manager.provider_count, 0)

    async def test_lifespan_context_manager(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        async with manager.lifespan() as mgr:
            self.assertTrue(mgr.initialized)
            self.assertIsNotNone(mgr.get_provider("ollama-local"))
        self.assertFalse(manager.initialized)

    async def test_inference_blocked_before_start(self):
        catalog = _make_catalog()
        factory = _MockFactory({})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        llm = LLMService(manager, catalog)
        with self.assertRaises(LLMProviderError):
            await llm.chat(messages=[ChatMessage(role="user", content="hi")])


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 3 — Routing
# ═══════════════════════════════════════════════════════════════════════════

class TestRoutingScenarios(_FakeModuleIsolationMixin, unittest.IsolatedAsyncioTestCase):

    async def test_explicit_model(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(
                messages=[ChatMessage(role="user", content="hi")],
                model="llama3.1:8b",
            )
            self.assertEqual(resp.content, "hello from ollama")
        finally:
            await manager.stop()

    async def test_explicit_provider(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(
                messages=[ChatMessage(role="user", content="hi")],
                provider="ollama-local",
            )
            self.assertEqual(resp.content, "hello from ollama")
        finally:
            await manager.stop()

    async def test_explicit_provider_and_model_agree(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(
                messages=[ChatMessage(role="user", content="hi")],
                model="llama3.1:8b",
                provider="ollama-local",
            )
            self.assertEqual(resp.content, "hello from ollama")
        finally:
            await manager.stop()

    async def test_wrong_capability_raises(self):
        catalog = _make_catalog()
        factory = _MockFactory({})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            with self.assertRaises(LLMModelNotFoundError):
                await llm.chat(
                    messages=[ChatMessage(role="user", content="hi")],
                    model="amazon.titan-embed-text-v2:0",
                )
        finally:
            await manager.stop()

    async def test_disabled_provider_skipped(self):
        # Disable ollama-local and bedrock-cloud so only openai-cloud is a candidate.
        # Without this, the router may pick bedrock-cloud (lexicographically earlier
        # than openai-cloud among CLOUD providers) even though it has no factory entry.
        catalog = _make_catalog()
        catalog._frozen = False

        rec_ollama = catalog.get_provider("ollama-local")
        catalog.register_provider(ProviderRecord(
            provider_id="ollama-local", provider_type=rec_ollama.provider_type,
            deployment=rec_ollama.deployment, auth=rec_ollama.auth,
            connection=rec_ollama.connection,
            capabilities=rec_ollama.capabilities, enabled=False,
            priority=rec_ollama.priority,
        ))

        rec_bedrock = catalog.get_provider("bedrock-cloud")
        catalog.register_provider(ProviderRecord(
            provider_id="bedrock-cloud", provider_type=rec_bedrock.provider_type,
            deployment=rec_bedrock.deployment, auth=rec_bedrock.auth,
            connection=rec_bedrock.connection,
            capabilities=rec_bedrock.capabilities, enabled=False,
            priority=rec_bedrock.priority,
        ))

        catalog.freeze()

        factory = _MockFactory({"openai_compatible": _make_started_openai})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(messages=[ChatMessage(role="user", content="hi")])
            self.assertEqual(resp.content, "hello from openai")
        finally:
            await manager.stop()

    async def test_no_candidates_raises(self):
        empty_cat = ModelCatalog()
        empty_cat.register_provider(ProviderRecord(
            provider_id="broken", provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED, auth=AuthConfig(),
            connection=ConnectionConfig(base_url="http://localhost:1"),
            capabilities=frozenset(), enabled=True, priority=1,
        ))
        empty_cat.register_model(ModelRecord(
            model_id="empty", provider_id="broken",
            model_type=ModelType.CHAT, capabilities=frozenset(),
        ))
        empty_cat.freeze()

        factory = _MockFactory({})
        register_all_adapters(factory)
        manager = ProviderManager(factory, empty_cat)
        await manager.start()
        try:
            llm = LLMService(manager, empty_cat)
            with self.assertRaises(LLMModelNotFoundError):
                await llm.chat(messages=[ChatMessage(role="user", content="hi")])
        finally:
            await manager.stop()

    async def test_deployment_preference_order(self):
        catalog = _make_catalog()
        factory = _MockFactory({
            "ollama": _make_started_ollama,
            "openai_compatible": _make_started_openai,
        })
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(messages=[ChatMessage(role="user", content="hi")])
            self.assertEqual(resp.content, "hello from ollama")
        finally:
            await manager.stop()

    async def test_model_priority_tiebreak(self):
        twin_cat = ModelCatalog()
        twin_cat.register_provider(ProviderRecord(
            provider_id="p1", provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED, auth=AuthConfig(),
            connection=ConnectionConfig(base_url="http://localhost:1"),
            capabilities=frozenset({Capability.CHAT}), enabled=True, priority=1,
        ))
        twin_cat.register_provider(ProviderRecord(
            provider_id="p2", provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED, auth=AuthConfig(),
            connection=ConnectionConfig(base_url="http://localhost:2"),
            capabilities=frozenset({Capability.CHAT}), enabled=True, priority=1,
        ))
        twin_cat.register_model(ModelRecord(
            model_id="model-a", provider_id="p1", model_type=ModelType.CHAT,
            capabilities=frozenset({Capability.CHAT}), priority=5,
        ))
        twin_cat.register_model(ModelRecord(
            model_id="model-b", provider_id="p2", model_type=ModelType.CHAT,
            capabilities=frozenset({Capability.CHAT}), priority=3,
        ))
        twin_cat.freeze()

        def make_p1(record):
            adapter = OllamaAdapter(record)
            adapter.initialize()
            mc = MagicMock()
            mc.post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: {"message": {"content": record.provider_id}, "done": True},
                raise_for_status=MagicMock(),
            ))
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        factory = _MockFactory({"ollama": make_p1})
        register_all_adapters(factory)
        manager = ProviderManager(factory, twin_cat)
        await manager.start()
        try:
            llm = LLMService(manager, twin_cat)
            resp = await llm.chat(messages=[ChatMessage(role="user", content="hi")])
            # model-b (priority=3) beats model-a (priority=5).
            self.assertEqual(resp.content, "p2")
        finally:
            await manager.stop()

    async def test_deterministic_no_randomness(self):
        catalog = _make_catalog()
        factory = _MockFactory({
            "ollama": _make_started_ollama,
            "openai_compatible": _make_started_openai,
        })
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp1 = await llm.chat(messages=[ChatMessage(role="user", content="hi")])
            resp2 = await llm.chat(messages=[ChatMessage(role="user", content="hi")])
            self.assertEqual(resp1.content, resp2.content)
        finally:
            await manager.stop()


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 4 — LLMService Verification
# ═══════════════════════════════════════════════════════════════════════════

class TestLLMServiceVerification(_FakeModuleIsolationMixin, unittest.IsolatedAsyncioTestCase):

    async def test_chat_calls_router_once(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            original = llm._router.route
            count = [0]
            def counting(*a, **kw):
                count[0] += 1
                return original(*a, **kw)
            llm._router.route = counting
            await llm.chat(messages=[ChatMessage(role="user", content="hi")])
            self.assertEqual(count[0], 1)
        finally:
            await manager.stop()

    async def test_chat_returns_chatresponse_not_adapter(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.chat(
                messages=[ChatMessage(role="user", content="hi")],
                provider="ollama-local",
            )
            self.assertIsInstance(resp, ChatResponse)
            self.assertEqual(resp.content, "hello from ollama")
        finally:
            await manager.stop()

    async def test_embed_routes_to_embedding_capable(self):
        def make_embed(record):
            adapter = OllamaAdapter(record)
            adapter.initialize()
            mc = MagicMock()
            mc.post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: {"embedding": [0.1, 0.2], "num_tokens": 3},
                raise_for_status=MagicMock(),
            ))
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        catalog = _make_catalog()
        factory = _MockFactory({"ollama": make_embed})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            resp = await llm.embed(texts=["hello world"], model="llama3.1:8b")
            self.assertEqual(resp.embeddings[0], [0.1, 0.2])
        finally:
            await manager.stop()


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 5 — ProviderFactory Verification
# ═══════════════════════════════════════════════════════════════════════════

class TestProviderFactoryVerification(unittest.TestCase):

    def test_ollama_factory(self):
        factory = ProviderFactory()
        register_all_adapters(factory)
        self.assertIn("ollama", factory.registered_types)
        caps = factory.get_capabilities("ollama")
        self.assertIn(Capability.CHAT, caps)
        self.assertIn(Capability.EMBEDDING, caps)
        record = ProviderRecord(
            provider_id="test-ollama", provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED, auth=AuthConfig(),
            connection=ConnectionConfig(base_url="http://localhost:11434"),
            capabilities=frozenset(), enabled=True, priority=1,
        )
        adapter = factory.create(record)
        self.assertIsInstance(adapter, OllamaAdapter)
        self.assertEqual(adapter.provider_id, "test-ollama")
        self.assertEqual(adapter.provider_type, "ollama")
        self.assertIn(Capability.CHAT, adapter.capabilities)
        self.assertIn(Capability.EMBEDDING, adapter.capabilities)

    def test_openai_factory(self):
        factory = ProviderFactory()
        register_all_adapters(factory)
        self.assertIn("openai_compatible", factory.registered_types)
        caps = factory.get_capabilities("openai_compatible")
        self.assertIn(Capability.CHAT, caps)
        self.assertIn(Capability.EMBEDDING, caps)
        record = ProviderRecord(
            provider_id="test-openai", provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD, auth=AuthConfig(api_key="k"),
            connection=ConnectionConfig(base_url="https://api.example.com"),
            capabilities=frozenset(), enabled=True, priority=1,
        )
        adapter = factory.create(record)
        self.assertIsInstance(adapter, OpenAICompatibleAdapter)
        self.assertEqual(adapter.provider_id, "test-openai")
        self.assertIn(Capability.CHAT, adapter.capabilities)
        self.assertIn(Capability.EMBEDDING, adapter.capabilities)

    def test_bedrock_factory(self):
        factory = ProviderFactory()
        register_all_adapters(factory)
        self.assertIn("bedrock", factory.registered_types)
        caps = factory.get_capabilities("bedrock")
        self.assertIn(Capability.CHAT, caps)
        self.assertIn(Capability.EMBEDDING, caps)
        record = ProviderRecord(
            provider_id="test-bedrock", provider_type=ProviderType.BEDROCK,
            deployment=DeploymentType.CLOUD, auth=AuthConfig(),
            connection=ConnectionConfig(base_url=""),
            capabilities=frozenset(), enabled=True, priority=1,
        )
        adapter = factory.create(record)
        self.assertIsInstance(adapter, BedrockAdapter)
        self.assertEqual(adapter.provider_id, "test-bedrock")
        self.assertEqual(adapter.provider_type, "bedrock")
        self.assertIn(Capability.CHAT, adapter.capabilities)
        self.assertIn(Capability.EMBEDDING, adapter.capabilities)

    def test_unregistered_type_raises(self):
        factory = ProviderFactory()
        with self.assertRaises(LLMConfigurationError):
            factory.create(ProviderRecord(
                provider_id="x", provider_type=ProviderType.OLLAMA,
                deployment=DeploymentType.SELF_HOSTED, auth=AuthConfig(),
                connection=ConnectionConfig(base_url=""),
                capabilities=frozenset(), enabled=True, priority=1,
            ))

    def test_find_by_capability(self):
        factory = ProviderFactory()
        register_all_adapters(factory)
        chat = factory.find_by_capability(Capability.CHAT)
        self.assertIn("ollama", chat)
        self.assertIn("openai_compatible", chat)
        self.assertIn("bedrock", chat)


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 6 — RegistryRuntime / Catalog Verification
# ═══════════════════════════════════════════════════════════════════════════

class TestCatalogVerification(unittest.TestCase):

    def test_secondary_indices_match_primary(self):
        catalog = _make_catalog()
        for cap in Capability:
            for m in catalog.find_models_by_capability(cap):
                self.assertIsNotNone(catalog.get_model(m.model_id))
        for pid in {p.provider_id for p in catalog.iter_providers()}:
            for m in catalog.models_by_provider(pid):
                self.assertEqual(catalog.get_model(m.model_id).model_id, m.model_id)

    def test_frozen_prevents_mutation(self):
        catalog = _make_catalog()
        self.assertTrue(catalog.frozen)
        with self.assertRaises(RuntimeError):
            catalog.register_model(ModelRecord(
                model_id="new", provider_id="ollama-local",
                model_type=ModelType.CHAT, capabilities=frozenset({Capability.CHAT}),
            ))


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 7 — Exception Propagation
# ═══════════════════════════════════════════════════════════════════════════

class TestExceptionPropagation(_FakeModuleIsolationMixin, unittest.IsolatedAsyncioTestCase):

    async def test_ollama_timeout(self):
        def make_timeout(record):
            adapter = OllamaAdapter(record)
            adapter.initialize()
            mc = MagicMock()
            mc.post = AsyncMock(side_effect=httpx.TimeoutException("simulated read timeout"))
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        catalog = _make_catalog()
        factory = _MockFactory({"ollama": make_timeout})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            with self.assertRaises(LLMTimeoutError):
                await llm.chat(messages=[ChatMessage(role="user", content="hi")], provider="ollama-local")
        finally:
            await manager.stop()

    async def test_openai_validation_422(self):
        def make_val(record):
            adapter = OpenAICompatibleAdapter(record)
            adapter.initialize()
            mc = MagicMock()
            resp = MagicMock(status_code=422)
            # Real httpx raises HTTPStatusError (carrying .response.status_code)
            # from raise_for_status(); the adapter maps 422 -> LLMValidationError.
            status_err = httpx.HTTPStatusError("HTTP 422 Unprocessable Entity")
            status_err.response = resp
            resp.raise_for_status = MagicMock(side_effect=status_err)
            mc.post = AsyncMock(return_value=resp)
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        catalog = _make_catalog()
        factory = _MockFactory({"openai_compatible": make_val})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            with self.assertRaises(LLMValidationError):
                await llm.chat(messages=[ChatMessage(role="user", content="hi")], provider="openai-cloud")
        finally:
            await manager.stop()

    async def test_bedrock_expired_token(self):
        def make_auth(record):
            adapter = BedrockAdapter(record)
            adapter.initialize()
            mc = MagicMock()
            mc.invoke_model = MagicMock(side_effect=_FakeClientError(
                {"Error": {"Code": "ExpiredTokenException", "Message": "expired"}},
                "InvokeModel",
            ))
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        catalog = _make_catalog()
        factory = _MockFactory({"bedrock": make_auth})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            with self.assertRaises(LLMAuthenticationError):
                await llm.chat(messages=[ChatMessage(role="user", content="hi")], provider="bedrock-cloud")
        finally:
            await manager.stop()

    async def test_bedrock_endpoint_connection(self):
        def make_unavail(record):
            adapter = BedrockAdapter(record)
            adapter.initialize()
            mc = MagicMock()
            mc.invoke_model = MagicMock(
                side_effect=_FakeBotocoreExceptions.EndpointConnectionError()
            )
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        catalog = _make_catalog()
        factory = _MockFactory({"bedrock": make_unavail})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            with self.assertRaises(LLMUnavailableError):
                await llm.chat(messages=[ChatMessage(role="user", content="hi")], provider="bedrock-cloud")
        finally:
            await manager.stop()

    async def test_bedrock_timeout(self):
        def make_timeout(record):
            adapter = BedrockAdapter(record)
            adapter.initialize()
            mc = MagicMock()
            mc.invoke_model = MagicMock(
                side_effect=_FakeBotocoreExceptions.ConnectTimeoutError()
            )
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        catalog = _make_catalog()
        factory = _MockFactory({"bedrock": make_timeout})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            with self.assertRaises(LLMTimeoutError):
                await llm.chat(messages=[ChatMessage(role="user", content="hi")], provider="bedrock-cloud")
        finally:
            await manager.stop()


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 8 — Streaming Verification
# ═══════════════════════════════════════════════════════════════════════════

class TestStreamingVerification(_FakeModuleIsolationMixin, unittest.IsolatedAsyncioTestCase):

    async def test_ollama_stream_is_lazy(self):
        def make_stream_ollama(record):
            adapter = OllamaAdapter(record)
            adapter.initialize()
            mc = MagicMock()

            # httpx's AsyncClient.stream() is a synchronous method that returns an
            # async context manager (used as `async with client.stream(...)`). The
            # mock must therefore be a sync def returning the async CM, not a
            # coroutine — otherwise `async with` receives a coroutine and fails.
            def mock_stream(*a, **kw):
                ctx = MagicMock()
                ctx.__aenter__ = AsyncMock(return_value=ctx)
                ctx.__aexit__ = AsyncMock(return_value=None)
                async def aiter_lines():
                    yield '{"message":{"content":"hel"}}'
                    yield '{"message":{"content":"lo"}}'
                    yield "[DONE]"
                ctx.aiter_lines = aiter_lines
                ctx.raise_for_status = MagicMock()
                return ctx

            mc.stream = mock_stream
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        catalog = _make_catalog()
        factory = _MockFactory({"ollama": make_stream_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            chunks = []
            stream = await llm.chat_stream(
                messages=[ChatMessage(role="user", content="hi")],
                provider="ollama-local",
            )
            async for chunk in stream:
                chunks.append(chunk)
            self.assertEqual(chunks, ["hel", "lo"])
        finally:
            await manager.stop()

    async def test_stream_returns_async_iterator(self):
        catalog = _make_catalog()
        factory = _MockFactory({"ollama": _make_started_ollama})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            # chat_stream() is async def; must await to get the AsyncIterator.
            result = await llm.chat_stream(
                messages=[ChatMessage(role="user", content="hi")],
                provider="ollama-local",
            )
            self.assertTrue(hasattr(result, "__anext__"))
        finally:
            await manager.stop()

    async def test_openai_stream_yields_deltas(self):
        def make_stream_openai(record):
            adapter = OpenAICompatibleAdapter(record)
            adapter.initialize()
            mc = MagicMock()

            # httpx's AsyncClient.stream() is synchronous and returns an async
            # context manager, so the mock is a sync def returning the async CM.
            # The OpenAI SSE protocol frames each event as `data: <json>` and
            # terminates with `data: [DONE]`; the adapter skips any line that does
            # not start with `data: `, so the mock must emit that exact framing.
            def mock_stream(*a, **kw):
                ctx = MagicMock()
                ctx.__aenter__ = AsyncMock(return_value=ctx)
                ctx.__aexit__ = AsyncMock(return_value=None)
                async def aiter_lines():
                    yield 'data: {"choices":[{"delta":{"content":"hi"}}]}'
                    yield 'data: {"choices":[{"delta":{"content":"!"}}]}'
                    yield "data: [DONE]"
                ctx.aiter_lines = aiter_lines
                ctx.raise_for_status = MagicMock()
                return ctx

            mc.stream = mock_stream
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        catalog = _make_catalog()
        factory = _MockFactory({"openai_compatible": make_stream_openai})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            chunks = []
            stream = await llm.chat_stream(
                messages=[ChatMessage(role="user", content="hi")],
                provider="openai-cloud",
            )
            async for chunk in stream:
                chunks.append(chunk)
            self.assertEqual(chunks, ["hi", "!"])
        finally:
            await manager.stop()

    async def test_bedrock_stream_yields_deltas(self):
        def make_stream_bedrock(record):
            adapter = BedrockAdapter(record)
            adapter.initialize()

            # BedrockAdapter.chat_stream does: event_stream = response["body"]
            # so response["body"] must be an iterable list of events.
            events = [
                {"bytes": base64.b64encode(json.dumps({"type": "content_block_delta", "delta": {"text": "he"}}).encode()).decode()},
                {"bytes": base64.b64encode(json.dumps({"type": "content_block_delta", "delta": {"text": "llo"}}).encode()).decode()},
            ]
            # Make invoke_model_with_response_stream return a dict-like object
            # whose ["body"] key yields the events iterable.
            mc = MagicMock()
            mc.invoke_model_with_response_stream = MagicMock(
                return_value={"body": events}
            )
            object.__setattr__(adapter, "_client", mc)
            object.__setattr__(adapter, "_started", True)
            return adapter

        catalog = _make_catalog()
        factory = _MockFactory({"bedrock": make_stream_bedrock})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        await manager.start()
        try:
            llm = LLMService(manager, catalog)
            chunks = []
            stream = await llm.chat_stream(
                messages=[ChatMessage(role="user", content="hi")],
                provider="bedrock-cloud",
            )
            async for chunk in stream:
                chunks.append(chunk)
            self.assertEqual(chunks, ["he", "llo"])
        finally:
            await manager.stop()


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 9 — Architecture Verification
# ═══════════════════════════════════════════════════════════════════════════

class TestArchitectureVerification(unittest.TestCase):

    def test_no_circular_imports(self):
        from app.intelligence.exceptions import LLMError
        from app.intelligence.ports.chat import ChatCapable
        from app.intelligence.ports.embedding import EmbeddingCapable
        from app.intelligence.providers.base_provider import BaseProviderRuntime
        from app.intelligence.registry.types.capability import Capability
        from app.intelligence.registry.types.deployment import DeploymentType
        from app.intelligence.inference.services.llm_service import LLMService
        from app.intelligence.inference.router.router import Router
        from app.intelligence.inference.strategies.priority import PriorityStrategy
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.provider_manager import ProviderManager
        from app.intelligence.registry.catalog.catalog import ModelCatalog
        from app.intelligence.providers.adapters import (
            BedrockAdapter, OllamaAdapter, OpenAICompatibleAdapter,
        )
        self.assertTrue(True)

    def test_factory_owns_construction(self):
        factory = ProviderFactory()
        register_all_adapters(factory)
        record = ProviderRecord(
            provider_id="x", provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED, auth=AuthConfig(),
            connection=ConnectionConfig(base_url="http://localhost:1"),
            capabilities=frozenset(), enabled=True, priority=1,
        )
        adapter = factory.create(record)
        self.assertIsInstance(adapter, OllamaAdapter)

    def test_llm_service_never_holds_factory_or_adapter_constructor(self):
        catalog = _make_catalog()
        factory = _MockFactory({})
        register_all_adapters(factory)
        manager = ProviderManager(factory, catalog)
        llm = LLMService(manager, catalog)
        self.assertNotIn("_factory", dir(llm))
        self.assertNotIn("_registrations", dir(llm))

    def test_adapter_transport_not_shared(self):
        factory = ProviderFactory()
        register_all_adapters(factory)
        ollama = factory.create(ProviderRecord(
            provider_id="x", provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED, auth=AuthConfig(),
            connection=ConnectionConfig(base_url="http://localhost:1"),
            capabilities=frozenset(), enabled=True, priority=1,
        ))
        bedrock = factory.create(ProviderRecord(
            provider_id="y", provider_type=ProviderType.BEDROCK,
            deployment=DeploymentType.CLOUD, auth=AuthConfig(),
            connection=ConnectionConfig(base_url=""),
            capabilities=frozenset(), enabled=True, priority=1,
        ))
        self.assertNotEqual(type(ollama).__name__, type(bedrock).__name__)


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIVE 10 — Dead Code Audit
# ═══════════════════════════════════════════════════════════════════════════

class TestDeadCodeAudit(unittest.TestCase):

    def test_no_notimplemented_in_capability_methods(self):
        import inspect
        for adapter_cls, methods in [
            (OllamaAdapter, ["chat", "chat_stream", "embed"]),
            (OpenAICompatibleAdapter, ["chat", "chat_stream", "embed"]),
            (BedrockAdapter, ["chat", "chat_stream", "embed"]),
        ]:
            for name in methods:
                method = getattr(adapter_cls, name, None)
                if method is None:
                    continue
                try:
                    src = inspect.getsource(method)
                    self.assertNotIn("raise NotImplementedError", src,
                        msg=f"{adapter_cls.__name__}.{name} has NotImplementedError")
                except OSError:
                    pass

    def test_no_notimplemented_in_llm_service(self):
        import inspect
        from app.intelligence.inference.services.llm_service import LLMService
        for name in ["chat", "chat_stream", "embed"]:
            method = getattr(LLMService, name, None)
            if method is None:
                continue
            try:
                src = inspect.getsource(method)
                self.assertNotIn("raise NotImplementedError", src,
                    msg=f"LLMService.{name} has NotImplementedError")
            except OSError:
                pass

    def test_no_todo_fixme_placeholder_in_core_files(self):
        # Derive the mcp-server root from this test file's location so the audit
        # runs against the real tree regardless of the checkout/workspace path.
        # This file lives at <root>/tests/intelligence/, so go up two levels.
        base = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        core_files = [
            "app/intelligence/inference/services/llm_service.py",
            "app/intelligence/inference/router/router.py",
            "app/intelligence/inference/strategies/priority.py",
            "app/intelligence/providers/base_provider.py",
            "app/intelligence/providers/provider_factory.py",
            "app/intelligence/providers/provider_manager.py",
            "app/intelligence/providers/adapters/ollama.py",
            "app/intelligence/providers/adapters/openai_compatible.py",
            "app/intelligence/providers/adapters/bedrock.py",
            "app/intelligence/ports/chat.py",
            "app/intelligence/ports/embedding.py",
            "app/intelligence/registry/catalog/catalog.py",
            "app/intelligence/runtime/registry_runtime.py",
        ]
        patterns = [re.compile(r"\bTODO\b"), re.compile(r"\bFIXME\b"), re.compile(r"\bPLACEHOLDER\b")]
        matches = []
        for path in core_files:
            full = os.path.join(base, path)
            if not os.path.exists(full):
                continue
            with open(full) as f:
                content = f.read()
            for pattern in patterns:
                if pattern.search(content):
                    matches.append(path)
        self.assertEqual(matches, [], msg=f"TODO/FIXME/PLACEHOLDER in: {matches}")


if __name__ == "__main__":
    unittest.main()
