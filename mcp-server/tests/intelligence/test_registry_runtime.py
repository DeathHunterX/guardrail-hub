"""Unit tests for RegistryRuntime — bootstrap, immutability, fail-fast."""

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from app.intelligence.registry.builders.catalog_builder import CatalogBuilder
from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.exceptions import (
    RegistryLoadError,
    RegistryValidationError,
)
from app.intelligence.registry.loaders.registry_loader import RegistryLoader
from app.intelligence.runtime import (
    RegistryRuntime,
    RegistryRuntimeSettings,
)


class RegistryRuntimeLifecycleTests(unittest.TestCase):
    """Tests for the lifecycle of :class:`RegistryRuntime`."""

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

    def test_start_builds_empty_catalog_from_empty_yaml(self):
        providers_path, models_path = self._make_paths(
            "providers: []\n", "models: []\n"
        )
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=providers_path,
                models_path=models_path,
            )
        )
        catalog = runtime.start()
        self.assertIsInstance(catalog, ModelCatalog)
        self.assertTrue(runtime.started)
        self.assertTrue(catalog.frozen)
        self.assertTrue(catalog.is_empty)
        self.assertIs(runtime.catalog, catalog)

    def test_start_is_not_idempotent(self):
        providers_path, models_path = self._make_paths(
            "providers: []\n", "models: []\n"
        )
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=providers_path,
                models_path=models_path,
            )
        )
        runtime.start()
        with self.assertRaises(RuntimeError):
            runtime.start()

    def test_catalog_property_requires_start(self):
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=Path("/tmp/nope.yaml"),
                models_path=Path("/tmp/nope2.yaml"),
            )
        )
        with self.assertRaises(RuntimeError):
            _ = runtime.catalog

    def test_stop_is_a_noop(self):
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=Path("/tmp/nope.yaml"),
                models_path=Path("/tmp/nope2.yaml"),
            )
        )
        # Should not raise even though start was never called.
        runtime.stop()

    def test_start_with_missing_files_fails_fast(self):
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=Path("/tmp/no-such-file-providers.yaml"),
                models_path=Path("/tmp/no-such-file-models.yaml"),
                require_files=True,
            )
        )
        with self.assertRaises(FileNotFoundError):
            runtime.start()

    def test_start_with_missing_files_optional_builds_empty(self):
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=Path("/tmp/no-such-providers.yaml"),
                models_path=Path("/tmp/no-such-models.yaml"),
                require_files=False,
            )
        )
        catalog = runtime.start()
        self.assertTrue(catalog.is_empty)
        self.assertTrue(catalog.frozen)


class RegistryRuntimeLoadFailureTests(unittest.TestCase):
    """Tests that load errors and validation errors are surfaced."""

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

    def test_invalid_yaml_surfaces_registry_load_error(self):
        providers_path, models_path = self._make_paths(
            "providers:\n  - bad: : syntax\n", "models: []\n"
        )
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=providers_path,
                models_path=models_path,
            )
        )
        with self.assertRaises(RegistryLoadError):
            runtime.start()

    def test_unknown_provider_reference_raises_validation_error(self):
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
                    provider_id: not_in_registry
                    model_type: chat
                    capabilities:
                      - chat
            """),
        )
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=providers_path,
                models_path=models_path,
            )
        )
        with self.assertRaises(RegistryValidationError):
            runtime.start()

    def test_duplicate_provider_id_raises_validation_error(self):
        providers_path, models_path = self._make_paths(
            textwrap.dedent("""
                providers:
                  - provider_id: dup
                    provider_type: openai_compatible
                    deployment: cloud
                    connection:
                      base_url: https://api.example.com
                  - provider_id: dup
                    provider_type: openai_compatible
                    deployment: cloud
                    connection:
                      base_url: https://api.example.com
            """),
            "models: []\n",
        )
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=providers_path,
                models_path=models_path,
            )
        )
        with self.assertRaises(RegistryValidationError):
            runtime.start()


class RegistryRuntimeSettingsTests(unittest.TestCase):
    """Tests for :class:`RegistryRuntimeSettings`."""

    def test_from_mapping_defaults(self):
        settings = RegistryRuntimeSettings.from_mapping({})
        self.assertEqual(
            str(settings.providers_path), "config/providers.yaml"
        )
        self.assertEqual(
            str(settings.models_path), "config/models.yaml"
        )
        self.assertTrue(settings.require_files)

    def test_from_mapping_overrides(self):
        settings = RegistryRuntimeSettings.from_mapping(
            {
                "registry_providers_path": "/custom/providers.yaml",
                "registry_models_path": "/custom/models.yaml",
                "registry_require_files": False,
            }
        )
        self.assertEqual(
            str(settings.providers_path), "/custom/providers.yaml"
        )
        self.assertFalse(settings.require_files)


class RegistryRuntimeBuilderInjectionTests(unittest.TestCase):
    """The runtime accepts a custom builder (for testing)."""

    def test_injected_builder_is_used(self):
        providers_path = Path("/tmp/nope.yaml")
        models_path = Path("/tmp/nope2.yaml")

        sentinel_catalog = ModelCatalog()
        sentinel_catalog.freeze()

        class _SentinelBuilder:
            def build_from_paths(self, *_args, **_kwargs):
                return sentinel_catalog, None

        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                providers_path=providers_path,
                models_path=models_path,
                require_files=False,
            ),
            builder=_SentinelBuilder(),
        )
        catalog = runtime.start()
        self.assertIs(catalog, sentinel_catalog)
        self.assertIs(runtime.catalog, sentinel_catalog)


if __name__ == "__main__":
    unittest.main()