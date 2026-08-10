"""Tests for the AWS Bedrock adapter.

All tests are isolated from real AWS by injecting fake boto3/botocore/httpx
modules into sys.modules before any adapter is imported.
"""

import json
import os
import sys
import unittest
from base64 import b64encode
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Fake exception classes — must be defined before _inject_all_fakes()
# ---------------------------------------------------------------------------

class _FakeClientError(Exception):
    """Fake botocore ClientError with a .response dict."""

    def __init__(self, response, operation_name):
        super().__init__(str(response))
        self.response = response


class _FakeEndpointConnectionError(Exception):
    def __init__(self, endpoint_url=None, **kwargs):
        super().__init__(f"Could not connect to {endpoint_url}")


class _FakeConnectTimeoutError(Exception):
    def __init__(self, endpoint_url=None, **kwargs):
        super().__init__(f"Connect timeout to {endpoint_url}")


class _FakeReadTimeoutError(Exception):
    def __init__(self, endpoint_url=None, **kwargs):
        super().__init__(f"Read timeout from {endpoint_url}")


class _FakeResponseStreamingError(Exception):
    def __init__(self, **kwargs):
        super().__init__("Response streaming error")


class _FakeDataNotFoundError(Exception):
    def __init__(self, key=None, *args, **kwargs):
        super().__init__(f"Data not found: {key}")
        self.key = key


class _FakeUnknownServiceError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__("Unknown service")


class _FakeBotoCoreError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__("BotoCore error")


# ---------------------------------------------------------------------------
# Inject fake modules — must happen before any adapter import
# ---------------------------------------------------------------------------

def _inject_all_fakes():
    """Install fake boto3, botocore, and httpx into sys.modules.

    The fake boto3.Session is a real class so that it accepts the kwargs
    that the adapter passes. botocore must be a real module object (not a
    MagicMock) so that ``import botocore.exceptions as botocore`` inside the
    adapter gets the actual fake exception classes, making isinstance() work.
    """
    # --- httpx (needed by OllamaAdapter imported in __init__) ---
    fake_httpx = MagicMock()
    fake_httpx.AsyncClient = MagicMock
    fake_httpx.Timeout = type("Timeout", (), {"__init__": lambda s, *a, **k: None})
    fake_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
    fake_httpx.ConnectError = type("ConnectError", (Exception,), {})
    fake_httpx.PoolTimeout = type("PoolTimeout", (Exception,), {})
    fake_httpx.ProtocolError = type("ProtocolError", (Exception,), {})
    fake_httpx.HTTPStatusError = type("HTTPStatusError", (Exception,), {})
    fake_httpx.Response = type("Response", (), {})
    sys.modules["httpx"] = fake_httpx

    # --- botocore — real module object so isinstance() works inside the adapter ---
    class _FakeBotocoreExceptions:
        ClientError = _FakeClientError
        BotoCoreError = _FakeBotoCoreError
        EndpointConnectionError = _FakeEndpointConnectionError
        ConnectTimeoutError = _FakeConnectTimeoutError
        ReadTimeoutError = _FakeReadTimeoutError
        ResponseStreamingError = _FakeResponseStreamingError
        DataNotFoundError = _FakeDataNotFoundError
        UnknownServiceError = _FakeUnknownServiceError

    class _FakeBotocoreModule:
        """Fake botocore module: both the module and .exceptions are real objects."""
        exceptions = _FakeBotocoreExceptions()
        ClientError = _FakeClientError
        BotoCoreError = _FakeBotoCoreError
        EndpointConnectionError = _FakeEndpointConnectionError
        ConnectTimeoutError = _FakeConnectTimeoutError
        ReadTimeoutError = _FakeReadTimeoutError
        ResponseStreamingError = _FakeResponseStreamingError
        DataNotFoundError = _FakeDataNotFoundError
        UnknownServiceError = _FakeUnknownServiceError

    fake_botocore = _FakeBotocoreModule()
    # Both are required so import botocore.exceptions works inside the adapter.
    sys.modules["botocore"] = fake_botocore
    sys.modules["botocore.exceptions"] = fake_botocore.exceptions

    # --- boto3 ---
    # Must be a real class so Session() accepts kwargs.
    class _FakeBoto3Session:
        def __init__(self, **kwargs):
            self._kwargs = kwargs

        def client(self, name, **kw):
            return _FakeBedrockClient()

    class _FakeBoto3SessionConfig:
        def __init__(self, **kwargs):
            pass

    fake_boto3 = MagicMock()
    fake_boto3.Session = _FakeBoto3Session
    fake_boto3.__version__ = "1.0.0"
    fake_boto3.botocore = fake_botocore
    fake_boto3.session = MagicMock()
    fake_boto3.session.Config = _FakeBoto3SessionConfig
    sys.modules["boto3"] = fake_boto3
    sys.modules["boto3.session"] = fake_boto3.session
    sys.modules["boto3.session.Config"] = fake_boto3.session.Config


