"""Unit tests for ProviderLoader and ModelLoader YAML/env behavior."""

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from app.intelligence.registry.exceptions import RegistryLoadError
from app.intelligence.registry.loaders.model_loader import ModelLoader
from app.intelligence.registry.loaders.provider_loader import ProviderLoader


class ProviderLoaderYamlTests(unittest.TestCase):
    """ProviderLoader tests focused on file/YAML/env behavior."""

    def setUp(self):
        self.loader = ProviderLoader()

    def _write(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_load_valid_yaml(self):
        path = self._write(textwrap.dedent("""
            providers:
              - provider_id: ollama-local
                provider_type: ollama
                deployment: self_hosted
                capabilities:
                  - chat
                connection:
                  base_url: http://localhost:11434
                  timeout_seconds: 30.0
        """))
        result = self.loader.load_from_yaml(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.providers), 1)
        provider = result.providers[0]
        self.assertEqual(provider.provider_id, "ollama-local")
        self.assertEqual(provider.provider_type.value, "ollama")

    def test_load_resolves_env_vars(self):
        os.environ["PROVIDER_TEST_BASE_URL"] = "http://from-env:11434"
        try:
            path = self._write(textwrap.dedent("""
                providers:
                  - provider_id: from-env
                    provider_type: ollama
                    deployment: self_hosted
                    connection:
                      base_url: "${PROVIDER_TEST_BASE_URL}"
            """))
            result = self.loader.load_from_yaml(path)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(
                result.providers[0].connection.base_url,
                "http://from-env:11434",
            )
        finally:
            del os.environ["PROVIDER_TEST_BASE_URL"]

    def test_unresolved_env_var_is_a_load_error(self):
        path = self._write(textwrap.dedent("""
            providers:
              - provider_id: from-env
                provider_type: ollama
                deployment: self_hosted
                connection:
                  base_url: "${DEFINITELY_NOT_SET_VAR}"
        """))
        result = self.loader.load_from_yaml(path)
        self.assertGreater(len(result.errors), 0)
        joined = " ".join(result.errors)
        self.assertIn("DEFINITELY_NOT_SET_VAR", joined)

    def test_missing_file_raises(self):
        with self.assertRaises(RegistryLoadError):
            self.loader.load_from_yaml("/tmp/definitely-does-not-exist-xyz.yaml")

    def test_yaml_syntax_error_raises(self):
        path = self._write("providers:\n  - provider_id: x\n : bad indent")
        with self.assertRaises(RegistryLoadError):
            self.loader.load_from_yaml(path)

    def test_empty_providers_list(self):
        path = self._write("providers: []\n")
        result = self.loader.load_from_yaml(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.providers), 0)


class ModelLoaderYamlTests(unittest.TestCase):
    """ModelLoader tests focused on file/YAML/env behavior."""

    def setUp(self):
        self.loader = ModelLoader()

    def _write(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_load_valid_yaml(self):
        path = self._write(textwrap.dedent("""
            models:
              - model_id: llama-3
                provider_id: ollama-local
                model_type: chat
                context_window: 8192
                capabilities:
                  - chat
        """))
        result = self.loader.load_from_yaml(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.models), 1)
        model = result.models[0]
        self.assertEqual(model.context_window, 8192)

    def test_load_resolves_env_var(self):
        os.environ["MODEL_TEST_NAME"] = "deployment-from-env"
        try:
            path = self._write(textwrap.dedent("""
                models:
                  - model_id: llama-3
                    provider_id: ollama-local
                    model_type: chat
                    deployment_name: "${MODEL_TEST_NAME}"
                    capabilities:
                      - chat
            """))
            result = self.loader.load_from_yaml(path)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(
                result.models[0].deployment_name,
                "deployment-from-env",
            )
        finally:
            del os.environ["MODEL_TEST_NAME"]

    def test_invalid_model_type_reports_position(self):
        path = self._write(textwrap.dedent("""
            models:
              - model_id: bad
                provider_id: ollama-local
                model_type: not_a_real_type
                capabilities:
                  - chat
        """))
        result = self.loader.load_from_yaml(path)
        self.assertEqual(len(result.models), 0)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("invalid model_type", result.errors[0])

    def test_negative_context_window_is_a_load_error(self):
        path = self._write(textwrap.dedent("""
            models:
              - model_id: bad
                provider_id: ollama-local
                model_type: chat
                context_window: -1
                capabilities:
                  - chat
        """))
        result = self.loader.load_from_yaml(path)
        self.assertEqual(len(result.models), 0)
        self.assertEqual(len(result.errors), 1)


if __name__ == "__main__":
    unittest.main()