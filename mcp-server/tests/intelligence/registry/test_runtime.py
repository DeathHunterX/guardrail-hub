"""Component tests for RegistryRuntime lifecycle and fail-fast loading."""

import tempfile
import textwrap
import unittest
from pathlib import Path

from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.exceptions import RegistryLoadError, RegistryValidationError
from app.intelligence.runtime import RegistryRuntime, RegistryRuntimeSettings


class RegistryRuntimeTests(unittest.TestCase):
    def _write_config(self, content: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        handle.write(content)
        handle.close()
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_start_builds_frozen_empty_catalog(self):
        path = self._write_config("llm:\n  providers: []\n")
        runtime = RegistryRuntime(RegistryRuntimeSettings(llm_config_path=path))

        catalog = runtime.start()

        self.assertIsInstance(catalog, ModelCatalog)
        self.assertTrue(runtime.started)
        self.assertTrue(catalog.frozen)
        self.assertTrue(catalog.is_empty)
        self.assertIs(runtime.catalog, catalog)

    def test_start_is_not_idempotent(self):
        path = self._write_config("llm:\n  providers: []\n")
        runtime = RegistryRuntime(RegistryRuntimeSettings(llm_config_path=path))
        runtime.start()

        with self.assertRaises(RuntimeError):
            runtime.start()

    def test_catalog_property_requires_start(self):
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=Path("missing.yaml"))
        )

        with self.assertRaises(RuntimeError):
            _ = runtime.catalog

    def test_stop_is_safe_before_start(self):
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=Path("missing.yaml"))
        )

        runtime.stop()

    def test_missing_required_config_fails_fast(self):
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                llm_config_path=Path("definitely-missing-llm.yaml"),
                require_files=True,
            )
        )

        with self.assertRaises(FileNotFoundError):
            runtime.start()

    def test_missing_optional_config_builds_frozen_empty_catalog(self):
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(
                llm_config_path=Path("definitely-missing-llm.yaml"),
                require_files=False,
            )
        )

        catalog = runtime.start()

        self.assertTrue(catalog.frozen)
        self.assertTrue(catalog.is_empty)

    def test_invalid_yaml_surfaces_registry_load_error(self):
        path = self._write_config("llm:\n  providers:\n    - bad: : syntax\n")
        runtime = RegistryRuntime(RegistryRuntimeSettings(llm_config_path=path))

        with self.assertRaises(RegistryLoadError):
            runtime.start()

    def test_loader_errors_surface_as_registry_load_error(self):
        path = self._write_config(
            textwrap.dedent(
                """
                llm:
                  providers:
                    - id: duplicate
                      type: ollama
                      models: []
                    - id: duplicate
                      type: ollama
                      models: []
                """
            )
        )
        runtime = RegistryRuntime(RegistryRuntimeSettings(llm_config_path=path))

        with self.assertRaises(RegistryLoadError):
            runtime.start()

    def test_catalog_validation_errors_remain_distinct(self):
        path = self._write_config(
            textwrap.dedent(
                """
                llm:
                  providers:
                    - id: excessive-priority
                      type: ollama
                      deployment: self_hosted
                      priority: -1
                      connection:
                        base_url: http://localhost:11434
                      models:
                        - id: model
                          type: chat
                          capabilities: [chat]
                """
            )
        )
        runtime = RegistryRuntime(RegistryRuntimeSettings(llm_config_path=path))

        with self.assertRaises(RegistryValidationError):
            runtime.start()


class RegistryRuntimeSettingsTests(unittest.TestCase):
    def test_from_mapping_requires_unified_config_path(self):
        with self.assertRaises(ValueError):
            RegistryRuntimeSettings.from_mapping({})

    def test_from_mapping_uses_unified_config_path_and_flag(self):
        settings = RegistryRuntimeSettings.from_mapping(
            {
                "registry_llm_config_path": "/custom/llm.yaml",
                "registry_require_files": False,
            }
        )

        self.assertEqual(settings.llm_config_path, Path("/custom/llm.yaml"))
        self.assertFalse(settings.require_files)


class RegistryRuntimeCatalogInjectionTests(unittest.TestCase):
    def test_injected_catalog_is_exposed_without_loading_disk(self):
        catalog = ModelCatalog()
        catalog.freeze()
        runtime = RegistryRuntime(
            RegistryRuntimeSettings(llm_config_path=Path("missing.yaml")),
            catalog=catalog,
        )

        result = runtime.start()

        self.assertIs(result, catalog)
        self.assertIs(runtime.catalog, catalog)


if __name__ == "__main__":
    unittest.main()