_inject_all_fakes()

# ---------------------------------------------------------------------------
# Imports from the application
# ---------------------------------------------------------------------------

from app.intelligence.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitedError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMValidationError,
)
from app.intelligence.ports.chat import ChatMessage, ChatOptions
from app.intelligence.ports.embedding import EmbeddingOptions
from app.intelligence.providers.adapters.bedrock import (
    BedrockAdapter,
    _build_anthropic_payload,
    _build_embedding_payload,
    _build_titan_payload,
    _build_cohere_payload,
    _parse_anthropic_response,
    _parse_stream_event,
    _parse_embedding_response,
    _extract_anthropic_usage,
    _extract_finish_reason,
    _translate_boto_error,
    _is_valid_aws_region,
)
from app.intelligence.registry.models.provider import AuthConfig, ConnectionConfig, ProviderRecord
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class _FakeBody:
    """Fake boto3 API response body (io-like, has .read())."""

    def __init__(self, data: dict):
        self._data = json.dumps(data).encode("utf-8")

    def read(self):
        return self._data


class _FakeBedrockClient:
    """Fake bedrock-runtime client whose methods can be overridden per-test."""

    def invoke_model(self, **kwargs):
        # Default: return a valid chat response. Tests override via assignment.
        return _make_ok_chat_response("hello world")

    def invoke_model_with_response_stream(self, **kwargs):
        # Default: return a valid stream. Tests override via assignment.
        return {
            "body": _FakeEventStream([
                _make_stream_event("he"),
                _make_stream_event("llo"),
            ])
        }


def _make_ok_chat_response(content: str = "hello world") -> dict:
    return {
        "body": _FakeBody({
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": content}],
            "model": "anthropic.claude-3-sonnet-v1",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        })
    }


def _make_stream_event(text: str) -> dict:
    """Build a fake Bedrock content_block_delta event as the SDK sends it."""
    inner = {"type": "content_block_delta", "index": 0, "delta": {"type": "text", "text": text}}
    return {"bytes": b64encode(json.dumps(inner).encode("utf-8")).decode("ascii")}


class _FakeEventStream:
    """Fake botocore event stream that yields raw_event dicts."""

    def __init__(self, events: list):
        self._events = events

    def __iter__(self):
        return iter(self._events)


def _make_record(**overrides) -> ProviderRecord:
    defaults = dict(
        provider_id="test-bedrock",
        provider_type=ProviderType.BEDROCK,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(),
        connection=ConnectionConfig(base_url=""),
        capabilities=frozenset(),
    )
    defaults.update(overrides)
    return ProviderRecord(**defaults)


def _set_bedrock_env(
    region="us-east-1",
    access_key="AKIAIOSFODNN7EXAMPLE",
    secret="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    session_token=None,
):
    os.environ["AWS_REGION"] = region
    os.environ["AWS_ACCESS_KEY_ID"] = access_key
    os.environ["AWS_SECRET_ACCESS_KEY"] = secret
    if session_token is not None:
        os.environ["AWS_SESSION_TOKEN"] = session_token
    else:
        os.environ.pop("AWS_SESSION_TOKEN", None)


def _clear_bedrock_env():
    for var in (
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ):
        os.environ.pop(var, None)


def _start_adapter(adapter):
    """Inject a mock client without calling boto3."""
    mock_client = MagicMock()
    mock_client.invoke_model = MagicMock()
    mock_client.invoke_model_with_response_stream = MagicMock()
    object.__setattr__(adapter, "_client", mock_client)
    object.__setattr__(adapter, "_started", True)


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------

