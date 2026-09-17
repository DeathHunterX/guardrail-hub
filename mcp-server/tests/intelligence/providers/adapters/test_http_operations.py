"""HTTP request, streaming, embedding, and error contracts for adapters."""

import httpx
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.intelligence.exceptions import (
    LLMConfigurationError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMValidationError,
)
from app.intelligence.ports.chat import ChatMessage, ChatOptions
from app.intelligence.ports.embedding import EmbeddingOptions
from app.intelligence.registry.models.provider import (
    AuthConfig,
    AuthType,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ollama_record(
    provider_id: str = "test_ollama",
    base_url: str = "http://localhost:11434",
    deployment: DeploymentType = DeploymentType.SELF_HOSTED,
) -> ProviderRecord:
    return ProviderRecord(
        provider_id=provider_id,
        provider_type=ProviderType.OLLAMA,
        deployment=deployment,
        auth=AuthConfig(type=AuthType.NONE),
        connection=ConnectionConfig(base_url=base_url),
        capabilities=frozenset({Capability.CHAT, Capability.EMBEDDING}),
        enabled=True,
        priority=10,
    )


def _make_openai_record(
    provider_id: str = "test_openai",
    base_url: str = "https://api.openai.com/v1",
) -> ProviderRecord:
    return ProviderRecord(
        provider_id=provider_id,
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(type=AuthType.API_KEY),
        connection=ConnectionConfig(base_url=base_url),
        capabilities=frozenset({Capability.CHAT, Capability.EMBEDDING}),
        enabled=True,
        priority=20,
    )


# ---------------------------------------------------------------------------
# OllamaAdapter — chat
# ---------------------------------------------------------------------------

class TestOllamaAdapterChat(unittest.IsolatedAsyncioTestCase):
    async def test_chat_returns_response(self):
        record = _make_ollama_record()
        adapter = _build_ollama_adapter(record)
        _start_ollama_adapter(adapter)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "hello world"},
            "done": True,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter._client, "post", new=AsyncMock(return_value=mock_response)):
            response = await adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="llama3"),
            )

        self.assertEqual(response.content, "hello world")
        self.assertEqual(response.model, "llama3")
        self.assertEqual(response.finish_reason, "stop")

    async def test_chat_translates_404_to_validation_error(self):
        record = _make_ollama_record()
        adapter = _build_ollama_adapter(record)
        _start_ollama_adapter(adapter)

        mock_response = MagicMock()
        mock_response.status_code = 404
        # _raise_for_status catches HTTPStatusError → _raise_from_status → LLMValidationError
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "HTTP 404", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(
            adapter._client, "post", new=AsyncMock(return_value=mock_response)
        ):
            with self.assertRaises(LLMValidationError):
                await adapter.chat(
                    [ChatMessage(role="user", content="hi")],
                    ChatOptions(model="nonexistent"),
                )

    async def test_chat_raises_when_unstarted(self):
        record = _make_ollama_record()
        adapter = _build_ollama_adapter(record)
        adapter.initialize()
        with self.assertRaises(LLMConfigurationError) as ctx:
            await adapter.chat(
                [ChatMessage(role="user", content="hi")],
                ChatOptions(model="llama3"),
            )
        self.assertIn("not been started", str(ctx.exception))


# ---------------------------------------------------------------------------
# OllamaAdapter — streaming
# ---------------------------------------------------------------------------

class TestOllamaAdapterStream(unittest.IsolatedAsyncioTestCase):
    async def test_chat_stream_yields_chunks(self):
        record = _make_ollama_record()
        adapter = _build_ollama_adapter(record)
        _start_ollama_adapter(adapter)

        mock_response = _make_stream_response(
            ['{"message":{"content":"hel"}}', '{"message":{"content":"lo"}}', '{"done":true}']
        )

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        adapter._client.stream = MagicMock(return_value=mock_ctx)

        chunks = [c async for c in adapter.chat_stream(
            [ChatMessage(role="user", content="hi")],
            ChatOptions(model="llama3"),
        )]
        self.assertEqual(chunks, ["hel", "lo"])


# ---------------------------------------------------------------------------
# OllamaAdapter — embeddings
# ---------------------------------------------------------------------------

class TestOllamaAdapterEmbed(unittest.IsolatedAsyncioTestCase):
    async def test_embed_returns_response(self):
        record = _make_ollama_record()
        adapter = _build_ollama_adapter(record)
        _start_ollama_adapter(adapter)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embedding": [0.1, 0.2, 0.3],
            "num_tokens": 5,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            adapter._client, "post", new=AsyncMock(return_value=mock_response)
        ):
            response = await adapter.embed(
                ["hello world"],
                EmbeddingOptions(model="nomic-embed-text"),
            )

        self.assertEqual(len(response.embeddings), 1)
        self.assertEqual(response.embeddings[0], [0.1, 0.2, 0.3])
        self.assertEqual(response.model, "nomic-embed-text")
        self.assertEqual(response.usage, {"prompt_tokens": 5})


# ---------------------------------------------------------------------------
# OpenAICompatibleAdapter — chat
# ---------------------------------------------------------------------------

