"""LLM-specific exceptions — unified error hierarchy for provider SDK normalization.

All provider SDK exceptions must be normalized into these types.
This ensures consistent error handling across all LLM providers.
"""

from app.intelligence.exceptions.llm import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMRateLimitedError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMValidationError,
)

__all__ = [
    "LLMError",
    "LLMProviderError",
    "LLMAuthenticationError",
    "LLMRateLimitedError",
    "LLMTimeoutError",
    "LLMUnavailableError",
    "LLMValidationError",
    "LLMConfigurationError",
    "LLMModelNotFoundError",
]