class TestBuildAnthropicPayload(unittest.TestCase):
    def test_basic_payload_includes_version_and_messages(self):
        messages = [ChatMessage(role="user", content="say hello")]
        opts = ChatOptions(model="anthropic.claude-3-sonnet-v1:0")
        payload = _build_anthropic_payload(messages, opts)
        self.assertEqual(payload["anthropic_version"], "bedrock-2023-05-31")
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["messages"][0]["content"], "say hello")
        self.assertFalse(payload["stream"])

    def test_system_message_mapped_correctly(self):
        messages = [
            ChatMessage(role="system", content="you are helpful"),
            ChatMessage(role="user", content="hi"),
        ]
        opts = ChatOptions(model="claude")
        payload = _build_anthropic_payload(messages, opts)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")

    def test_temperature_forwarded(self):
        messages = [ChatMessage(role="user", content="hi")]
        opts = ChatOptions(model="claude", temperature=0.9)
        self.assertEqual(_build_anthropic_payload(messages, opts)["temperature"], 0.9)

    def test_max_tokens_explicit_overrides_default(self):
        messages = [ChatMessage(role="user", content="hi")]
        opts = ChatOptions(model="claude", max_tokens=256)
        self.assertEqual(_build_anthropic_payload(messages, opts)["max_tokens"], 256)

    def test_default_max_tokens_when_not_specified(self):
        messages = [ChatMessage(role="user", content="hi")]
        opts = ChatOptions(model="claude")
        self.assertEqual(_build_anthropic_payload(messages, opts)["max_tokens"], 4096)

    def test_stop_sequences_forwarded(self):
        messages = [ChatMessage(role="user", content="hi")]
        opts = ChatOptions(model="claude", stop=["END", "STOP"])
        self.assertEqual(_build_anthropic_payload(messages, opts)["stop_sequences"], ["END", "STOP"])

    def test_top_p_forwarded(self):
        messages = [ChatMessage(role="user", content="hi")]
        opts = ChatOptions(model="claude", top_p=0.8)
        self.assertEqual(_build_anthropic_payload(messages, opts)["top_p"], 0.8)

    def test_seed_forwarded(self):
        messages = [ChatMessage(role="user", content="hi")]
        opts = ChatOptions(model="claude", seed=42)
        self.assertEqual(_build_anthropic_payload(messages, opts)["random_seed"], 42)

    def test_stream_true_when_requested(self):
        messages = [ChatMessage(role="user", content="hi")]
        opts = ChatOptions(model="claude")
        self.assertTrue(_build_anthropic_payload(messages, opts, stream=True)["stream"])


class TestBuildEmbeddingPayload(unittest.TestCase):
    def test_titan_payload(self):
        opts = EmbeddingOptions(model="amazon.titan-embed-text-v1")
        payload = _build_embedding_payload(["hello world"], opts)
        self.assertEqual(payload["inputText"], "hello world")

    def test_titan_encoding_format(self):
        opts = EmbeddingOptions(model="amazon.titan-embed-text-v1", encoding_format="base64")
        payload = _build_embedding_payload(["hello"], opts)
        self.assertEqual(payload["embeddingConfig"]["outputDataType"], "base64")

    def test_cohere_payload(self):
        opts = EmbeddingOptions(model="cohere.embed-english-v3")
        payload = _build_embedding_payload(["hello", "world"], opts)
        self.assertEqual(payload["texts"], ["hello", "world"])

    def test_cohere_dimensions(self):
        opts = EmbeddingOptions(model="cohere.embed-english-v3", dimensions=1024)
        payload = _build_embedding_payload(["hello"], opts)
        self.assertEqual(payload["dimensions"], 1024)
        self.assertEqual(payload["input_type"], "search_document")

    def test_unsupported_model_raises_validation(self):
        opts = EmbeddingOptions(model="unsupported.model.v1")
        with self.assertRaises(LLMValidationError) as ctx:
            _build_embedding_payload(["hello"], opts)
        self.assertIn("unsupported embedding model", str(ctx.exception))


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

