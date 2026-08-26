"""End-to-end tests for the ``guardrail-hub setup`` command.

These drive :func:`app.cli.main` with an explicit argument vector and injected
collaborators (credential store, secret prompt, AWS detector, output buffer), so
no test touches a real terminal, the AWS SDK, or an OS keyring.

Covered behaviours (mapping to the Phase 4 spec §6 and acceptance criteria):
    - the setup command runs from a single llm.yaml
    - a missing api_key is prompted for and stored
    - hidden input is used for the secret (wired to the prompt port)
    - an existing credential is detected and not re-prompted
    - multiple providers are configured in one invocation
    - a provider without authentication needs no credential
    - an AWS provider is validated via the credential chain (not stored)
    - llm.yaml is never modified
    - no .env file is created
    - the secret never appears in command output
    - missing / invalid configuration produces a clear config error (exit 2)
    - an unavailable credential backend produces a clear setup error (exit 3)
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Optional

from app.cli import main
from app.intelligence.credentials import (
    CredentialNotFoundError,
    CredentialStore,
    InMemoryCredentialBackend,
)

# Exit codes mirrored from app.cli (kept local so a change there is caught).
EXIT_OK = 0
EXIT_INCOMPLETE = 1
EXIT_CONFIG_ERROR = 2
EXIT_SETUP_ERROR = 3

_SECRET = "sk-CLI-SECRET-do-not-leak-0007"


# ------------------------------------------------------------------
# Fakes
# ------------------------------------------------------------------


class FakeSecretPrompt:
    """Hidden-input stand-in that returns queued secrets and records prompts."""

    def __init__(self, values: Optional[List[str]] = None) -> None:
        self._values = list(values) if values is not None else []
        self.prompts: List[str] = []
        self.call_count = 0

    def read_secret(self, prompt_text: str) -> str:
        self.prompts.append(prompt_text)
        self.call_count += 1
        return self._values.pop(0) if self._values else ""


class FakeAwsDetector:
    def __init__(self, available: bool) -> None:
        self._available = available
        self.call_count = 0

    def is_available(self) -> bool:
        self.call_count += 1
        return self._available


class BufferOutput:
    def __init__(self) -> None:
        self.lines: List[str] = []

    def write_line(self, text: str) -> None:
        self.lines.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


# ------------------------------------------------------------------
# YAML fixtures
# ------------------------------------------------------------------

_OPENAI_ONLY = """\
llm:
  providers:
    - id: openai-cloud
      type: openai_compatible
      deployment: cloud
      connection:
        base_url: https://api.openai.com/v1
      auth:
        type: api_key
        api_key_env: OPENAI_API_KEY
      models: []
"""

_MIXED = """\
llm:
  providers:
    - id: ollama-local
      type: ollama
      deployment: self_hosted
      connection:
        base_url: http://localhost:11434
      auth:
        type: none
      models: []
    - id: openai-cloud
      type: openai_compatible
      deployment: cloud
      connection:
        base_url: https://api.openai.com/v1
      auth:
        type: api_key
        api_key_env: OPENAI_API_KEY
      models: []
    - id: bedrock
      type: bedrock
      deployment: cloud
      connection:
        region: us-east-1
      auth:
        type: aws
      models: []
"""

_OLLAMA_ONLY = """\
llm:
  providers:
    - id: ollama-local
      type: ollama
      deployment: self_hosted
      connection:
        base_url: http://localhost:11434
      auth:
        type: none
      models: []
"""

_BEDROCK_ONLY = """\
llm:
  providers:
    - id: bedrock
      type: bedrock
      deployment: cloud
      connection:
        region: us-east-1
      auth:
        type: aws
      models: []
"""

# Structurally invalid: the provider is missing its required 'type'.
_INVALID = """\
llm:
  providers:
    - id: broken-provider
      deployment: cloud
      models: []
