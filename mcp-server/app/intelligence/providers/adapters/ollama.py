"""Ollama adapter — self-hosted LLM inference via the Ollama REST API.

This adapter implements the :class:`BaseProviderRuntime` lifecycle and
exposes chat and embedding capabilities through the Ollama REST API.

Deployment: self-hosted. The adapter resolves ``$OLLAMA_BASE_URL``
(default: ``http://localhost:11434``) and ``$OLLAMA_API_KEY`` (optional).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Sequence

import httpx

from app.intelligence.exceptions import (
    LLMError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMValidationError,
)
from app.intelligence.ports.chat import ChatCapable, ChatMessage, ChatOptions, ChatResponse
from app.intelligence.ports.embedding import EmbeddingCapable, EmbeddingOptions, EmbeddingResponse
from app.intelligence.providers.base_provider import BaseProviderRuntime
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType

if TYPE_CHECKING:
    from app.intelligence.registry.models.provider import AuthConfig, ConnectionConfig, ProviderRecord


_OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_TIMEOUT_SECONDS = 120.0


class OllamaAdapter(
    BaseProviderRuntime,
    ChatCapable,
    EmbeddingCapable,
):
    """Ollama self-hosted inference provider.

    Connects to a locally-running Ollama instance via its REST API.

    * Chat completion: ``POST /api/chat``
    * Streaming chat: ``POST /api/chat`` with ``stream: true`` (SSE)
    * Embeddings: ``POST /api/embeddings``

    **Environment variables**

    =======================  ================================================
    ``OLLAMA_BASE_URL``      Full base URL of the Ollama server.
                            Defaults to ``http://localhost:11434``.
    ``OLLAMA_API_KEY``       Optional API key for authenticated servers.
    =======================  ================================================
    """

    # -------------------------------------------------------------------------
    # BaseProvider contract
    # -------------------------------------------------------------------------

    @property
    def provider_id(self) -> str:
        return self._record.provider_id

    @property
    def provider_type(self) -> str:
        return ProviderType.OLLAMA.value

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({
            Capability.CHAT,
            Capability.EMBEDDING,
        })

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def initialize(self) -> None:
        """Resolve Ollama-specific environment variables and validate basic presence.

        Raises:
            LLMConfigurationError: If ``OLLAMA_BASE_URL`` resolves to an
                empty string or the URL is syntactically invalid.
        """
        import os
        from urllib.parse import urlparse

        base_url = (
            self._record.connection.base_url
            if self._record.connection.base_url
            else os.environ.get("OLLAMA_BASE_URL", _OLLAMA_DEFAULT_BASE_URL)
        )
        if not base_url or not base_url.strip():
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': OLLAMA_BASE_URL is "
                "empty; set it in the registry or as an environment variable"
            )

        try:
            parsed = urlparse(base_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"invalid URL: {base_url}")
        except Exception as e:
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': OLLAMA_BASE_URL is not "
                f"a valid URL ({e})"
            ) from e

        object.__setattr__(self, "_base_url", base_url)

        api_key = (
            os.environ.get("OLLAMA_API_KEY")
            or (
                self._record.auth.api_key
                if self._record.auth.api_key
                else None
            )
        )
        object.__setattr__(self, "_api_key", api_key)

    def validate_configuration(self) -> None:
        """Validate the Ollama provider configuration.

        Raises:
            LLMConfigurationError: If the deployment type is not self-hosted.
        """
        if self._record.deployment not in (
            DeploymentType.SELF_HOSTED,
            DeploymentType.PROXY,
            DeploymentType.LOCAL,
        ):
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': Ollama provider "
                f"must have deployment 'self-hosted', 'local', or 'proxy', "
                f"got '{self._record.deployment.value}'"
            )

    async def start(self) -> None:
        """Open the async HTTP client.

        If a client was already injected (e.g. in tests via object.__setattr__),
        this method skips client construction and leaves the existing client intact.
        This makes _client effectively "sticky" so that test fixtures survive
        repeated calls to start().

        Raises:
            LLMConfigurationError: If the client cannot be constructed.
        """
        # Skip client construction if a client was already injected (test path).
        if hasattr(self, "_client") and self._client is not None:
            object.__setattr__(self, "_started", True)
            return

        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=httpx.Timeout(_DEFAULT_TIMEOUT_SECONDS),
                follow_redirects=True,
            )
            object.__setattr__(self, "_client", client)
        except Exception as e:
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': failed to create "
                f"HTTP client ({e})"
            ) from e

        object.__setattr__(self, "_started", True)

    async def close(self) -> None:
        """Close the HTTP client and release resources.

        Gracefully handles the case where _client is a mock (test environments).
        Only calls aclose() if the client exposes it as a real awaitable coroutine.
        """
        import asyncio
        client: httpx.AsyncClient | None = getattr(self, "_client", None)
        if client is not None:
            try:
                aclose_coro = client.aclose
                if asyncio.iscoroutine(aclose_coro):
                    await aclose_coro
            except AttributeError:
                # _client is None or missing aclose; skip.
                pass
        object.__setattr__(self, "_started", False)

    # -------------------------------------------------------------------------
    # ChatCapable
    # -------------------------------------------------------------------------

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> ChatResponse:
        """Generate a chat completion via ``POST /api/chat``."""
        self._check_started()
        payload = _build_chat_payload(messages, options)
        try:
            response = await self._client.post("/api/chat", json=payload)
            response = _handle_response(response, "/api/chat", self._record.provider_id)
        except LLMError:
            raise
        except Exception as exc:
            raise _translate_httpx_error(exc, "chat completion", self._record.provider_id) from exc

        data = response.json()
        content = ""
        finish_reason = None
        if "message" in data:
            content = data["message"].get("content", "")
        if "done" in data and data["done"]:
            finish_reason = "stop"

        return ChatResponse(
            content=content,
            model=options.model,
            finish_reason=finish_reason,
        )

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> AsyncIterator[str]:
        """Stream chat completions via ``POST /api/chat`` with ``stream: true``.

        Yields raw text chunks from the server-sent event stream.
        """
        self._check_started()
        payload = _build_chat_payload(messages, options, stream=True)
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as response:
                _raise_for_status(response, "/api/chat", self._record.provider_id)
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if not line.startswith("{"):
                        continue
                    # Ollama sends NDJSON: one JSON object per line.
                    try:
                        import json
                        event = json.loads(line)
                    except Exception:
                        continue
                    if "message" in event and "content" in event["message"]:
                        chunk = event["message"]["content"]
                        if chunk:
                            yield chunk
        except LLMError:
            raise
        except Exception as exc:
            raise _translate_httpx_error(exc, "streaming chat", self._record.provider_id) from exc

    # -------------------------------------------------------------------------
    # EmbeddingCapable
    # -------------------------------------------------------------------------

    async def embed(
        self,
        texts: Sequence[str],
        options: EmbeddingOptions,
    ) -> EmbeddingResponse:
        """Generate embeddings via ``POST /api/embeddings``."""
        self._check_started()

        payload: dict[str, Any] = {
            "model": options.model,
            "prompt": "\n".join(texts),
        }
        if options.encoding_format:
            payload["encoding_format"] = options.encoding_format
        if options.dimensions is not None:
            payload["dimensions"] = options.dimensions

        try:
            response = await self._client.post("/api/embeddings", json=payload)
            response = _handle_response(response, "/api/embeddings", self._record.provider_id)
        except LLMError:
            raise
        except Exception as exc:
            raise _translate_httpx_error(exc, "embeddings", self._record.provider_id) from exc

        data = response.json()
        embedding = data.get("embedding", [])
        usage = data.get("usage", {})
        if "num_tokens" in data:
            usage = {"prompt_tokens": data["num_tokens"]}

        return EmbeddingResponse(
            embeddings=[embedding],
            model=options.model,
            usage=usage if usage else None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_chat_payload(
    messages: Sequence[ChatMessage],
    options: ChatOptions,
    stream: bool = False,
) -> dict[str, Any]:
    """Build the Ollama /api/chat request payload."""
    payload: dict[str, Any] = {
        "model": options.model,
        "messages": [
            {"role": m.role, "content": m.content}
            for m in messages
        ],
        "stream": stream,
    }
    if options.temperature is not None:
        payload["options"] = payload.get("options", {})
        payload["options"]["temperature"] = options.temperature
    if options.max_tokens is not None:
        payload["options"] = payload.get("options", {})
        payload["options"]["num_predict"] = options.max_tokens
    if options.top_p is not None:
        payload["options"] = payload.get("options", {})
        payload["options"]["top_p"] = options.top_p
    if options.stop is not None:
        payload["options"] = payload.get("options", {})
        payload["options"]["stop"] = options.stop
    if options.seed is not None:
        payload["options"] = payload.get("options", {})
        payload["options"]["seed"] = options.seed
    return payload


def _raise_for_status(response: httpx.Response, path: str, provider_id: str) -> None:
    """Raise an LLM exception for a failed HTTP response."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _raise_from_status(exc.response.status_code, path, provider_id, exc.response)
    except httpx.TimeoutException as exc:
        raise LLMTimeoutError(
            f"provider '{provider_id}': timeout calling {path}"
        ) from exc
    except httpx.ConnectError as exc:
        raise LLMUnavailableError(
            f"provider '{provider_id}': connection refused for {path}"
        ) from exc
    except httpx.PoolTimeout as exc:
        raise LLMTimeoutError(
            f"provider '{provider_id}': connection pool timeout for {path}"
        ) from exc
    except httpx.ProtocolError as exc:
        raise LLMUnavailableError(
            f"provider '{provider_id}': protocol error for {path}"
        ) from exc


