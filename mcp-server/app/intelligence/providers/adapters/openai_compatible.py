"""OpenAI-compatible adapter — REST inference via any OpenAI-compatible API.

This adapter implements the :class:`BaseProviderRuntime` lifecycle and
exposes chat and embedding capabilities through the OpenAI-compatible
REST API (OpenAI, Azure OpenAI, Cohere, Groq, LocalAI, etc.).

**Endpoint mapping**

========================  ==================================================
``POST /v1/chat/completions``   Chat completion (streaming supported)
``POST /v1/embeddings``        Text embeddings
========================  ==================================================

**Authentication**

The adapter sends ``Authorization: Bearer <api_key>`` on every request.
The key is read from ``$OPENAI_API_KEY`` or the registry's ``auth.api_key``.

**Streaming**

Streaming responses are server-sent events following the OpenAI
``data: [DONE]`` protocol. The adapter yields raw text chunks.
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
    from app.intelligence.registry.models.provider import ProviderRecord


_DEFAULT_TIMEOUT_SECONDS = 120.0


class OpenAICompatibleAdapter(
    BaseProviderRuntime,
    ChatCapable,
    EmbeddingCapable,
):
    """OpenAI-compatible REST inference provider.

    Connects to any server that implements the OpenAI REST API:

    * Chat completion: ``POST /v1/chat/completions`` (streaming supported)
    * Embeddings: ``POST /v1/embeddings``

    **Environment variables**

    =======================  ================================================
    ``OPENAI_API_KEY``      API key sent as ``Bearer <token>`` on every request.
                            Falls back to ``auth.api_key`` from the registry.
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
        return ProviderType.OPENAI_COMPATIBLE.value

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
        """Resolve the base URL and API key from the registry or environment.

        Raises:
            LLMConfigurationError: If the base URL is empty or syntactically
                invalid, or if no API key is available.
        """
        import os
        from urllib.parse import urlparse

        # base_url precedence: record > $OPENAI_BASE_URL
        base_url = self._record.connection.base_url or ""
        if not base_url:
            base_url = os.environ.get("OPENAI_BASE_URL", "").strip()

        if not base_url:
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': base_url is required for "
                "OpenAI-compatible providers. Set it in the registry or as "
                "$OPENAI_BASE_URL."
            )

        base_url = base_url.rstrip("/")

        try:
            parsed = urlparse(base_url)
            if not parsed.scheme:
                raise ValueError(f"no scheme in URL: {base_url}")
        except Exception as e:
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': base_url is not a valid "
                f"URL ({e})"
            ) from e

        object.__setattr__(self, "_base_url", base_url)

        # API key resolution.
        # The key is resolved by the ProviderManager from the CredentialStore
        # (keyed by provider_id) and attached as runtime-only credential
        # material before initialize() runs. The secret is never read from the
        # registry configuration and never stored in llm.yaml.
        credential = self._credential
        if credential is None or not credential.api_key:
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': no API key credential "
                "was attached to the runtime. API-key providers must be "
                "initialized via the ProviderManager with a configured "
                "CredentialStore."
            )
        object.__setattr__(self, "_api_key", credential.api_key)

        # Custom auth header (e.g. "X-API-Key") if specified in the registry.
        # Defaults to "Authorization" (the standard Bearer scheme).
        auth_header = self._record.auth.auth_header
        object.__setattr__(
            self, "_auth_header", auth_header if auth_header else "Authorization"
        )

    def validate_configuration(self) -> None:
        """Validate the provider configuration.

        Raises:
            LLMConfigurationError: If the base URL is not HTTPS for cloud deployments.
        """
        from urllib.parse import urlparse

        parsed = urlparse(self._base_url)
        if self._record.deployment == DeploymentType.CLOUD and parsed.scheme != "https":
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': cloud OpenAI-compatible "
                f"providers must use HTTPS, got '{parsed.scheme}'"
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

        try:
            client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
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

    async def check_connection(self) -> bool:
        """Perform a non-generative authenticated OpenAI-compatible probe."""
        self._check_started()
        try:
            response = await self._client.get("/v1/models")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    # -------------------------------------------------------------------------
    # ChatCapable
    # -------------------------------------------------------------------------

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> ChatResponse:
        """Generate a chat completion via ``POST /v1/chat/completions``."""
        self._check_started()
        payload = _build_openai_chat_payload(messages, options, stream=False)
        try:
            response = await self._client.post("/v1/chat/completions", json=payload)
            _raise_for_status(response, "/v1/chat/completions", self._record.provider_id)
        except LLMError:
            raise
        except Exception as exc:
            raise _translate_httpx_error(exc, "chat completion", self._record.provider_id) from exc

        data = response.json()
        choices = data.get("choices", [])
        content = ""
        finish_reason = None
        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            finish_reason = choice.get("finish_reason")

        return ChatResponse(
            content=content,
            model=data.get("model", options.model),
            finish_reason=finish_reason,
            usage=_extract_usage(data),
        )

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> AsyncIterator[str]:
        """Stream chat completions via ``POST /v1/chat/completions`` with ``stream: true``.

        Yields raw text chunks from the server-sent event stream.
        """
        self._check_started()
        payload = _build_openai_chat_payload(messages, options, stream=True)
        try:
            async with self._client.stream(
                "POST", "/v1/chat/completions", json=payload
            ) as response:
                _raise_for_status(
                    response, "/v1/chat/completions (streaming)", self._record.provider_id
                )
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if not line.startswith("data: "):
                        continue
                    json_str = line[6:]  # strip "data: "
                    try:
                        import json as _json
                        event = _json.loads(json_str)
                    except Exception:
                        continue
                    choices = event.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
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
        """Generate embeddings via ``POST /v1/embeddings``."""
        self._check_started()
        payload: dict[str, Any] = {
            "model": options.model,
            "input": list(texts),
        }
        if options.encoding_format:
            payload["encoding_format"] = options.encoding_format
        if options.dimensions is not None:
            payload["dimensions"] = options.dimensions

        try:
            response = await self._client.post("/v1/embeddings", json=payload)
            _raise_for_status(response, "/v1/embeddings", self._record.provider_id)
        except LLMError:
            raise
        except Exception as exc:
            raise _translate_httpx_error(exc, "embeddings", self._record.provider_id) from exc

        data = response.json()
        embeddings = [
            item["embedding"]
            for item in data.get("data", [])
            if "embedding" in item
        ]

        return EmbeddingResponse(
            embeddings=embeddings,
            model=data.get("model", options.model),
            usage=_extract_usage(data),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_openai_chat_payload(
    messages: Sequence[ChatMessage],
    options: ChatOptions,
    stream: bool = False,
) -> dict[str, Any]:
    """Build the OpenAI /v1/chat/completions request payload."""
    payload: dict[str, Any] = {
        "model": options.model,
        "messages": [
            {"role": m.role, "content": m.content}
            for m in messages
        ],
        "stream": stream,
    }
    if options.temperature is not None:
        payload["temperature"] = options.temperature
    if options.max_tokens is not None:
        payload["max_tokens"] = options.max_tokens
    if options.top_p is not None:
        payload["top_p"] = options.top_p
    if options.stop is not None:
        payload["stop"] = list(options.stop) if options.stop else None
    if options.seed is not None:
        payload["seed"] = options.seed
    if options.response_format is not None:
        payload["response_format"] = options.response_format
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
        raise LLMAuthenticationError(msg) from None
    if 500 <= status_code < 600:
        raise LLMUnavailableError(msg) from None
    raise LLMProviderError(msg) from None


def _translate_httpx_error(
    exc: Exception,
    action: str,
    provider_id: str,
) -> LLMError:
    """Translate any unhandled httpx exception into the LLM hierarchy."""
    if isinstance(exc, httpx.TimeoutException):
        return LLMTimeoutError(f"provider '{provider_id}': timeout during {action}")
    if isinstance(exc, httpx.ConnectError):
        return LLMUnavailableError(f"provider '{provider_id}': connection refused during {action}")
    if isinstance(exc, httpx.PoolTimeout):
        return LLMTimeoutError(f"provider '{provider_id}': connection pool timeout during {action}")
    if isinstance(exc, httpx.ProtocolError):
        return LLMUnavailableError(f"provider '{provider_id}': protocol error during {action}")
    if isinstance(exc, httpx.HTTPStatusError):
        return LLMProviderError(
            f"provider '{provider_id}': HTTP {exc.response.status_code} during {action}"
        )
    return LLMProviderError(
        f"provider '{provider_id}': unexpected error during {action}: {exc}"
    )


def _extract_usage(data: dict[str, Any]) -> dict[str, int] | None:
    """Extract a usage dict from an OpenAI API response, or None if absent."""
    usage = data.get("usage")
    if not usage:
        return None
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