"""


class _TempConfig:
    """Context manager that writes a YAML string to a temp llm.yaml file."""

    def __init__(self, content: str) -> None:
        self._content = content
        self._dir: Optional[tempfile.TemporaryDirectory] = None
        self.path: str = ""

    def __enter__(self) -> "_TempConfig":
        self._dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self._dir.name)
        cfg = self.dir_path / "llm.yaml"
        cfg.write_text(self._content, encoding="utf-8")
        self.path = str(cfg)
        return self

    def __exit__(self, *exc) -> None:
        if self._dir is not None:
            self._dir.cleanup()


def _new_store() -> CredentialStore:
    return CredentialStore(InMemoryCredentialBackend())


# ------------------------------------------------------------------
# Happy-path configuration
# ------------------------------------------------------------------


class SetupCommandTests(unittest.TestCase):
    """Core setup command behaviours."""

    def test_missing_api_key_is_prompted_and_stored(self):
        store = _new_store()
        prompt = FakeSecretPrompt(values=[_SECRET])
        out = BufferOutput()
        with _TempConfig(_OPENAI_ONLY) as cfg:
            code = main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=prompt,
                aws_detector=FakeAwsDetector(False),
                output=out,
            )

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(prompt.call_count, 1)
        self.assertEqual(store.get("openai-cloud"), _SECRET)

    def test_hidden_input_prompt_port_is_used_for_secret(self):
        # The command must obtain the secret via the SecretPrompt port (which
        # the production wiring backs with getpass for no-echo input), not by
        # echoing it or reading it from the config.
        store = _new_store()
        prompt = FakeSecretPrompt(values=[_SECRET])
        out = BufferOutput()
        with _TempConfig(_OPENAI_ONLY) as cfg:
            code = main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=prompt,
                aws_detector=FakeAwsDetector(False),
                output=out,
            )

        self.assertEqual(code, EXIT_OK)
        # The prompt port received exactly one hidden-input request.
        self.assertEqual(len(prompt.prompts), 1)

    def test_existing_credential_is_detected_not_reprompted(self):
        store = _new_store()
        store.set("openai-cloud", _SECRET)
        prompt = FakeSecretPrompt(values=["SHOULD-NOT-BE-USED"])
        out = BufferOutput()
        with _TempConfig(_OPENAI_ONLY) as cfg:
            code = main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=prompt,
                aws_detector=FakeAwsDetector(False),
                output=out,
            )

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(prompt.call_count, 0)
        self.assertIn("already configured", out.text.lower())

    def test_reconfigure_flag_replaces_existing_credential(self):
        store = _new_store()
        store.set("openai-cloud", "old-value")
        new_secret = "sk-CLI-NEW-0008"
        prompt = FakeSecretPrompt(values=[new_secret])
        out = BufferOutput()
        with _TempConfig(_OPENAI_ONLY) as cfg:
            code = main(
                ["setup", "--config", cfg.path, "--reconfigure", "openai-cloud"],
                credential_store=store,
                secret_prompt=prompt,
                aws_detector=FakeAwsDetector(False),
                output=out,
            )

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(prompt.call_count, 1)
        self.assertEqual(store.get("openai-cloud"), new_secret)

    def test_multiple_providers_from_one_config(self):
        store = _new_store()
        prompt = FakeSecretPrompt(values=[_SECRET])
        out = BufferOutput()
        with _TempConfig(_MIXED) as cfg:
            code = main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=prompt,
                aws_detector=FakeAwsDetector(True),
                output=out,
            )

        self.assertEqual(code, EXIT_OK)
        # Only the api_key provider was prompted.
        self.assertEqual(prompt.call_count, 1)
        self.assertEqual(store.get("openai-cloud"), _SECRET)
        # Ollama needs nothing; Bedrock is detected via the AWS chain.
        self.assertIn("No credential required", out.text)
        self.assertIn("AWS credentials detected", out.text)

    def test_provider_without_authentication_needs_no_credential(self):
        store = _new_store()
        prompt = FakeSecretPrompt()
        out = BufferOutput()
        with _TempConfig(_OLLAMA_ONLY) as cfg:
            code = main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=prompt,
                aws_detector=FakeAwsDetector(False),
                output=out,
            )

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(prompt.call_count, 0)
        self.assertIn("No credential required", out.text)


# ------------------------------------------------------------------
# AWS providers
# ------------------------------------------------------------------


class AwsProviderCliTests(unittest.TestCase):
    def test_aws_detected_returns_ok(self):
        store = _new_store()
        out = BufferOutput()
        with _TempConfig(_BEDROCK_ONLY) as cfg:
            code = main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=FakeSecretPrompt(),
                aws_detector=FakeAwsDetector(True),
                output=out,
            )
        self.assertEqual(code, EXIT_OK)
        self.assertIn("AWS credentials detected", out.text)

    def test_aws_unavailable_returns_incomplete(self):
        store = _new_store()
        out = BufferOutput()
        with _TempConfig(_BEDROCK_ONLY) as cfg:
            code = main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=FakeSecretPrompt(),
                aws_detector=FakeAwsDetector(False),
                output=out,
            )
        self.assertEqual(code, EXIT_INCOMPLETE)
        self.assertIn("AWS credentials not found", out.text)


# ------------------------------------------------------------------
# Security guarantees: no llm.yaml change, no .env, no secret in output
# ------------------------------------------------------------------


class SecurityGuaranteeTests(unittest.TestCase):
    def test_setup_does_not_modify_llm_yaml(self):
        store = _new_store()
        out = BufferOutput()
        with _TempConfig(_MIXED) as cfg:
            before = Path(cfg.path).read_bytes()
            code = main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=FakeSecretPrompt(values=[_SECRET]),
                aws_detector=FakeAwsDetector(True),
                output=out,
            )
            after = Path(cfg.path).read_bytes()

        self.assertEqual(code, EXIT_OK)
        # The configuration file is byte-for-byte unchanged.
        self.assertEqual(before, after)

    def test_setup_creates_no_env_file(self):
        store = _new_store()
        out = BufferOutput()
        original_cwd = os.getcwd()
        with _TempConfig(_MIXED) as cfg:
            # Run with cwd inside the temp dir so a stray ".env" (relative to
            # cwd) would be detectable.
            os.chdir(cfg.dir_path)
            try:
                code = main(
                    ["setup", "--config", cfg.path],
                    credential_store=store,
                    secret_prompt=FakeSecretPrompt(values=[_SECRET]),
                    aws_detector=FakeAwsDetector(True),
                    output=out,
                )
            finally:
                os.chdir(original_cwd)

            self.assertEqual(code, EXIT_OK)
            # No .env anywhere in the temp tree, and none in the config dir.
            env_files = list(cfg.dir_path.rglob(".env")) + list(
                cfg.dir_path.rglob(".env.*")
            )
            self.assertEqual(env_files, [])

    def test_secret_absent_from_command_output(self):
        store = _new_store()
        out = BufferOutput()
        with _TempConfig(_OPENAI_ONLY) as cfg:
            main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=FakeSecretPrompt(values=[_SECRET]),
                aws_detector=FakeAwsDetector(False),
                output=out,
            )
        self.assertNotIn(_SECRET, out.text)


# ------------------------------------------------------------------
# Failure handling
# ------------------------------------------------------------------


class FailureHandlingTests(unittest.TestCase):
    def test_missing_config_file_returns_config_error(self):
        store = _new_store()
        out = BufferOutput()
        missing = str(Path(tempfile.gettempdir()) / "does-not-exist-llm.yaml")
        code = main(
            ["setup", "--config", missing],
            credential_store=store,
            secret_prompt=FakeSecretPrompt(),
            aws_detector=FakeAwsDetector(False),
            output=out,
        )
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("Configuration error", out.text)

    def test_invalid_config_returns_config_error(self):
        store = _new_store()
        out = BufferOutput()
        with _TempConfig(_INVALID) as cfg:
            code = main(
                ["setup", "--config", cfg.path],
                credential_store=store,
                secret_prompt=FakeSecretPrompt(),
                aws_detector=FakeAwsDetector(False),
                output=out,
            )
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("Configuration error", out.text)

    def test_unavailable_backend_returns_setup_error(self):
        # With no injected store, the CLI builds the default backend. On any
        # non-Windows platform that fails closed (no plaintext fallback), which
        # must surface as a clear setup error (exit 3) — never a crash.
        if sys.platform == "win32":
            self.skipTest("default backend is available on Windows")
        out = BufferOutput()
        with _TempConfig(_OPENAI_ONLY) as cfg:
            code = main(
                ["setup", "--config", cfg.path],
                # credential_store intentionally NOT injected.
                secret_prompt=FakeSecretPrompt(values=[_SECRET]),
                aws_detector=FakeAwsDetector(False),
                output=out,
            )
        self.assertEqual(code, EXIT_SETUP_ERROR)
        self.assertIn("Setup error", out.text)


# ------------------------------------------------------------------
# Integration against the real repository config
# ------------------------------------------------------------------


class RealConfigIntegrationTests(unittest.TestCase):
    """Prove the command works against the repository's own config/llm.yaml."""

    def _repo_config_path(self) -> Path:
        # tests/cli/ -> tests/ -> mcp-server/
        return Path(__file__).resolve().parents[2] / "config" / "llm.yaml"

    def test_real_config_runs_and_is_not_modified(self):
        config_path = self._repo_config_path()
        if not config_path.exists():
            self.skipTest("repository config/llm.yaml not present")

        store = _new_store()
        out = BufferOutput()
        before = config_path.read_bytes()
        code = main(
            ["setup", "--config", str(config_path)],
            credential_store=store,
            secret_prompt=FakeSecretPrompt(values=[_SECRET]),
            aws_detector=FakeAwsDetector(True),
            output=out,
        )
        after = config_path.read_bytes()

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(before, after)
        self.assertNotIn(_SECRET, out.text)
        self.assertIn("Setup complete.", out.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