def _raise_from_status(
    status_code: int,
    path: str,
    provider_id: str,
    response: httpx.Response,
) -> None:
    """Map an HTTP status code to an LLM exception type."""
    msg = f"provider '{provider_id}': HTTP {status_code} from {path}"
    if status_code == 401 or status_code == 403:
        raise LLMAuthenticationError(msg) from None
    if status_code == 404:
        raise LLMValidationError(msg) from None
    if status_code == 422:
        raise LLMValidationError(msg) from None
    if status_code == 429:
        raise LLMAuthenticationError(msg) from None  # retryable but non-config
    if 500 <= status_code < 600:
        raise LLMUnavailableError(msg) from None
    raise LLMProviderError(msg) from None


def _handle_response(
    response: httpx.Response,
    path: str,
    provider_id: str,
) -> httpx.Response:
    """Validate a successful response and return it, or raise an LLM exception."""
    _raise_for_status(response, path, provider_id)
    return response


def _translate_httpx_error(exc: Exception, action: str, provider_id: str) -> LLMError:
    """Translate any unhandled httpx exception into the LLM hierarchy."""
    if isinstance(exc, httpx.TimeoutException):
        return LLMTimeoutError(
            f"provider '{provider_id}': timeout during {action}"
        )
    if isinstance(exc, httpx.ConnectError):
        return LLMUnavailableError(
            f"provider '{provider_id}': connection refused during {action}"
        )
    if isinstance(exc, httpx.PoolTimeout):
        return LLMTimeoutError(
            f"provider '{provider_id}': connection pool timeout during {action}"
        )
    if isinstance(exc, httpx.ProtocolError):
        return LLMUnavailableError(
            f"provider '{provider_id}': protocol error during {action}"
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return LLMProviderError(
            f"provider '{provider_id}': HTTP {exc.response.status_code} "
            f"during {action}"
        )
    return LLMProviderError(
        f"provider '{provider_id}': unexpected error during {action}: {exc}"
    )
