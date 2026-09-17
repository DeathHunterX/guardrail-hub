"""Unified LLM exception hierarchy.

Providers normalize their SDK exceptions into these types.
This creates a stable interface for error handling across all providers.
"""


class LLMError(Exception):
    """Base exception for all LLM-related errors.

    Routers map these to appropriate HTTP status codes or handle
    them according to the application's error policy.
    """

    pass


class LLMProviderError(LLMError):
    """A provider-level error occurred (network, upstream, internal).

    Wraps the original cause via ``raise ... from``.
    """

    pass


class LLMAuthenticationError(LLMProviderError):
    """Authentication with the provider failed.

    Causes: invalid API key, expired token, missing credentials.
    Routers map this to HTTP 401.
    """

    pass


class LLMRateLimitedError(LLMProviderError):
    """The provider rate limit has been exceeded.

    Causes: too many requests, quota exceeded.
    Routers map this to HTTP 429.
    """

    pass


class LLMTimeoutError(LLMProviderError):
    """The provider request timed out.

    Causes: slow response, network issues.
    Routers may retry with backoff or fail gracefully.
    """

    pass


class LLMUnavailableError(LLMProviderError):
    """The provider is unavailable or returned an error.

    Causes: provider outage, service degradation, 5xx responses.
    Routers may attempt failover to another provider.
    """

    pass


class LLMValidationError(LLMError):
    """Request validation failed.

    Causes: invalid parameters, missing required fields, schema violations.
    Routers map this to HTTP 400.
    """

    pass


class LLMConfigurationError(LLMError):
    """Provider configuration is invalid or missing.

    Causes: missing environment variables, invalid endpoint URL.
    This is typically caught at startup, not at request time.
    """

    pass


class LLMModelNotFoundError(LLMError):
    """The requested model is not available or not found.

    Causes: model_id does not exist in the registry.
    Routers map this to HTTP 404.
    """

    pass
