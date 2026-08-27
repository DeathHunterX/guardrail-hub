"""Comprehensive tests for Phase 3 provider adapters.

Tests cover:
- OllamaAdapter
- OpenAICompatibleAdapter
- BedrockAdapter

For each adapter the test matrix covers:
1. BaseProvider contract (provider_id, provider_type, capabilities)
2. Lifecycle: initialize() — env var resolution
3. Lifecycle: validate_configuration() — success and failure paths
4. Lifecycle: start() / close()
5. register_all_adapters helper

Note: httpx is not installed in the test environment. A fake httpx module is
injected into sys.modules before adapter imports so that adapter.start() can
construct an AsyncClient without a real HTTP dependency.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Fake httpx — injected before any adapter import so AsyncClient construction works.
# Replaces the real httpx module for the entire test suite. The adapter's start()
# method calls httpx.AsyncClient(...); _FakeAsyncClient accepts all real parameters.
class _FakeAsyncClient:
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
_fake_httpx.Timeout = type("Timeout", (object,), {
    "__init__": lambda self, *args, **kwargs: None
})
_fake_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
_fake_httpx.ConnectError = type("ConnectError", (Exception,), {})
_fake_httpx.PoolTimeout = type("PoolTimeout", (Exception,), {})
_fake_httpx.ProtocolError = type("ProtocolError", (Exception,), {})
_fake_httpx.HTTPStatusError = type("HTTPStatusError", (Exception,), {})
sys.modules["httpx"] = _fake_httpx

# --- boto3 / botocore (needed by BedrockAdapter imported above) ---
class _FakeBoto3Session:
    def __init__(self, **kwargs): pass
    def client(self, name, **kw): return MagicMock()

class _FakeBoto3SessionConfig:
    def __init__(self, **kwargs): pass

class _FakeClientError(Exception):
    def __init__(self, response, operation_name):
        super().__init__(str(response))
        self.response = response

class _FakeBotoCoreError(Exception):
    def __init__(self, *args, **kwargs): super().__init__("BotoCore error")

class _FakeBotocoreExceptions:
    ClientError = _FakeClientError
    BotoCoreError = _FakeBotoCoreError
    EndpointConnectionError = type("ECE", (Exception,), {})
    ConnectTimeoutError = type("CTE", (Exception,), {})
    ReadTimeoutError = type("RTE", (Exception,), {})
    # These are real botocore.exceptions classes referenced by
    # BedrockAdapter._translate_boto_error. They must exist on the fake so that
    # the adapter's isinstance() checks resolve regardless of which test module
    # last installed the shared sys.modules["botocore.exceptions"] entry.
    ResponseStreamingError = type("RSE", (Exception,), {})
    DataNotFoundError = type("DNF", (Exception,), {})
    UnknownServiceError = type("USE", (Exception,), {})

class _FakeBotocoreModule:
    exceptions = _FakeBotocoreExceptions()
    ClientError = _FakeClientError
    BotoCoreError = _FakeBotoCoreError

_fake_boto3 = MagicMock()
_fake_boto3.Session = _FakeBoto3Session
_fake_boto3.__version__ = "1.0.0"
_fake_boto3.botocore = _FakeBotocoreModule()
_fake_boto3.session = MagicMock()
_fake_boto3.session.Config = _FakeBoto3SessionConfig
sys.modules["boto3"] = _fake_boto3
sys.modules["botocore"] = _fake_boto3.botocore
sys.modules["botocore.exceptions"] = _fake_boto3.botocore.exceptions
sys.modules["boto3.session"] = _fake_boto3.session
sys.modules["boto3.session.Config"] = _fake_boto3.session.Config


from app.intelligence.exceptions import LLMConfigurationError
from app.intelligence.ports.chat import ChatOptions
from app.intelligence.ports.embedding import EmbeddingOptions
from app.intelligence.providers.adapters import (
    BedrockAdapter,
    OllamaAdapter,
    OpenAICompatibleAdapter,
)
from app.intelligence.providers.base_provider import BaseProviderRuntime
from app.intelligence.providers.credential import ProviderCredential
from app.intelligence.registry.models.provider import AuthConfig, AuthType, ConnectionConfig, ProviderRecord
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record(
    *,
    provider_id: str = "test-provider",
    provider_type: ProviderType = ProviderType.OLLAMA,
    deployment: DeploymentType = DeploymentType.SELF_HOSTED,
    base_url: str = "http://localhost:11434",
    auth_type: AuthType | None = None,
    auth_header: str | None = None,
) -> ProviderRecord:
    """Construct a ProviderRecord using Phase 5D auth configuration.

    Auth type is derived from provider_type when not explicitly set:
    - OPENAI_COMPATIBLE: AuthType.API_KEY
    - BEDROCK: AuthType.AWS
    - OLLAMA/LOCAL: AuthType.NONE

    API keys are NOT stored in the record. They are resolved by ProviderManager
    from the CredentialStore and attached to the adapter at runtime.
    """
    if auth_type is None:
        if provider_type == ProviderType.OPENAI_COMPATIBLE:
            auth_type = AuthType.API_KEY
        elif provider_type == ProviderType.BEDROCK:
            auth_type = AuthType.AWS
        else:
            auth_type = AuthType.NONE

    return ProviderRecord(
        provider_id=provider_id,
        provider_type=provider_type,
        deployment=deployment,
        auth=AuthConfig(type=auth_type, auth_header=auth_header),
        connection=ConnectionConfig(base_url=base_url),
        capabilities=frozenset(),
    )


# ---------------------------------------------------------------------------
# Base Provider Contract — shared by all adapters
# ---------------------------------------------------------------------------

class TestBaseProviderContract(unittest.TestCase):
    """All adapters satisfy the BaseProvider and BaseProviderRuntime contracts."""

    def test_ollama_provider_id(self):
        adapter = OllamaAdapter(_record(provider_type=ProviderType.OLLAMA))
        self.assertEqual(adapter.provider_id, "test-provider")

    def test_ollama_provider_type(self):
        adapter = OllamaAdapter(_record(provider_type=ProviderType.OLLAMA))
        self.assertEqual(adapter.provider_type, "ollama")

    def test_ollama_capabilities(self):
        adapter = OllamaAdapter(_record(provider_type=ProviderType.OLLAMA))
        self.assertIn(Capability.CHAT, adapter.capabilities)
        self.assertIn(Capability.EMBEDDING, adapter.capabilities)

    def test_openai_provider_id(self):
        adapter = OpenAICompatibleAdapter(
            _record(provider_type=ProviderType.OPENAI_COMPATIBLE)
        )
        self.assertEqual(adapter.provider_id, "test-provider")

    def test_openai_provider_type(self):
        adapter = OpenAICompatibleAdapter(
            _record(provider_type=ProviderType.OPENAI_COMPATIBLE)
        )
        self.assertEqual(adapter.provider_type, "openai_compatible")

    def test_openai_capabilities(self):
        adapter = OpenAICompatibleAdapter(
            _record(provider_type=ProviderType.OPENAI_COMPATIBLE)
        )
        self.assertIn(Capability.CHAT, adapter.capabilities)
        self.assertIn(Capability.EMBEDDING, adapter.capabilities)

    def test_bedrock_provider_id(self):
        adapter = _make_bedrock_adapter()
        self.assertEqual(adapter.provider_id, "test-provider")

    def test_bedrock_provider_type(self):
        adapter = _make_bedrock_adapter()
        self.assertEqual(adapter.provider_type, "bedrock")

    def test_bedrock_capabilities(self):
        adapter = _make_bedrock_adapter()
        self.assertIn(Capability.CHAT, adapter.capabilities)
        self.assertIn(Capability.EMBEDDING, adapter.capabilities)

    def test_all_inherit_from_base_provider_runtime(self):
        self.assertTrue(issubclass(OllamaAdapter, BaseProviderRuntime))
        self.assertTrue(issubclass(OpenAICompatibleAdapter, BaseProviderRuntime))
        self.assertTrue(issubclass(BedrockAdapter, BaseProviderRuntime))


# ---------------------------------------------------------------------------
# OllamaAdapter — initialize()
# ---------------------------------------------------------------------------

class TestOllamaAdapterInitialize(unittest.TestCase):
    """initialize() uses the attached credential for API key.

    The API key comes from self._credential (attached by ProviderManager).
    When no credential is attached, _api_key is None (Ollama is typically unauthenticated).
    """

    def setUp(self):
        for var in ("OLLAMA_BASE_URL", "OLLAMA_API_KEY"):
            os.environ.pop(var, None)

    def test_uses_record_base_url(self):
        adapter = OllamaAdapter(_record(base_url="http://localhost:11434"))
        adapter.initialize()
        self.assertEqual(adapter._base_url, "http://localhost:11434")

    def test_uses_env_var_when_record_url_empty(self):
        os.environ["OLLAMA_BASE_URL"] = "http://ollama.local:11434"
        adapter = OllamaAdapter(_record(base_url=""))
        adapter.initialize()
        self.assertEqual(adapter._base_url, "http://ollama.local:11434")

    def test_uses_default_when_record_and_env_are_empty(self):
        adapter = OllamaAdapter(_record(base_url=""))
        adapter.initialize()
        self.assertEqual(adapter._base_url, "http://localhost:11434")

    def test_raises_when_url_invalid(self):
        adapter = OllamaAdapter(_record(base_url="not-a-url"))
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.initialize()
        self.assertIn("not a valid URL", str(ctx.exception))

    def test_uses_attached_credential(self):
        # API key comes from the attached credential (set by ProviderManager).
        adapter = OllamaAdapter(_record(provider_type=ProviderType.OLLAMA, base_url="http://localhost:11434"))
        adapter.attach_credential(ProviderCredential(api_key="attached-secret"))
        adapter.initialize()
        self.assertEqual(adapter._api_key, "attached-secret")

    def test_api_key_none_without_credential(self):
        # Ollama is typically unauthenticated: no credential attached means no API key.
        adapter = OllamaAdapter(_record(provider_type=ProviderType.OLLAMA, base_url="http://localhost:11434"))
        adapter.initialize()
        self.assertIsNone(adapter._api_key)

    def tearDown(self):
        for var in ("OLLAMA_BASE_URL", "OLLAMA_API_KEY"):
            os.environ.pop(var, None)


# ---------------------------------------------------------------------------
# OllamaAdapter — validate_configuration()
# ---------------------------------------------------------------------------

class TestOllamaAdapterValidate(unittest.TestCase):
    """validate_configuration() enforces Ollama deployment constraints."""

    def setUp(self):
        for var in ("OLLAMA_BASE_URL", "OLLAMA_API_KEY"):
            os.environ.pop(var, None)

    def test_accepts_self_hosted(self):
        adapter = OllamaAdapter(_record(deployment=DeploymentType.SELF_HOSTED))
        adapter.initialize()
        adapter.validate_configuration()  # must not raise

    def test_accepts_proxy(self):
        adapter = OllamaAdapter(_record(deployment=DeploymentType.PROXY))
        adapter.initialize()
        adapter.validate_configuration()  # must not raise

    def test_rejects_cloud(self):
        adapter = OllamaAdapter(_record(deployment=DeploymentType.CLOUD))
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.validate_configuration()
        self.assertIn("cloud", str(ctx.exception).lower())

    def tearDown(self):
        for var in ("OLLAMA_BASE_URL", "OLLAMA_API_KEY"):
            os.environ.pop(var, None)


# ---------------------------------------------------------------------------
# OllamaAdapter — lifecycle
# ---------------------------------------------------------------------------

class TestOllamaAdapterLifecycle(unittest.TestCase):
    """start() / close() and is_started flag."""

    def setUp(self):
        for var in ("OLLAMA_BASE_URL", "OLLAMA_API_KEY"):
            os.environ.pop(var, None)

    def test_start_marks_started(self):
        adapter = OllamaAdapter(_record())
        adapter.initialize()
        self.assertFalse(adapter.is_started)
        import asyncio
        asyncio.run(adapter.start())
        self.assertTrue(adapter.is_started)

    def test_close_marks_stopped(self):
        adapter = OllamaAdapter(_record())
        adapter.initialize()
        import asyncio
        asyncio.run(adapter.start())
        self.assertTrue(adapter.is_started)
        asyncio.run(adapter.close())
        self.assertFalse(adapter.is_started)

    def test_start_is_idempotent(self):
        adapter = OllamaAdapter(_record())
        adapter.initialize()
        import asyncio
        asyncio.run(adapter.start())
        asyncio.run(adapter.start())  # must not raise

    def tearDown(self):
        for var in ("OLLAMA_BASE_URL", "OLLAMA_API_KEY"):
            os.environ.pop(var, None)


# ---------------------------------------------------------------------------
# OpenAICompatibleAdapter — initialize()
# ---------------------------------------------------------------------------

class TestOpenAICompatibleAdapterInitialize(unittest.TestCase):
    """initialize() uses the attached credential for API key.

    A credential MUST be attached via attach_credential() before initialize().
    The Authorization header value comes from auth.auth_header in the record.
    """

    def setUp(self):
        for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
            os.environ.pop(var, None)

    def _make_openai_record(self, **kwargs) -> ProviderRecord:
        defaults = dict(
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            base_url="https://api.openai.com/v1",
            auth_type=AuthType.API_KEY,
        )
        defaults.update(kwargs)
        return _record(**defaults)

    def test_uses_record_base_url(self):
        adapter = OpenAICompatibleAdapter(self._make_openai_record())
        adapter.attach_credential(ProviderCredential(api_key="test-key"))
        adapter.initialize()
        self.assertEqual(adapter._base_url, "https://api.openai.com/v1")

    def test_env_var_used_when_record_url_is_empty(self):
        # Env var is the fallback when the record URL is not set.
        os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/v1"
        adapter = OpenAICompatibleAdapter(
            self._make_openai_record(base_url="")
        )
        adapter.attach_credential(ProviderCredential(api_key="test-key"))
        adapter.initialize()
        self.assertEqual(adapter._base_url, "https://api.groq.com/v1")

    def test_record_url_takes_priority_over_env_var(self):
        # Record URL is checked first; env var is only a fallback.
        os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/v1"
        adapter = OpenAICompatibleAdapter(
            self._make_openai_record(base_url="https://api.openai.com/v1")
        )
        adapter.attach_credential(ProviderCredential(api_key="test-key"))
        adapter.initialize()
        self.assertEqual(adapter._base_url, "https://api.openai.com/v1")

    def test_raises_when_no_credential_attached(self):
        # API-key providers require a credential to be attached before initialize().
        adapter = OpenAICompatibleAdapter(self._make_openai_record())
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.initialize()
        self.assertIn("API key credential", str(ctx.exception))

    def test_uses_attached_credential(self):
        # API key comes from the attached credential (set by ProviderManager).
        adapter = OpenAICompatibleAdapter(self._make_openai_record())
        adapter.attach_credential(ProviderCredential(api_key="attached-secret"))
        adapter.initialize()
        self.assertEqual(adapter._api_key, "attached-secret")

    def test_stores_custom_auth_header(self):
        adapter = OpenAICompatibleAdapter(
            self._make_openai_record(auth_header="X-API-Key")
        )
        adapter.attach_credential(ProviderCredential(api_key="test-key"))
        adapter.initialize()
        self.assertEqual(adapter._auth_header, "X-API-Key")

    def test_defaults_auth_header_to_authorization(self):
        adapter = OpenAICompatibleAdapter(self._make_openai_record())
        adapter.attach_credential(ProviderCredential(api_key="test-key"))
        adapter.initialize()
        self.assertEqual(adapter._auth_header, "Authorization")

    def tearDown(self):
        for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
            os.environ.pop(var, None)


# ---------------------------------------------------------------------------
# OpenAICompatibleAdapter — validate_configuration()
# ---------------------------------------------------------------------------

class TestOpenAICompatibleAdapterValidate(unittest.TestCase):
    """validate_configuration() enforces HTTPS for cloud deployments."""

    def setUp(self):
        for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
            os.environ.pop(var, None)

    def _make_openai_record(self, **kwargs) -> ProviderRecord:
        defaults = dict(
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            base_url="https://api.openai.com/v1",
            auth_type=AuthType.API_KEY,
        )
        defaults.update(kwargs)
        return _record(**defaults)

    def test_accepts_https(self):
        adapter = OpenAICompatibleAdapter(self._make_openai_record())
        adapter.attach_credential(ProviderCredential(api_key="test-key"))
        adapter.initialize()
        adapter.validate_configuration()  # must not raise

    def test_rejects_http_for_cloud(self):
        adapter = OpenAICompatibleAdapter(
            self._make_openai_record(base_url="http://insecure.local/v1")
        )
        adapter.attach_credential(ProviderCredential(api_key="test-key"))
        adapter.initialize()
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.validate_configuration()
        self.assertIn("HTTPS", str(ctx.exception))

    def tearDown(self):
        for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
            os.environ.pop(var, None)


# ---------------------------------------------------------------------------
# OpenAICompatibleAdapter — lifecycle
# ---------------------------------------------------------------------------

class TestOpenAICompatibleAdapterLifecycle(unittest.TestCase):
    """start() / close() for OpenAICompatibleAdapter."""

    def setUp(self):
        for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
            os.environ.pop(var, None)

    def test_start_and_close(self):
        adapter = OpenAICompatibleAdapter(
            _record(
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                deployment=DeploymentType.CLOUD,
                base_url="https://api.openai.com/v1",
                auth_type=AuthType.API_KEY,
            )
        )
        adapter.attach_credential(ProviderCredential(api_key="test-key"))
        adapter.initialize()
        import asyncio
        asyncio.run(adapter.start())
        self.assertTrue(adapter.is_started)
        asyncio.run(adapter.close())
        self.assertFalse(adapter.is_started)

    def tearDown(self):
        for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
            os.environ.pop(var, None)


# ---------------------------------------------------------------------------
# BedrockAdapter — helpers
# ---------------------------------------------------------------------------

def _clear_bedrock_env() -> None:
    for var in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    ):
        os.environ.pop(var, None)


def _set_bedrock_env(region: str = "us-east-1") -> None:
    os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "secret123"
    os.environ["AWS_REGION"] = region


def _make_bedrock_adapter(region: str = "us-east-1") -> BedrockAdapter:
    """Construct a ready-to-initialize BedrockAdapter with valid env vars."""
    _set_bedrock_env(region)
    adapter = BedrockAdapter(
        _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
    )
    return adapter


# ---------------------------------------------------------------------------
# BedrockAdapter — initialize()
# ---------------------------------------------------------------------------

class TestBedrockAdapterInitialize(unittest.TestCase):
    """initialize() resolves AWS credentials and region from the environment."""

    def setUp(self):
        _clear_bedrock_env()

    def test_resolves_region_from_AWS_REGION(self):
        # Credentials must be set alongside the region being tested.
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secret123"
        os.environ["AWS_REGION"] = "us-west-2"
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        adapter.initialize()
        self.assertEqual(adapter._region, "us-west-2")

    def test_resolves_region_from_AWS_DEFAULT_REGION(self):
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secret123"
        os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        adapter.initialize()
        self.assertEqual(adapter._region, "eu-west-1")

    def test_raises_when_region_missing(self):
        # Only credentials are set; region is absent to exercise the right check.
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secret123"
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.initialize()
        self.assertIn("AWS_REGION", str(ctx.exception))

    def test_constructs_endpoint_from_region(self):
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secret123"
        os.environ["AWS_REGION"] = "us-west-2"
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        adapter.initialize()
        self.assertEqual(
            adapter._endpoint,
            "https://bedrock-runtime.us-west-2.amazonaws.com",
        )

    def test_raises_on_invalid_region_format(self):
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secret123"
        os.environ["AWS_REGION"] = "not a valid region with spaces!!!"
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.initialize()
        self.assertIn("does not look like", str(ctx.exception))

    def test_resolves_access_key(self):
        _set_bedrock_env()
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        adapter.initialize()
        self.assertEqual(adapter._access_key, "AKIAIOSFODNN7EXAMPLE")

    def test_raises_when_access_key_missing(self):
        # Region must be set first so we pass the region check.
        _set_bedrock_env()
        os.environ.pop("AWS_ACCESS_KEY_ID", None)
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.initialize()
        self.assertIn("AWS_ACCESS_KEY_ID", str(ctx.exception))

    def test_raises_when_secret_key_missing(self):
        _set_bedrock_env()
        os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.initialize()
        self.assertIn("AWS_SECRET_ACCESS_KEY", str(ctx.exception))

    def test_stores_session_token_when_present(self):
        _set_bedrock_env()
        os.environ["AWS_SESSION_TOKEN"] = "session-token-value"
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        adapter.initialize()
        self.assertEqual(adapter._session_token, "session-token-value")

    def test_session_token_none_when_not_set(self):
        _set_bedrock_env()
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.CLOUD)
        )
        adapter.initialize()
        self.assertIsNone(adapter._session_token)

    def tearDown(self):
        _clear_bedrock_env()


# ---------------------------------------------------------------------------
# BedrockAdapter — validate_configuration()
# ---------------------------------------------------------------------------

class TestBedrockAdapterValidate(unittest.TestCase):
    """validate_configuration() enforces Bedrock-specific rules."""

    def setUp(self):
        _clear_bedrock_env()
        # Set full credentials so individual tests can skip what they don't need to test.
        _set_bedrock_env()

    def test_accepts_cloud(self):
        adapter = _make_bedrock_adapter()
        adapter.initialize()
        adapter.validate_configuration()  # must not raise

    def test_rejects_self_hosted(self):
        adapter = BedrockAdapter(
            _record(provider_type=ProviderType.BEDROCK, deployment=DeploymentType.SELF_HOSTED)
        )
        adapter.initialize()
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.validate_configuration()
        self.assertIn("cloud", str(ctx.exception))

    def tearDown(self):
        _clear_bedrock_env()


# ---------------------------------------------------------------------------
# BedrockAdapter — lifecycle
# ---------------------------------------------------------------------------

class TestBedrockAdapterLifecycle(unittest.TestCase):
    """start() / close() for BedrockAdapter."""

    def setUp(self):
        _clear_bedrock_env()

    def test_start_and_close(self):
        adapter = _make_bedrock_adapter()
        adapter.initialize()
        import asyncio
        asyncio.run(adapter.start())
        self.assertTrue(adapter.is_started)
        asyncio.run(adapter.close())
        self.assertFalse(adapter.is_started)

    def tearDown(self):
        _clear_bedrock_env()


# ---------------------------------------------------------------------------
# register_all_adapters
# ---------------------------------------------------------------------------

class TestRegisterAllAdapters(unittest.TestCase):
    """register_all_adapters registers all Phase 3 adapters with a factory."""

    def test_registers_three_types(self):
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.adapters import register_all_adapters

        factory = ProviderFactory()
        register_all_adapters(factory)

        self.assertTrue(factory.is_registered("ollama"))
        self.assertTrue(factory.is_registered("openai_compatible"))
        self.assertTrue(factory.is_registered("bedrock"))

    def test_each_type_has_chat_and_embedding_capabilities(self):
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.adapters import register_all_adapters

        factory = ProviderFactory()
        register_all_adapters(factory)

        for ptype in ("ollama", "openai_compatible", "bedrock"):
            caps = factory.get_capabilities(ptype)
            self.assertIn(Capability.CHAT, caps, f"{ptype} missing CHAT")
            self.assertIn(Capability.EMBEDDING, caps, f"{ptype} missing EMBEDDING")

    def test_factory_can_create_ollama_adapter(self):
        from app.intelligence.providers.provider_factory import ProviderFactory
        from app.intelligence.providers.adapters import register_all_adapters

        factory = ProviderFactory()
        register_all_adapters(factory)

        adapter = factory.create(
            _record(
                provider_type=ProviderType.OLLAMA,
                deployment=DeploymentType.SELF_HOSTED,
                base_url="http://localhost:11434",
            )
        )
        self.assertIsInstance(adapter, OllamaAdapter)


if __name__ == "__main__":
    unittest.main()
