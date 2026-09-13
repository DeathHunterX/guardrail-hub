"""Unit tests for LLmConfigLoader — unified llm.yaml loading and normalization.

Coverage:
1.  Unified llm.yaml loading
2.  Multiple providers
3.  Multiple models per provider
4.  provider_id normalization (inherited from parent)
5.  deployment_name != model_id
6.  Duplicate provider IDs
7.  Duplicate model IDs
8.  Invalid provider type
9.  Invalid deployment
10. Missing required provider configuration
11. Missing model capabilities
12. Invalid model type
13. Negative / zero context_window
14. Unresolved environment variable
15. Malformed YAML
16. Provider capabilities derived from models (not independently configured)
"""

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoader
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.model import ModelType
from app.intelligence.registry.types.provider import ProviderType


class LLmConfigLoaderBasicTests(unittest.TestCase):
    """Basic loading tests for the unified LLmConfigLoader."""

    def setUp(self):
        self.loader = LLmConfigLoader()

    def _write(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    # ------------------------------------------------------------------
    # 1. Valid configuration — single provider / single model
    # ------------------------------------------------------------------

    def test_loads_empty_config(self):
        path = self._write("llm:\n  providers: []\n")
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.providers), 0)
        self.assertEqual(len(result.models), 0)

    def test_loads_single_provider_with_model(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: ollama-local
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: llama3
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.providers), 1)
        self.assertEqual(len(result.models), 1)

        provider = result.providers[0]
        self.assertEqual(provider.provider_id, "ollama-local")
        self.assertEqual(provider.provider_type, ProviderType.OLLAMA)
        self.assertEqual(provider.deployment, DeploymentType.SELF_HOSTED)
        self.assertEqual(provider.connection.base_url, "http://localhost:11434")

        model = result.models[0]
        self.assertEqual(model.model_id, "llama3")
        self.assertEqual(model.provider_id, "ollama-local")
        self.assertEqual(model.model_type, ModelType.CHAT)
        self.assertEqual(model.capabilities, frozenset({Capability.CHAT}))
        self.assertIsNone(model.deployment_name)

    # ------------------------------------------------------------------
    # 2. Multiple providers
    # ------------------------------------------------------------------

    def test_loads_multiple_providers(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: provider-a
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: model-a1
                      type: chat
                      capabilities:
                        - chat
                - id: provider-b
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  models:
                    - id: model-b1
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.providers), 2)
        self.assertEqual(len(result.models), 2)
        self.assertEqual(result.providers[0].provider_id, "provider-a")
        self.assertEqual(result.providers[1].provider_id, "provider-b")
        self.assertEqual(result.models[0].provider_id, "provider-a")
        self.assertEqual(result.models[1].provider_id, "provider-b")

    # ------------------------------------------------------------------
    # 3. Multiple models per provider
    # ------------------------------------------------------------------

    def test_multiple_models_per_provider(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: multi-model
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  models:
                    - id: gpt-4o
                      type: chat
                      capabilities:
                        - chat
                    - id: embedding-model
                      type: embedding
                      capabilities:
                        - embedding
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.models), 2)
        model_ids = {m.model_id for m in result.models}
        self.assertEqual(model_ids, {"gpt-4o", "embedding-model"})
        for m in result.models:
            self.assertEqual(m.provider_id, "multi-model")

    # ------------------------------------------------------------------
    # 4. provider_id normalization — model inherits from parent
    # ------------------------------------------------------------------

    def test_model_provider_id_normalized_from_parent(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: my-provider
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: model-under-provider
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        for model in result.models:
            self.assertEqual(model.provider_id, "my-provider")

    def test_provider_id_not_from_model_yaml_field(self):
        """Model.provider_id comes from YAML hierarchy, not a model-level field."""
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: explicit-provider
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: model-with-provider-field
                      provider_id: wrong-value
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        for model in result.models:
            self.assertEqual(model.provider_id, "explicit-provider")

    # ------------------------------------------------------------------
    # 5. deployment_name != model_id
    # ------------------------------------------------------------------

    def test_deployment_name_may_differ_from_model_id(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: bedrock
                  type: bedrock
                  deployment: cloud
                  connection:
                    region: us-east-1
                  models:
                    - id: claude-sonnet
                      type: chat
                      deployment_name: anthropic.claude-3-sonnet-20240229-v1:0
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        model = result.models[0]
        self.assertEqual(model.model_id, "claude-sonnet")
        self.assertEqual(model.deployment_name, "anthropic.claude-3-sonnet-20240229-v1:0")
        self.assertNotEqual(model.model_id, model.deployment_name)

    def test_deployment_name_defaults_to_none_when_not_specified(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: ollama
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: llama3
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertIsNone(result.models[0].deployment_name)

    # ------------------------------------------------------------------
    # 6. Duplicate provider IDs
    # ------------------------------------------------------------------

    def test_duplicate_provider_id_detected(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: dup-provider
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models: []
                - id: dup-provider
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  models: []
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("duplicate" in e and "provider" in e for e in result.errors)
        )

    # ------------------------------------------------------------------
    # 7. Duplicate model IDs
    # ------------------------------------------------------------------

    def test_duplicate_model_id_detected(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: provider-a
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  models:
                    - id: shared-model-id
                      type: chat
                      capabilities:
                        - chat
                - id: provider-b
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://other.example.com
                  models:
                    - id: shared-model-id
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("duplicate" in e and "model" in e for e in result.errors)
        )

    # ------------------------------------------------------------------
    # 8. Invalid provider type
    # ------------------------------------------------------------------

    def test_invalid_provider_type(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: bad-type
                  type: not_a_real_type
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models: []
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("invalid provider type" in e for e in result.errors)
        )

    # ------------------------------------------------------------------
    # 9. Invalid deployment
    # ------------------------------------------------------------------

    def test_invalid_deployment(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: bad-deployment
                  type: ollama
                  deployment: not_valid
                  connection:
                    base_url: http://localhost:11434
                  models: []
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("invalid deployment" in e for e in result.errors))

    # ------------------------------------------------------------------
    # 10. Missing required provider configuration
    # ------------------------------------------------------------------

    def test_missing_provider_id(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models: []
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("'id' is required" in e for e in result.errors))

    def test_missing_provider_type(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: no-type
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models: []
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("'type' is required" in e for e in result.errors))

    def test_missing_models_list(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: no-models
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("'models' list" in e for e in result.errors))

    # ------------------------------------------------------------------
    # 11. Missing model capabilities
    # ------------------------------------------------------------------

    def test_missing_model_capabilities(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: no-caps
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: model-no-caps
                      type: chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("capability" in e for e in result.errors))

    # ------------------------------------------------------------------
    # 12. Invalid model type
    # ------------------------------------------------------------------

    def test_invalid_model_type(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: ollama
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: bad-model-type
                      type: not_a_type
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("invalid model type" in e for e in result.errors))

    # ------------------------------------------------------------------
    # 13. Negative / zero context_window
    # ------------------------------------------------------------------

    def test_negative_context_window(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: ollama
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: bad-context
                      type: chat
                      context_window: -100
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("context_window" in e for e in result.errors))

    def test_zero_context_window(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: ollama
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: zero-context
                      type: chat
                      context_window: 0
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("context_window" in e for e in result.errors))

    # ------------------------------------------------------------------
    # 14. Unresolved environment variable
    # ------------------------------------------------------------------

    def test_unresolved_env_var_reported(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: env-provider
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: "${DEFINITELY_NOT_SET_VAR_12345}"
                  models:
                    - id: env-model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("DEFINITELY_NOT_SET_VAR_12345" in e for e in result.errors)
        )

    # ------------------------------------------------------------------
    # 15. Malformed YAML / file errors
    # ------------------------------------------------------------------

    def test_yaml_syntax_error_raises(self):
        from app.intelligence.registry.exceptions import RegistryLoadError

        path = self._write("llm:\n  providers:\n  - bad: : syntax\n")
        with self.assertRaises(RegistryLoadError):
            self.loader.load(path)

    def test_missing_file_raises(self):
        from app.intelligence.registry.exceptions import RegistryLoadError

        with self.assertRaises(RegistryLoadError):
            self.loader.load("/tmp/definitely-does-not-exist-xyz.yaml")

    def test_missing_top_level_llm_key(self):
        path = self._write("providers: []\n")
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("top-level 'llm'" in e for e in result.errors))

    def test_llm_value_not_dict(self):
        path = self._write("llm:\n  - item\n")
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("must be a dictionary" in e for e in result.errors))

    # ------------------------------------------------------------------
    # 16. Provider capabilities derived from models
    # ------------------------------------------------------------------

    def test_provider_capabilities_derived_from_models(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: multi-cap
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  models:
                    - id: chat-model
                      type: chat
                      capabilities:
                        - chat
                        - embedding
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)

        provider = result.providers[0]
        self.assertEqual(
            provider.capabilities,
            frozenset({Capability.CHAT, Capability.EMBEDDING}),
        )

        model = result.models[0]
        self.assertEqual(
            model.capabilities,
            frozenset({Capability.CHAT, Capability.EMBEDDING}),
        )

    def test_provider_capabilities_empty_when_no_models(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: empty-provider
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models: []
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.providers[0].capabilities, frozenset())

    # ------------------------------------------------------------------
    # 17. Additional configuration fields
    # ------------------------------------------------------------------

    def test_loads_with_context_window(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: ollama
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: llama-3-70b
                      type: chat
                      context_window: 32768
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.models[0].context_window, 32768)

    def test_loads_with_priority(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: ollama
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: llama3
                      type: chat
                      priority: 5
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.models[0].priority, 5)

    def test_loads_with_enabled_flag(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: disabled-provider
                  type: ollama
                  deployment: self_hosted
                  enabled: false
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: disabled-model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertFalse(result.providers[0].enabled)

    def test_loads_with_auth_api_key_env(self):
        os.environ["TEST_API_KEY"] = "test-secret-123"
        try:
            path = self._write(textwrap.dedent("""
                llm:
                  providers:
                    - id: auth-provider
                      type: openai_compatible
                      deployment: cloud
                      connection:
                        base_url: https://api.example.com
                      auth:
                        api_key_env: TEST_API_KEY
                      models:
                        - id: model-with-auth
                          type: chat
                          capabilities:
                            - chat
            """))
            result = self.loader.load(path)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(result.providers[0].auth.api_key_env, "TEST_API_KEY")
        finally:
            del os.environ["TEST_API_KEY"]

    def test_env_var_substitution(self):
        os.environ["TEST_BASE_URL"] = "http://custom-host:9999"
        try:
            path = self._write(textwrap.dedent("""
                llm:
                  providers:
                    - id: env-provider
                      type: ollama
                      deployment: self_hosted
                      connection:
                        base_url: "${TEST_BASE_URL}"
                      models:
                        - id: env-model
                          type: chat
                          capabilities:
                            - chat
            """))
            result = self.loader.load(path)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(
                result.providers[0].connection.base_url,
                "http://custom-host:9999",
            )
        finally:
            del os.environ["TEST_BASE_URL"]

    def test_base_url_must_be_http_or_https(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: bad-url
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: ftp://localhost
                  models:
                    - id: model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("http:// or https://" in e for e in result.errors)
        )

    def test_deployment_name_must_be_string(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: ollama
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  models:
                    - id: model
                      type: chat
                      deployment_name: 12345
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("deployment_name" in e for e in result.errors)
        )

    # ------------------------------------------------------------------
    # 18. load_from_dict
    # ------------------------------------------------------------------

    def test_load_from_dict(self):
        data = {
            "llm": {
                "providers": [
                    {
                        "id": "dict-provider",
                        "type": "ollama",
                        "deployment": "self_hosted",
                        "connection": {"base_url": "http://localhost:11434"},
                        "models": [
                            {
                                "id": "dict-model",
                                "type": "chat",
                                "capabilities": ["chat"],
                            }
                        ],
                    }
                ]
            }
        }
        result = self.loader.load_from_dict(data)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.providers), 1)
        self.assertEqual(len(result.models), 1)
        self.assertEqual(result.providers[0].provider_id, "dict-provider")
        self.assertEqual(result.models[0].model_id, "dict-model")

    def test_load_from_dict_missing_llm_key(self):
        result = self.loader.load_from_dict({})
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("'llm'" in e for e in result.errors))

    # ------------------------------------------------------------------
    # 19. Model-level base_url override validation
    # ------------------------------------------------------------------

    def test_model_with_invalid_base_url_rejected(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: provider
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  models:
                    - id: model
                      type: chat
                      base_url: bad-url
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("http:// or https://" in e for e in result.errors)
        )


if __name__ == "__main__":
    unittest.main()
