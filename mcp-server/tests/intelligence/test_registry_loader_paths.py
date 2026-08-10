"""Unit tests for RegistryLoader.load_from_paths — end-to-end YAML pipeline."""

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from app.intelligence.registry.loaders.registry_loader import RegistryLoader


class RegistryLoaderPathsTests(unittest.TestCase):
    """End-to-end registry loading from on-disk YAML files."""

    def _make_paths(self, providers_text: str, models_text: str):
        providers = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        providers.write(providers_text)
        providers.close()

        models = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        models.write(models_text)
        models.close()

        self.addCleanup(lambda: Path(providers.name).unlink(missing_ok=True))
        self.addCleanup(lambda: Path(models.name).unlink(missing_ok=True))

        return Path(providers.name), Path(models.name)

    def test_load_clean_pair(self):
        providers_path, models_path = self._make_paths(
            textwrap.dedent("""
                providers:
                  - provider_id: ollama-local
                    provider_type: ollama
                    deployment: self_hosted
                    capabilities:
                      - chat
                    connection:
                      base_url: http://localhost:11434
                  - provider_id: cloud-1
                    provider_type: openai_compatible
                    deployment: cloud
                    connection:
                      base_url: https://api.example.com
            """),
            textwrap.dedent("""
                models:
                  - model_id: llama-3
                    provider_id: ollama-local
                    model_type: chat
                    capabilities:
                      - chat
                  - model_id: cloud-chat
                    provider_id: cloud-1
                    model_type: chat
                    capabilities:
                      - chat
            """),
        )
        loader = RegistryLoader()
        result = loader.load_from_paths(providers_path, models_path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.providers), 2)
        self.assertEqual(len(result.models), 2)

    def test_load_resolves_env_in_both_files(self):
        os.environ["REG_LOADER_TEST_URL"] = "http://from-env:11434"
        try:
            providers_path, models_path = self._make_paths(
                textwrap.dedent("""
                    providers:
                      - provider_id: ollama-local
                        provider_type: ollama
                        deployment: self_hosted
                        capabilities:
                          - chat
                        connection:
                          base_url: "${REG_LOADER_TEST_URL}"
                """),
                textwrap.dedent("""
                    models:
                      - model_id: llama-3
                        provider_id: ollama-local
                        model_type: chat
                        capabilities:
                          - chat
                """),
            )
            loader = RegistryLoader()
            result = loader.load_from_paths(providers_path, models_path)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(
                result.providers[0].connection.base_url,
                "http://from-env:11434",
            )
        finally:
            del os.environ["REG_LOADER_TEST_URL"]

    def test_validation_surfaces_cross_reference_errors(self):
        providers_path, models_path = self._make_paths(
            textwrap.dedent("""
                providers:
                  - provider_id: known
                    provider_type: openai_compatible
                    deployment: cloud
                    connection:
                      base_url: https://api.example.com
            """),
            textwrap.dedent("""
                models:
                  - model_id: orphan
                    provider_id: missing
                    model_type: chat
                    capabilities:
                      - chat
            """),
        )
        loader = RegistryLoader()
        result = loader.load_from_paths(providers_path, models_path)
        # Phase 2: the unknown provider reference becomes a validation
        # ERROR. The error is still in result.errors (the runtime turns
        # these into RegistryValidationError).
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("missing" in e for e in result.errors),
            f"Expected 'missing' in errors, got: {result.errors}",
        )


if __name__ == "__main__":
    unittest.main()