"""Unit tests for the credential setup adapters.

These cover the thin I/O adapters that back the setup ports:
    - GetpassSecretPrompt delegates to a no-echo getpass primitive
    - StreamOutputWriter writes newline-terminated lines and flushes
    - Boto3AwsCredentialDetector fails cleanly (no secret leak) when boto3 is
      unavailable
"""

import io
import sys
import unittest

from app.intelligence.exceptions.llm import LLMConfigurationError
from app.intelligence.setup.adapters import (
    Boto3AwsCredentialDetector,
    GetpassSecretPrompt,
    StreamOutputWriter,
)


class GetpassSecretPromptTests(unittest.TestCase):
    """The prompt must read via getpass (hidden input), not echo the value."""

    def test_delegates_to_injected_getpass(self):
        captured = {}

        def fake_getpass(prompt_text: str) -> str:
            captured["prompt"] = prompt_text
            return "sk-hidden-value"

        prompt = GetpassSecretPrompt(getpass_fn=fake_getpass)
        result = prompt.read_secret("  API Key: ")

        self.assertEqual(result, "sk-hidden-value")
        self.assertEqual(captured["prompt"], "  API Key: ")

    def test_default_getpass_is_the_stdlib_no_echo_primitive(self):
        # We do not invoke it (no TTY in tests), but assert the default wiring
        # is Python's getpass — the standard hidden-input primitive.
        import getpass as getpass_module

        prompt = GetpassSecretPrompt()
        self.assertIs(prompt._getpass_fn, getpass_module.getpass)


class StreamOutputWriterTests(unittest.TestCase):
    def test_writes_line_with_newline(self):
        buffer = io.StringIO()
        writer = StreamOutputWriter(stream=buffer)

        writer.write_line("hello")
        writer.write_line("world")

        self.assertEqual(buffer.getvalue(), "hello\nworld\n")


class Boto3DetectorTests(unittest.TestCase):
    """When boto3 is unavailable the detector fails cleanly, without leaking."""

    def test_missing_boto3_raises_clean_configuration_error(self):
        detector = Boto3AwsCredentialDetector()

        # Setting the module to None in sys.modules makes `import boto3` raise
        # ImportError deterministically, regardless of whether boto3 is
        # installed in the environment.
        sentinel = object()
        previous = sys.modules.get("boto3", sentinel)
        sys.modules["boto3"] = None  # type: ignore[assignment]
        try:
            with self.assertRaises(LLMConfigurationError) as ctx:
                detector.is_available()
        finally:
            if previous is sentinel:
                del sys.modules["boto3"]
            else:
                sys.modules["boto3"] = previous  # type: ignore[assignment]

        message = str(ctx.exception)
        # A clear, actionable message that names the missing dependency.
        self.assertIn("boto3", message)
        # And it carries no credential-like material.
        self.assertNotIn("secret", message.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