class TestParseAnthropicResponse(unittest.TestCase):
    def test_extracts_text_from_content_block(self):
        body = {
            "content": [{"type": "text", "text": "hello world"}],
            "stop_reason": "end_turn",
        }
        self.assertEqual(_parse_anthropic_response(body, "claude"), "hello world")

    def test_empty_content_returns_empty_string(self):
        self.assertEqual(_parse_anthropic_response({"content": []}, "claude"), "")

    def test_missing_content_returns_empty_string(self):
        self.assertEqual(_parse_anthropic_response({}, "claude"), "")


class TestExtractAnthropicUsage(unittest.TestCase):
    def test_full_usage(self):
        body = {"usage": {"input_tokens": 10, "output_tokens": 20}}
        usage = _extract_anthropic_usage(body)
        self.assertEqual(usage, {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})

    def test_no_usage_returns_none(self):
        self.assertIsNone(_extract_anthropic_usage({}))


class TestExtractFinishReason(unittest.TestCase):
    def test_end_turn_maps_to_stop(self):
        self.assertEqual(_extract_finish_reason({"stop_reason": "end_turn"}), "stop")

    def test_max_tokens_maps_to_length(self):
        self.assertEqual(_extract_finish_reason({"stop_reason": "max_tokens"}), "length")

    def test_tool_use_maps_to_tool_calls(self):
        self.assertEqual(_extract_finish_reason({"stop_reason": "tool_use"}), "tool_calls")

    def test_unknown_reason_passed_through(self):
        self.assertEqual(_extract_finish_reason({"stop_reason": "custom"}), "custom")


class TestParseEmbeddingResponse(unittest.TestCase):
    def test_titan_extracts_embedding_and_usage(self):
        body = {"embedding": [0.1, 0.2], "inputTokenCount": 5}
        emb, usage = _parse_embedding_response(body, "amazon.titan-embed-text-v1")
        self.assertEqual(emb, [[0.1, 0.2]])
        self.assertEqual(usage, {"prompt_tokens": 5, "completion_tokens": 0, "total_tokens": 5})

    def test_cohere_extracts_embeddings_and_usage(self):
        body = {"embeddings": [[0.3, 0.4]], "tokens": 3}
        emb, usage = _parse_embedding_response(body, "cohere.embed-english-v3")
        self.assertEqual(len(emb), 1)
        self.assertEqual(usage["prompt_tokens"], 3)


# ---------------------------------------------------------------------------
# Stream event parser — unit-testable in isolation
# ---------------------------------------------------------------------------

class TestParseStreamEvent(unittest.TestCase):
    def test_content_block_delta_returns_text(self):
        inner = {"type": "content_block_delta", "delta": {"text": "hello"}}
        event = {"bytes": b64encode(json.dumps(inner).encode()).decode()}
        self.assertEqual(_parse_stream_event(event), "hello")

    def test_message_delta_returns_none(self):
        inner = {"type": "message_delta", "usage": {"output_tokens": 10}}
        event = {"bytes": b64encode(json.dumps(inner).encode()).decode()}
        self.assertIsNone(_parse_stream_event(event))

    def test_no_bytes_field_returns_none(self):
        self.assertIsNone(_parse_stream_event({}))

    def test_malformed_base64_returns_none(self):
        # "not-valid-base64!!!" is not valid base64.
        self.assertIsNone(_parse_stream_event({"bytes": "not-valid-base64!!!"}))

    def test_valid_base64_non_json_returns_none(self):
        raw = b64encode(b"not json").decode()
        self.assertIsNone(_parse_stream_event({"bytes": raw}))


# ---------------------------------------------------------------------------
# Exception translation
# ---------------------------------------------------------------------------

