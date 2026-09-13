"""Unit tests for the Intelligence Layer exception hierarchy."""

import unittest

from app.intelligence.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMRateLimitedError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMValidationError,
    LLMAuthenticationError,
)


class LLMExceptionTests(unittest.TestCase):
    """Tests for the LLM exception hierarchy."""

    def test_llm_error_is_base(self):
        self.assertTrue(issubclass(LLMError, Exception))

    def test_llm_provider_error_inherits_from_llm_error(self):
        self.assertTrue(issubclass(LLMProviderError, LLMError))

    def test_auth_error_inherits_from_provider_error(self):
        self.assertTrue(issubclass(LLMAuthenticationError, LLMProviderError))
        self.assertTrue(issubclass(LLMAuthenticationError, LLMError))

    def test_rate_limit_error_inherits_from_provider_error(self):
        self.assertTrue(issubclass(LLMRateLimitedError, LLMProviderError))

    def test_timeout_error_inherits_from_provider_error(self):
        self.assertTrue(issubclass(LLMTimeoutError, LLMProviderError))

    def test_unavailable_error_inherits_from_provider_error(self):
        self.assertTrue(issubclass(LLMUnavailableError, LLMProviderError))

    def test_validation_error_inherits_from_llm_error(self):
        self.assertTrue(issubclass(LLMValidationError, LLMError))

    def test_configuration_error_inherits_from_llm_error(self):
        self.assertTrue(issubclass(LLMConfigurationError, LLMError))

    def test_model_not_found_error_inherits_from_llm_error(self):
        self.assertTrue(issubclass(LLMModelNotFoundError, LLMError))

    def test_exceptions_are_raisable(self):
        with self.assertRaises(LLMError):
            raise LLMError("test")

        with self.assertRaises(LLMAuthenticationError):
            raise LLMAuthenticationError("invalid key")

        with self.assertRaises(LLMTimeoutError):
            raise LLMTimeoutError("connection timeout")

    def test_exception_chaining(self):
        original = ValueError("original error")
        try:
            raise LLMProviderError("provider error") from original
        except LLMProviderError as e:
            self.assertIsNotNone(e.__cause__)
            self.assertEqual(e.__cause__, original)


if __name__ == "__main__":
    unittest.main()