class TestOpenAIAdapterChat(unittest.IsolatedAsyncioTestCase):
    async def test_chat_returns_response(self):
        record = _make_openai_record()
        adapter = _build_openai_adapter(record)
        _start_openai_adapter(adapter)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "gpt-4o",
            "choices": [
                {"message": {"content": "42 is the answer"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            adapter._client, "post", new=AsyncMock(return_value=mock_response)
        ):
            response = await adapter.chat(
                [ChatMessage(role="user", content="what is 6 * 7?")],
                ChatOptions(model="gpt-4o"),
            )

        self.assertEqual(response.content, "42 is the answer")
        self.assertEqual(response.model, "gpt-4o")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.usage, {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8})

    async def test_chat_stream_yields_chunks(self):
        record = _make_openai_record()
        adapter = _build_openai_adapter(record)
        _start_openai_adapter(adapter)

        mock_response = _make_stream_response([
            'data: {"choices":[{"delta":{"content":"he"}}]}',
            'data: {"choices":[{"delta":{"content":"llo"}}]}',
            "data: [DONE]",
        ])

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        adapter._client.stream = MagicMock(return_value=mock_ctx)

        chunks = [c async for c in adapter.chat_stream(
            [ChatMessage(role="user", content="hi")],
            ChatOptions(model="gpt-4o"),
        )]
        self.assertEqual(chunks, ["he", "llo"])


# ---------------------------------------------------------------------------
# OpenAICompatibleAdapter — embeddings
# ---------------------------------------------------------------------------

class TestOpenAIAdapterEmbed(unittest.IsolatedAsyncioTestCase):
    async def test_embed_returns_response(self):
        record = _make_openai_record()
        adapter = _build_openai_adapter(record)
        _start_openai_adapter(adapter)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "text-embedding-3-small",
            "data": [
                {"embedding": [0.9, 0.1], "index": 0},
                {"embedding": [0.5, 0.5], "index": 1},
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 0, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            adapter._client, "post", new=AsyncMock(return_value=mock_response)
        ):
            response = await adapter.embed(
                ["hello", "world"],
                EmbeddingOptions(model="text-embedding-3-small"),
            )

        self.assertEqual(len(response.embeddings), 2)
        self.assertEqual(response.embeddings[0], [0.9, 0.1])
        self.assertEqual(response.usage, {"prompt_tokens": 8, "completion_tokens": 0, "total_tokens": 8})


# ---------------------------------------------------------------------------
# Shared error-translation tests
# ---------------------------------------------------------------------------

class TestErrorTranslation(unittest.IsolatedAsyncioTestCase):
    async def test_ollama_chat_timeout_becomes_LLMTimeoutError(self):
        record = _make_ollama_record()
        adapter = _build_ollama_adapter(record)
        _start_ollama_adapter(adapter)

        # _handle_response catches httpx.TimeoutException and re-raises as LLMTimeoutError.
        # Patch raise_for_status to raise the mock exception inside the handler.
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.TimeoutException("timed out")
        )

        with patch.object(
            adapter._client, "post", new=AsyncMock(return_value=mock_response)
        ):
            with self.assertRaises(LLMTimeoutError) as ctx:
                await adapter.chat(
                    [ChatMessage(role="user", content="hi")],
                    ChatOptions(model="llama3"),
                )
        self.assertIn("timeout", str(ctx.exception).lower())

    async def test_ollama_chat_connect_error_becomes_LLMUnavailableError(self):
        record = _make_ollama_record()
        adapter = _build_ollama_adapter(record)
        _start_ollama_adapter(adapter)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with patch.object(
            adapter._client, "post", new=AsyncMock(return_value=mock_response)
        ):
            with self.assertRaises(LLMUnavailableError) as ctx:
                await adapter.chat(
                    [ChatMessage(role="user", content="hi")],
                    ChatOptions(model="llama3"),
                )
        self.assertIn("connection refused", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# Internal test helpers
# ---------------------------------------------------------------------------

def _build_ollama_adapter(record: ProviderRecord):
    from app.intelligence.providers.adapters.ollama import OllamaAdapter
    return OllamaAdapter(record)


def _build_openai_adapter(record: ProviderRecord):
    from app.intelligence.providers.adapters.openai_compatible import OpenAICompatibleAdapter
    return OpenAICompatibleAdapter(record)


def _start_adapter(adapter):
    mock_client = MagicMock()
    mock_client.aclose = AsyncMock()
    object.__setattr__(adapter, "_client", mock_client)
    object.__setattr__(adapter, "_started", True)


def _start_ollama_adapter(adapter):
    _start_adapter(adapter)


def _start_openai_adapter(adapter):
    _start_adapter(adapter)


def _make_stream_response(lines: list[str]):
    """Return a mock httpx response with aiter_lines yielding given lines."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_aiter_lines():
        for line in lines:
            yield line

    mock_response.aiter_lines = mock_aiter_lines
    mock_response.raise_for_status = MagicMock()
    return mock_response


if __name__ == "__main__":
    unittest.main()