class TestTranslateBotoError(unittest.TestCase):
    # --- Authentication errors ---
    def test_expired_token(self):
        exc = _FakeClientError(
            {"Error": {"Code": "ExpiredTokenException", "Message": "token expired"}},
            "InvokeModel",
        )
        result = _translate_boto_error(exc, "bedrock-test")
        self.assertIsInstance(result, LLMAuthenticationError)
        self.assertIn("authentication failed", str(result))

    def test_unrecognized_client(self):
        exc = _FakeClientError(
            {"Error": {"Code": "UnrecognizedClientException", "Message": "bad sig"}},
            "InvokeModel",
        )
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMAuthenticationError)

    def test_access_denied(self):
        exc = _FakeClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "InvokeModel",
        )
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMAuthenticationError)

    # --- Rate limit ---
    def test_throttling(self):
        exc = _FakeClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "slow down"}},
            "InvokeModel",
        )
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMRateLimitedError)

    # --- Validation ---
    def test_validation_error(self):
        exc = _FakeClientError(
            {"Error": {"Code": "ValidationError", "Message": "bad param"}},
            "InvokeModel",
        )
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMValidationError)

    # --- Service unavailable ---
    def test_internal_server_error(self):
        exc = _FakeClientError(
            {"Error": {"Code": "InternalServerException", "Message": "500"}},
            "InvokeModel",
        )
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMUnavailableError)

    # --- Endpoint ---
    def test_endpoint_connection_error(self):
        exc = _FakeEndpointConnectionError(endpoint_url="https://bedrock")
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMUnavailableError)

    # --- Timeouts ---
    def test_connect_timeout(self):
        exc = _FakeConnectTimeoutError(endpoint_url="https://bedrock")
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMTimeoutError)

    def test_read_timeout(self):
        exc = _FakeReadTimeoutError(endpoint_url="https://bedrock")
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMTimeoutError)

    def test_response_streaming_error(self):
        exc = _FakeResponseStreamingError()
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMTimeoutError)

    # --- Model/service not found ---
    def test_data_not_found(self):
        exc = _FakeDataNotFoundError(key="model")
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMProviderError)

    # --- Generic ---
    def test_botocore_error(self):
        exc = _FakeBotoCoreError()
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMProviderError)

    def test_unknown_exception(self):
        exc = RuntimeError("something went wrong")
        self.assertIsInstance(_translate_boto_error(exc, "x"), LLMProviderError)


# ---------------------------------------------------------------------------
# Region validation
# ---------------------------------------------------------------------------

