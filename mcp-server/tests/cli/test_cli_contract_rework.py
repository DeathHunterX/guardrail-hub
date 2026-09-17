"""Contract tests for the approved Guardrail Hub CLI surface."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from app.cli import main
from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoader


class CliParserContractTests(unittest.TestCase):
    """The command parser accepts only the approved setup surface."""

    def test_legacy_setup_config_option_is_rejected(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main(["setup", "--config", "other.yaml"])
        self.assertEqual(2, raised.exception.code)

    def test_legacy_target_option_is_rejected(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main(["setup", "--target", "windows"])
        self.assertEqual(2, raised.exception.code)

    def test_credential_shortcut_requires_provider(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main(["setup", "--credential"])
        self.assertEqual(2, raised.exception.code)

    def test_reconfigure_shortcut_requires_provider(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main(["setup", "--reconfigure"])
        self.assertEqual(2, raised.exception.code)

    def test_credential_option_does_not_accept_a_secret_value(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main(["setup", "--provider", "nvidia-nim", "--credential", "secret"])
        self.assertEqual(2, raised.exception.code)

    def test_credential_option_does_not_echo_an_explicit_value(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            main(["setup", "--provider", "nvidia-nim", "--credential=never-echo"])
        self.assertEqual(2, raised.exception.code)
        self.assertNotIn("never-echo", stderr.getvalue())

    def test_setup_help_documents_only_the_approved_credential_syntax(self) -> None:
        help_text = io.StringIO()
        with redirect_stdout(help_text), self.assertRaises(SystemExit) as raised:
            main(["setup", "--help"])
        self.assertEqual(0, raised.exception.code)
        self.assertIn("guardrail-hub setup --provider nvidia-nim --credential", help_text.getvalue())
        self.assertIn("Credentials are entered securely when prompted.", help_text.getvalue())
        self.assertIn("Never pass API keys on the command line.", help_text.getvalue())


class StrictCandidateValidationTests(unittest.TestCase):
    """Candidate validation rejects fields that could be copied unseen."""

    def test_strict_load_rejects_unknown_provider_field(self) -> None:
        path = self._write("""\
llm:
  providers:
    - id: local
      type: ollama
      deployment: self_hosted
      auth: {type: none}
      connection: {base_url: http://localhost:11434}
      models: []
      secret: should-not-be-ignored
""")
        result = LLmConfigLoader().load(path, strict=True)
        self.assertTrue(any("unsupported field 'secret'" in error for error in result.errors))

    def test_strict_load_rejects_literal_api_key(self) -> None:
        path = self._write("""\
llm:
  providers:
    - id: cloud
      type: openai_compatible
      deployment: cloud
      auth: {type: api_key, api_key: literal-secret}
      connection: {base_url: https://example.invalid/v1}
      models: []
""")
        result = LLmConfigLoader().load(path, strict=True)
        self.assertTrue(any("auth.api_key is not permitted" in error for error in result.errors))

    def _write(self, content: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "candidate.yaml"
        path.write_text(content, encoding="utf-8")
        return path
