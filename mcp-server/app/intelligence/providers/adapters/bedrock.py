"""AWS Bedrock adapter — inference via AWS Bedrock runtime API.

This adapter implements the :class:`BaseProviderRuntime` lifecycle and
exposes chat and embedding capabilities through the AWS Bedrock runtime.

Deployment: cloud. The adapter resolves AWS credentials and region from
environment variables following the standard AWS SDK credential chain.

**Environment variables**

=========================  ======================================================
``AWS_ACCESS_KEY_ID``       AWS access key ID.
``AWS_SECRET_ACCESS_KEY``   AWS secret access key.
``AWS_SESSION_TOKEN``       Optional session token for temporary credentials.
``AWS_REGION``              AWS region (e.g., ``us-east-1``).
                            Required unless ``AWS_DEFAULT_REGION`` is set.
``AWS_DEFAULT_REGION``      Alias for ``AWS_REGION`` (AWS SDK standard).
=========================  ======================================================

**Supported model families**

Chat: Anthropic Claude models (``us.anthropic.claude-*``) via
``bedrock-runtime.invoke_model``.

Streaming: ``bedrock-runtime.invoke_model_with_response_stream`` using
the Bedrock response-stream protocol (base64-encoded event chunks).

Embedding: Amazon Titan (``amazon.titan-*``) and Cohere (``cohere.*``)
models via ``bedrock-runtime.invoke_model``.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
from typing import TYPE_CHECKING, Any, AsyncIterator

import boto3

from app.intelligence.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitedError,
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


# Regional Bedrock runtime endpoint.
_BEDROCK_ENDPOINT_TEMPLATE = "https://bedrock-runtime.{region}.amazonaws.com"

# Timeout for boto3 calls, in seconds.
_BOTO_TIMEOUT_SECONDS = 120

# Supported embedding model prefixes.
_TITAN_EMBED_PREFIX = "amazon.titan-"
_COHERE_EMBED_PREFIX = "cohere."


class BedrockAdapter(
    BaseProviderRuntime,
    ChatCapable,
    EmbeddingCapable,
):
    """AWS Bedrock inference provider.

    Connects to the Bedrock runtime using AWS credentials from environment
    variables. Supports chat completion (Anthropic Claude models) and
    embeddings (Amazon Titan, Cohere).
    """

    # -------------------------------------------------------------------------
    # BaseProvider contract
    # -------------------------------------------------------------------------

    @property
    def provider_id(self) -> str:
        return self._record.provider_id

    @property
    def provider_type(self) -> str:
        return ProviderType.BEDROCK.value

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
        """Resolve AWS credentials and region from the environment.

        Raises:
            LLMConfigurationError: If ``AWS_REGION`` or credentials are missing.
        """
        import os

        # Region: $AWS_REGION → $AWS_DEFAULT_REGION → raise.
        region = (
            os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
        )
        if not region or not region.strip():
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': AWS_REGION is not set. "
                "Set AWS_REGION (or AWS_DEFAULT_REGION) as an environment variable."
            )

        if not _is_valid_aws_region(region):
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': AWS_REGION '{region}' "
                "does not look like a valid AWS region identifier"
            )

        object.__setattr__(self, "_region", region)
        object.__setattr__(
            self,
            "_endpoint",
            _BEDROCK_ENDPOINT_TEMPLATE.format(region=region),
        )

        # Credentials.
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        session_token = os.environ.get("AWS_SESSION_TOKEN")

        if not access_key or not access_key.strip():
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': AWS_ACCESS_KEY_ID is not set. "
                "Set it as an environment variable."
            )
        if not secret_key or not secret_key.strip():
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': AWS_SECRET_ACCESS_KEY is not set. "
                "Set it as an environment variable."
            )

        object.__setattr__(self, "_access_key", access_key)
        object.__setattr__(self, "_secret_key", secret_key)
        object.__setattr__(self, "_session_token", session_token)

    def validate_configuration(self) -> None:
        """Validate the Bedrock provider configuration.

        Raises:
            LLMConfigurationError: If the deployment is not ``cloud``.
        """
        if self._record.deployment != DeploymentType.CLOUD:
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': Bedrock provider "
                f"must have deployment 'cloud', got '{self._record.deployment.value}'"
            )

    async def start(self) -> None:
        """Construct the boto3 Bedrock Runtime client.

        If a client was already injected (e.g. in tests via object.__setattr__),
        this method skips client construction and leaves the existing client
        intact. This makes _client effectively "sticky" so that test fixtures
        survive repeated calls to start(), matching the behaviour of the
        Ollama and OpenAI-compatible adapters.

        Raises:
            LLMConfigurationError: If the client cannot be created.
        """
        # Skip client construction if a client was already injected (test path).
        if getattr(self, "_client", None) is not None:
            object.__setattr__(self, "_started", True)
            return

        try:
            session_kwargs: dict[str, Any] = {
                "aws_access_key_id": self._access_key,
                "aws_secret_access_key": self._secret_key,
                "region_name": self._region,
            }
            if self._session_token:
                session_kwargs["aws_session_token"] = self._session_token

            session = boto3.Session(**session_kwargs)
            client = session.client(
                "bedrock-runtime",
                endpoint_url=_BEDROCK_ENDPOINT_TEMPLATE.format(region=self._region),
                config=boto3.session.Config(
                    connect_timeout=_BOTO_TIMEOUT_SECONDS,
                    read_timeout=_BOTO_TIMEOUT_SECONDS,
                ),
            )
            object.__setattr__(self, "_client", client)
        except Exception as e:
            raise LLMConfigurationError(
                f"provider '{self._record.provider_id}': failed to create "
                f"boto3 Bedrock client ({e})"
            ) from e

        object.__setattr__(self, "_started", True)

    async def close(self) -> None:
        """Close the boto3 client (no-op: boto3 clients require no explicit close)."""
        object.__setattr__(self, "_started", False)

    # -------------------------------------------------------------------------
    # ChatCapable
    # -------------------------------------------------------------------------

    async def chat(
        self,
        messages: list[ChatMessage],
        options: ChatOptions,
    ) -> ChatResponse:
        """Generate a chat completion via ``bedrock-runtime.invoke_model``.

        Raises:
            LLMConfigurationError: If the provider has not been started.
            LLMAuthenticationError: Invalid or expired AWS credentials.
            LLMTimeoutError: Request timed out.
            LLMValidationError: Invalid request parameters or model.
            LLMUnavailableError: Service unavailable.
            LLMProviderError: Unexpected SDK error.
        """
        self._check_started()

        payload = _build_anthropic_payload(messages, options)

        try:
            raw_response = await asyncio.to_thread(
                self._client.invoke_model,
                modelId=options.model,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload),
            )
            response_body = json.loads(raw_response["body"].read())
        except Exception as exc:
            raise _translate_boto_error(exc, self.provider_id) from exc

        content = _parse_anthropic_response(response_body, options.model)
        usage = _extract_anthropic_usage(response_body)
        finish_reason = _extract_finish_reason(response_body)

        return ChatResponse(
            content=content,
            model=options.model,
            finish_reason=finish_reason,
            usage=usage,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        options: ChatOptions,
    ) -> AsyncIterator[str]:
        """Stream chat completions via ``bedrock-runtime.invoke_model_with_response_stream``.

        Yields raw text chunks as they arrive from the Bedrock response stream.

        Raises:
            LLMConfigurationError: If the provider has not been started.
            LLMAuthenticationError: Invalid or expired AWS credentials.
            LLMTimeoutError: Request timed out.
            LLMValidationError: Invalid request parameters or model.
            LLMUnavailableError: Service unavailable.
            LLMProviderError: Unexpected SDK error.
        """
        self._check_started()

        payload = _build_anthropic_payload(messages, options, stream=True)

        try:
            response = await asyncio.to_thread(
                self._client.invoke_model_with_response_stream,
                modelId=options.model,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload),
            )
            event_stream = response["body"]
        except Exception as exc:
            raise _translate_boto_error(exc, self.provider_id) from exc

        for raw_event in event_stream:
            chunk_text = _parse_stream_event(raw_event)
            if chunk_text is not None:
                yield chunk_text

    # -------------------------------------------------------------------------
    # EmbeddingCapable
    # -------------------------------------------------------------------------

    async def embed(
        self,
        texts: list[str],
        options: EmbeddingOptions,
    ) -> EmbeddingResponse:
        """Generate embeddings via ``bedrock-runtime.invoke_model``.

        Supports Amazon Titan (``amazon.titan-*``) and Cohere (``cohere.*``) models.

        Raises:
            LLMConfigurationError: If the provider has not been started.
            LLMValidationError: Unsupported embedding model family.
            LLMAuthenticationError: Invalid or expired AWS credentials.
            LLMTimeoutError: Request timed out.
            LLMUnavailableError: Service unavailable.
            LLMProviderError: Unexpected SDK error.
        """
        self._check_started()

        payload = _build_embedding_payload(texts, options)

        try:
            raw_response = await asyncio.to_thread(
                self._client.invoke_model,
                modelId=options.model,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload),
            )
            response_body = json.loads(raw_response["body"].read())
        except Exception as exc:
            raise _translate_boto_error(exc, self.provider_id) from exc

        embeddings, usage = _parse_embedding_response(response_body, options.model)

        return EmbeddingResponse(
            embeddings=embeddings,
            model=options.model,
            usage=usage,
        )


# ---------------------------------------------------------------------------
# Internal helpers — payload construction
# ---------------------------------------------------------------------------

def _build_anthropic_payload(
    messages: list[ChatMessage],
    options: ChatOptions,
    stream: bool = False,
) -> dict[str, Any]:
    """Build the Anthropic-in-Bedrock request body.

    Uses the Anthropic Claude Messages API format supported by Bedrock.
    """
    role_map = {
        "system": "system",
        "user": "user",
        "assistant": "assistant",
    }

    anthropic_messages: list[dict[str, Any]] = [
        {"role": role_map.get(m.role, m.role), "content": m.content}
        for m in messages
    ]

    payload: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": anthropic_messages,
        "stream": stream,
    }

    if options.temperature is not None:
        payload["temperature"] = options.temperature
    if options.max_tokens is not None:
        payload["max_tokens"] = options.max_tokens
    else:
        payload["max_tokens"] = 4096
    if options.top_p is not None:
        payload["top_p"] = options.top_p
    if options.stop is not None:
        payload["stop_sequences"] = list(options.stop)
    if options.seed is not None:
        payload["random_seed"] = options.seed

    return payload


def _build_embedding_payload(
    texts: list[str],
    options: EmbeddingOptions,
) -> dict[str, Any]:
    """Build the correct embedding request body based on the model family."""
    model = options.model

    if model.startswith(_TITAN_EMBED_PREFIX):
        return _build_titan_payload(texts, options)
    elif model.startswith(_COHERE_EMBED_PREFIX):
        return _build_cohere_payload(texts, options)
    else:
        raise LLMValidationError(
            f"unsupported embedding model '{model}' on Bedrock: "
            f"expected amazon.titan-* or cohere.* prefix"
        )


def _build_titan_payload(
    texts: list[str],
    options: EmbeddingOptions,
) -> dict[str, Any]:
    """Build an Amazon Titan embedding request body."""
    payload: dict[str, Any] = {
        "inputText": "\n".join(texts),
    }
    if options.encoding_format:
        payload["embeddingConfig"] = {"outputDataType": options.encoding_format}
    return payload


def _build_cohere_payload(
    texts: list[str],
    options: EmbeddingOptions,
) -> dict[str, Any]:
    """Build a Cohere embedding request body for Bedrock."""
    payload: dict[str, Any] = {
        "texts": list(texts),
    }
    if options.dimensions is not None:
        payload["input_type"] = "search_document"
        payload["dimensions"] = options.dimensions
    return payload


# ---------------------------------------------------------------------------
# Internal helpers — response parsing
# ---------------------------------------------------------------------------

def _parse_anthropic_response(body: dict[str, Any], model: str) -> str:
    """Extract the text content from an Anthropic-in-Bedrock non-streaming response."""
    content = body.get("content", [])
    if isinstance(content, list) and content:
        block = content[0]
        if isinstance(block, dict) and block.get("type") == "text":
            return block.get("text", "")
    return ""


def _extract_anthropic_usage(body: dict[str, Any]) -> dict[str, int] | None:
    """Extract usage fields from an Anthropic-in-Bedrock response."""
    usage = body.get("usage")
    if not usage:
        return None
    return {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }


def _extract_finish_reason(body: dict[str, Any]) -> str | None:
    """Extract the stop reason from an Anthropic-in-Bedrock response."""
    stop_reason = body.get("stop_reason")
    if stop_reason == "end_turn":
        return "stop"
    if stop_reason == "max_tokens":
        return "length"
    if stop_reason == "tool_use":
        return "tool_calls"
    return stop_reason


def _parse_embedding_response(
    body: dict[str, Any],
    model: str,
) -> tuple[list[list[float]], dict[str, int] | None]:
    """Parse a Bedrock embedding response and return (embeddings, usage)."""
    embeddings: list[list[float]] = []
    usage: dict[str, int] | None = None

    if model.startswith(_TITAN_EMBED_PREFIX):
        embedding = body.get("embedding")
        if embedding is not None:
            embeddings = [embedding]
        input_token_count = body.get("inputTokenCount")
        if input_token_count is not None:
            usage = {
                "prompt_tokens": input_token_count,
                "completion_tokens": 0,
                "total_tokens": input_token_count,
            }

    elif model.startswith(_COHERE_EMBED_PREFIX):
        results = body.get("embeddings", [])
        embeddings = [list(emb) if isinstance(emb, (list, tuple)) else emb for emb in results]
        tokens = body.get("tokens")
        if tokens is not None:
            usage = {
                "prompt_tokens": tokens,
                "completion_tokens": 0,
                "total_tokens": tokens,
            }

    return embeddings, usage


# ---------------------------------------------------------------------------
# Internal helpers — streaming
# ---------------------------------------------------------------------------

def _parse_stream_event(raw_event: dict[str, Any]) -> str | None:
    """Parse a single Bedrock response-stream event and return text content, or None.

    Bedrock streams events as dictionaries. The "bytes" field contains a
    base64-encoded JSON payload. The inner JSON has a "type" field indicating
    the event kind. For Anthropic-in-Bedrock, relevant types are:

    - ``content_block_delta``: carries a text delta in ``delta.text``.
    - Other markers (``message_delta``, ``message_stop``, etc.): no content.

    Returns the text content of the delta, or None if the event carries no
    text (or is a non-textual delta).
    """
    inner_bytes = raw_event.get("bytes")
    if inner_bytes is None:
        return None

    try:
        decoded = base64.b64decode(inner_bytes).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return None

    try:
        inner = json.loads(decoded)
    except Exception:
        return None

    event_type = inner.get("type")

    if event_type == "content_block_delta":
        delta = inner.get("delta", {})
        text = delta.get("text")
        if text:
            return text
        return None

    return None


# ---------------------------------------------------------------------------
# Internal helpers — exception translation
# ---------------------------------------------------------------------------

def _translate_boto_error(exc: Exception, provider_id: str) -> LLMProviderError:
    """Translate any boto3/botocore exception into the LLM exception hierarchy.

    The provider_id is passed explicitly — no traceback inspection.
    """
    try:
        import botocore.exceptions as botocore
    except ImportError:
        return LLMProviderError(
            f"provider '{provider_id}': unexpected error during Bedrock call: {exc}"
        )

    if isinstance(exc, botocore.ClientError):
        error_code = exc.response.get("Error", {}).get("Code", "")
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))

        if error_code in (
            "ExpiredTokenException",
            "InvalidSignatureException",
            "UnrecognizedClientException",
            "AuthError",
        ):
            return LLMAuthenticationError(
                f"provider '{provider_id}': authentication failed: {error_msg}"
            )
        if error_code == "ThrottlingException":
            return LLMRateLimitedError(
                f"provider '{provider_id}': rate limit exceeded: {error_msg}"
            )
        if error_code in (
            "ValidationError",
            "InvalidParameterException",
            "ModelNotReadyException",
        ):
            return LLMValidationError(
                f"provider '{provider_id}': validation failed: {error_msg}"
            )
        if error_code in ("AccessDeniedException", "UnauthorizedException"):
            return LLMAuthenticationError(
                f"provider '{provider_id}': access denied: {error_msg}"
            )
        if error_code in (
            "InternalServerException",
            "ServiceUnavailable",
            "ServiceLatencyExceeded",
        ):
            return LLMUnavailableError(
                f"provider '{provider_id}': service unavailable: {error_msg}"
            )
        if error_code in ("ModelErrorException", "ModelTimeoutException"):
            return LLMProviderError(
                f"provider '{provider_id}': model error: {error_msg}"
            )
        return LLMProviderError(
            f"provider '{provider_id}': Bedrock error [{error_code}]: {error_msg}"
        )

    if isinstance(exc, botocore.EndpointConnectionError):
        return LLMUnavailableError(
            f"provider '{provider_id}': could not connect to Bedrock endpoint"
        )

    if isinstance(exc, (botocore.ConnectTimeoutError, botocore.ReadTimeoutError)):
        return LLMTimeoutError(
            f"provider '{provider_id}': timeout connecting to Bedrock"
        )

    if isinstance(exc, botocore.ResponseStreamingError):
        return LLMTimeoutError(
            f"provider '{provider_id}': timeout reading streaming response from Bedrock"
        )

    if isinstance(exc, (botocore.DataNotFoundError, botocore.UnknownServiceError)):
        return LLMProviderError(
            f"provider '{provider_id}': Bedrock model or service not found: {exc}"
        )

    if isinstance(exc, botocore.BotoCoreError):
        return LLMProviderError(
            f"provider '{provider_id}': boto3 error: {exc}"
        )

    return LLMProviderError(
        f"provider '{provider_id}': unexpected error during Bedrock call: {exc}"
    )


# ---------------------------------------------------------------------------
# Internal helpers — validation
# ---------------------------------------------------------------------------

def _is_valid_aws_region(region: str) -> bool:
    """Check that a string looks like an AWS region identifier.

    AWS regions are alphanumeric, may contain hyphens, and do not exceed
    20 characters. This is a best-effort syntactic check; it does not
    verify that the region is enabled in the account.
    """
    if not region or len(region) > 20:
        return False
    return all(c.isalnum() or c in "-_" for c in region)