class TestIsValidAwsRegion(unittest.TestCase):
    def test_valid_regions(self):
        self.assertTrue(_is_valid_aws_region("us-east-1"))
        self.assertTrue(_is_valid_aws_region("eu-west-1"))
        self.assertTrue(_is_valid_aws_region("ap-southeast-1"))

    def test_empty_is_invalid(self):
        self.assertFalse(_is_valid_aws_region(""))

    def test_too_long_is_invalid(self):
        self.assertFalse(_is_valid_aws_region("a" * 21))


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestBedrockAdapterLifecycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _clear_bedrock_env()
        _set_bedrock_env()

    def tearDown(self):
        _clear_bedrock_env()

    def test_initialize_stores_credentials(self):
        adapter = BedrockAdapter(_make_record())
        adapter.initialize()
        self.assertEqual(adapter._region, "us-east-1")
        self.assertEqual(adapter._access_key, "AKIAIOSFODNN7EXAMPLE")
        self.assertEqual(adapter._secret_key, "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

    def test_initialize_stores_session_token(self):
        _set_bedrock_env(session_token="session-token-xyz")
        adapter = BedrockAdapter(_make_record())
        adapter.initialize()
        self.assertEqual(adapter._session_token, "session-token-xyz")

    def test_initialize_raises_when_region_missing(self):
        _clear_bedrock_env()
        with self.assertRaises(LLMConfigurationError) as ctx:
            BedrockAdapter(_make_record()).initialize()
        self.assertIn("AWS_REGION", str(ctx.exception))

    def test_initialize_raises_when_access_key_missing(self):
        os.environ.pop("AWS_ACCESS_KEY_ID")
        with self.assertRaises(LLMConfigurationError) as ctx:
            BedrockAdapter(_make_record()).initialize()
        self.assertIn("AWS_ACCESS_KEY_ID", str(ctx.exception))

    def test_initialize_raises_when_secret_missing(self):
        os.environ.pop("AWS_SECRET_ACCESS_KEY")
        with self.assertRaises(LLMConfigurationError) as ctx:
            BedrockAdapter(_make_record()).initialize()
        self.assertIn("AWS_SECRET_ACCESS_KEY", str(ctx.exception))

    def test_initialize_raises_on_invalid_region_format(self):
        os.environ["AWS_REGION"] = "not--a--valid--region!!"
        with self.assertRaises(LLMConfigurationError) as ctx:
            BedrockAdapter(_make_record()).initialize()
        self.assertIn("does not look like a valid AWS region", str(ctx.exception))

    def test_validate_rejects_self_hosted(self):
        record = _make_record(deployment=DeploymentType.SELF_HOSTED)
        adapter = BedrockAdapter(record)
        adapter.initialize()
        with self.assertRaises(LLMConfigurationError) as ctx:
            adapter.validate_configuration()
        self.assertIn("cloud", str(ctx.exception).lower())

    def test_validate_accepts_cloud(self):
        adapter = BedrockAdapter(_make_record())
        adapter.initialize()
        adapter.validate_configuration()  # must not raise

    async def test_start_sets_started_flag(self):
        adapter = BedrockAdapter(_make_record())
        adapter.initialize()
        # Directly inject a mock client so we don't depend on boto3 internals.
        mock_client = MagicMock()
        object.__setattr__(adapter, "_client", mock_client)
        await adapter.start()
        self.assertTrue(adapter.is_started)

    async def test_close_sets_started_false(self):
        adapter = BedrockAdapter(_make_record())
        adapter.initialize()
        mock_client = MagicMock()
        object.__setattr__(adapter, "_client", mock_client)
        await adapter.start()
        self.assertTrue(adapter.is_started)
        await adapter.close()
        self.assertFalse(adapter.is_started)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class TestBedrockAdapterChat(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _clear_bedrock_env()
        _set_bedrock_env()
        self.adapter = BedrockAdapter(_make_record())
        self.adapter.initialize()
        _start_adapter(self.adapter)

    def tearDown(self):
        _clear_bedrock_env()

    async def test_chat_returns_content_and_usage(self):
        self.adapter._client.invoke_model = MagicMock(
            return_value=_make_ok_chat_response("hi there")
        )
        result = await self.adapter.chat(
            [ChatMessage(role="user", content="say hi")],
            ChatOptions(model="anthropic.claude-3-sonnet-v1:0"),
        )
        self.assertEqual(result.content, "hi there")
        self.assertEqual(result.finish_reason, "stop")
        self.assertIsNotNone(result.usage)

    async def test_chat_raises_when_not_started(self):
        adapter = BedrockAdapter(_make_record())
        adapter.initialize()
        with self.assertRaises(LLMConfigurationError) as ctx:
            await adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="claude"),
            )
        self.assertIn("not been started", str(ctx.exception))

    async def test_chat_auth_failure(self):
        self.adapter._client.invoke_model = MagicMock(
            side_effect=_FakeClientError(
                {"Error": {"Code": "ExpiredTokenException", "Message": "expired"}},
                "InvokeModel",
            )
        )
        with self.assertRaises(LLMAuthenticationError):
            await self.adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="claude"),
            )

    async def test_chat_validation_failure(self):
        self.adapter._client.invoke_model = MagicMock(
            side_effect=_FakeClientError(
                {"Error": {"Code": "ValidationError", "Message": "bad param"}},
                "InvokeModel",
            )
        )
        with self.assertRaises(LLMValidationError):
            await self.adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="claude"),
            )

    async def test_chat_timeout(self):
        self.adapter._client.invoke_model = MagicMock(
            side_effect=_FakeReadTimeoutError(endpoint_url="https://bedrock")
        )
        with self.assertRaises(LLMTimeoutError):
            await self.adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="claude"),
            )

    async def test_chat_unavailable(self):
        self.adapter._client.invoke_model = MagicMock(
            side_effect=_FakeEndpointConnectionError(endpoint_url="https://bedrock")
        )
        with self.assertRaises(LLMUnavailableError):
            await self.adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="claude"),
            )

    async def test_chat_generic_error(self):
        self.adapter._client.invoke_model = MagicMock(
            side_effect=_FakeBotoCoreError()
        )
        with self.assertRaises(LLMProviderError):
            await self.adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="claude"),
            )


# ---------------------------------------------------------------------------
# Chat Streaming
# ---------------------------------------------------------------------------

class TestBedrockAdapterStream(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _clear_bedrock_env()
        _set_bedrock_env()
        self.adapter = BedrockAdapter(_make_record())
        self.adapter.initialize()
        _start_adapter(self.adapter)

    def tearDown(self):
        _clear_bedrock_env()

    async def test_stream_yields_text_chunks(self):
        events = [
            _make_stream_event("he"),
            _make_stream_event("llo"),
            _make_stream_event(" wo"),
            _make_stream_event("rld!"),
        ]
        self.adapter._client.invoke_model_with_response_stream = MagicMock(
            return_value={"body": _FakeEventStream(events)}
        )
        chunks = [
            c async for c in self.adapter.chat_stream(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="anthropic.claude-3-sonnet-v1:0"),
            )
        ]
        self.assertEqual(chunks, ["he", "llo", " wo", "rld!"])

    async def test_stream_error_is_translated(self):
        # When invoke_model_with_response_stream raises, consuming the
        # iterator propagates the error and _translate_boto_error converts it.
        self.adapter._client.invoke_model_with_response_stream = MagicMock(
            side_effect=_FakeReadTimeoutError(endpoint_url="https://bedrock")
        )
        with self.assertRaises(LLMTimeoutError):
            async for _ in self.adapter.chat_stream(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="claude"),
            ):
                pass


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

class TestBedrockAdapterEmbed(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _clear_bedrock_env()
        _set_bedrock_env()
        self.adapter = BedrockAdapter(_make_record())
        self.adapter.initialize()
        _start_adapter(self.adapter)

    def tearDown(self):
        _clear_bedrock_env()

    async def test_embed_titan_returns_embeddings(self):
        self.adapter._client.invoke_model = MagicMock(
            return_value={
                "body": _FakeBody({
                    "embedding": [0.1, 0.2, 0.3],
                    "inputTokenCount": 5,
                })
            }
        )
        result = await self.adapter.embed(
            ["hello world"],
            EmbeddingOptions(model="amazon.titan-embed-text-v1"),
        )
        self.assertEqual(len(result.embeddings), 1)
        self.assertEqual(result.embeddings[0], [0.1, 0.2, 0.3])
        self.assertIsNotNone(result.usage)

    async def test_embed_cohere_returns_embeddings(self):
        self.adapter._client.invoke_model = MagicMock(
            return_value={
                "body": _FakeBody({
                    "embeddings": [[0.4, 0.5]],
                    "tokens": 3,
                })
            }
        )
        result = await self.adapter.embed(
            ["hello"],
            EmbeddingOptions(model="cohere.embed-english-v3"),
        )
        self.assertEqual(len(result.embeddings), 1)

    async def test_embed_unsupported_model_raises_validation(self):
        with self.assertRaises(LLMValidationError):
            await self.adapter.embed(
                ["hello"],
                EmbeddingOptions(model="unknown.model"),
            )

    async def test_embed_auth_failure(self):
        self.adapter._client.invoke_model = MagicMock(
            side_effect=_FakeClientError(
                {"Error": {"Code": "ExpiredTokenException", "Message": "expired"}},
                "InvokeModel",
            )
        )
        with self.assertRaises(LLMAuthenticationError):
            await self.adapter.embed(
                ["hello"],
                EmbeddingOptions(model="amazon.titan-embed-text-v1"),
            )


# ---------------------------------------------------------------------------
# BaseProvider contract
# ---------------------------------------------------------------------------

class TestBedrockAdapterContract(unittest.TestCase):
    def test_provider_id_from_record(self):
        record = _make_record(provider_id="my-bedrock")
        self.assertEqual(BedrockAdapter(record).provider_id, "my-bedrock")

    def test_provider_type_is_bedrock(self):
        self.assertEqual(BedrockAdapter(_make_record()).provider_type, "bedrock")

    def test_capabilities_include_chat_and_embed(self):
        adapter = BedrockAdapter(_make_record())
        self.assertIn(Capability.CHAT, adapter.capabilities)
        self.assertIn(Capability.EMBEDDING, adapter.capabilities)
        self.assertNotIn(Capability.RERANK, adapter.capabilities)
