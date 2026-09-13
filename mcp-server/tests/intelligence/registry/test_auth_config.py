"""Tests for authentication configuration (Phase 2).

Covers:
1.  api_key auth type declaration loads correctly
2.  aws auth type declaration loads correctly
3.  none auth type declaration loads correctly
4.  auth.type absent is treated as api_key (backward compatibility)
5.  auth.api_key (secret value) is rejected in llm.yaml
6.  Invalid auth.type is rejected with a clear error
7.  Auth type reflected in AuthConfig.type field
8.  ProviderRecord.auth.type carries correct value through loader
"""

import os
import tempfile
import textwrap
import unittest

from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoader
from app.intelligence.registry.models.provider import AUTH_TYPE_DEFAULT_SENTINEL, AuthType
from app.intelligence.registry.validators.registry_validator import RegistryValidator


class AuthTypeDeclarationTests(unittest.TestCase):
    """Tests for auth.type declaration in llm.yaml."""

    def setUp(self):
        self.loader = LLmConfigLoader()
        self.validator = RegistryValidator()

    def _write(self, content: str) -> str:
        """Write config to a temp file and return its path."""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        self.addCleanup(lambda: __import__("pathlib").Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    # -------------------------------------------------------------------------
    # 1. api_key auth type
    # -------------------------------------------------------------------------

    def test_api_key_auth_type_loads(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: api-key-provider
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  auth:
                    type: api_key
                    api_key_env: MY_API_KEY
                  models:
                    - id: model-a
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.providers), 1)
        provider = result.providers[0]
        self.assertEqual(provider.auth.type, AuthType.API_KEY)
        self.assertEqual(provider.auth.api_key_env, "MY_API_KEY")

    def test_api_key_auth_type_validates(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: api-key-provider
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  auth:
                    type: api_key
                    api_key_env: MY_API_KEY
                  models:
                    - id: model-a
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        validation = self.validator.validate(result.providers, result.models)
        self.assertTrue(validation.valid, f"Unexpected errors: {validation.errors}")

    # -------------------------------------------------------------------------
    # 2. aws auth type
    # -------------------------------------------------------------------------

    def test_aws_auth_type_loads(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: bedrock-provider
                  type: bedrock
                  deployment: cloud
                  connection:
                    region: us-east-1
                  auth:
                    type: aws
                  models:
                    - id: bedrock-model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        provider = result.providers[0]
        self.assertEqual(provider.auth.type, AuthType.AWS)
        self.assertIsNone(provider.auth.api_key_env)

    def test_aws_auth_type_validates(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: bedrock-provider
                  type: bedrock
                  deployment: cloud
                  connection:
                    region: us-east-1
                  auth:
                    type: aws
                  models:
                    - id: bedrock-model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        validation = self.validator.validate(result.providers, result.models)
        self.assertTrue(validation.valid, f"Unexpected errors: {validation.errors}")

    # -------------------------------------------------------------------------
    # 3. none auth type
    # -------------------------------------------------------------------------

    def test_none_auth_type_loads(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: no-auth-provider
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  auth:
                    type: none
                  models:
                    - id: local-model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        provider = result.providers[0]
        self.assertEqual(provider.auth.type, AuthType.NONE)
        self.assertIsNone(provider.auth.api_key_env)

    def test_none_auth_type_validates(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: no-auth-provider
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  auth:
                    type: none
                  models:
                    - id: local-model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        validation = self.validator.validate(result.providers, result.models)
        self.assertTrue(validation.valid, f"Unexpected errors: {validation.errors}")

    # -------------------------------------------------------------------------
    # 4. auth.type absent treated as api_key (backward compatibility)
    # -------------------------------------------------------------------------

    def test_auth_type_absent_returns_sentinel(self):
        """When auth.type is absent, loader sets the sentinel (Phase 1 compat)."""
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: legacy-provider
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  auth:
                    api_key_env: LEGACY_API_KEY
                  models:
                    - id: legacy-model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        provider = result.providers[0]
        # The sentinel signals "type was absent from YAML".
        self.assertIs(provider.auth.type, AUTH_TYPE_DEFAULT_SENTINEL)
        # api_key_env is still loaded.
        self.assertEqual(provider.auth.api_key_env, "LEGACY_API_KEY")

    def test_auth_type_absent_is_backward_compatible(self):
        """Phase 1 configs without auth.type pass validation (api_key semantics)."""
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: legacy-provider
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  auth:
                    api_key_env: LEGACY_API_KEY
                  models:
                    - id: legacy-model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        # Validator must NOT require api_key_env for absent auth.type.
        validation = self.validator.validate(result.providers, result.models)
        self.assertTrue(validation.valid, f"Unexpected errors: {validation.errors}")

    # -------------------------------------------------------------------------
    # 5. auth.api_key (secret value) is rejected
    # -------------------------------------------------------------------------

    def test_api_key_secret_value_rejected(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: bad-provider
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  auth:
                    type: api_key
                    api_key_env: OPENAI_API_KEY
                    api_key: sk-actual-secret-12345
                  models:
                    - id: model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("api_key is not permitted" in e for e in result.errors),
            f"Expected 'api_key is not permitted' error, got: {result.errors}",
        )

    # -------------------------------------------------------------------------
    # 6. Invalid auth.type
    # -------------------------------------------------------------------------

    def test_invalid_auth_type_rejected(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: bad-auth-provider
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  auth:
                    type: bearer_token
                  models:
                    - id: model
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("invalid auth.type" in e for e in result.errors),
            f"Expected 'invalid auth.type' error, got: {result.errors}",
        )

    # -------------------------------------------------------------------------
    # 7. Case-insensitive auth.type
    # -------------------------------------------------------------------------

    def test_auth_type_case_insensitive(self):
        path = self._write(textwrap.dedent("""
            llm:
              providers:
                - id: api-key-provider
                  type: openai_compatible
                  deployment: cloud
                  connection:
                    base_url: https://api.example.com
                  auth:
                    type: API_KEY
                  models:
                    - id: model-a
                      type: chat
                      capabilities:
                        - chat
                - id: aws-provider
                  type: bedrock
                  deployment: cloud
                  connection:
                    region: us-east-1
                  auth:
                    type: Aws
                  models:
                    - id: model-b
                      type: chat
                      capabilities:
                        - chat
                - id: none-provider
                  type: ollama
                  deployment: self_hosted
                  connection:
                    base_url: http://localhost:11434
                  auth:
                    type: NONE
                  models:
                    - id: model-c
                      type: chat
                      capabilities:
                        - chat
        """))
        result = self.loader.load(path)
        self.assertEqual(len(result.errors), 0)
        by_id = {p.provider_id: p for p in result.providers}
        self.assertEqual(by_id["api-key-provider"].auth.type, AuthType.API_KEY)
        self.assertEqual(by_id["aws-provider"].auth.type, AuthType.AWS)
        self.assertEqual(by_id["none-provider"].auth.type, AuthType.NONE)


class AuthValidationTests(unittest.TestCase):
    """Tests for auth validation in RegistryValidator."""

    def setUp(self):
        self.validator = RegistryValidator()

    def _connection(self, base_url="", region=None):
        from app.intelligence.registry.models.provider import ConnectionConfig
        return ConnectionConfig(base_url=base_url, region=region)

    def _provider(self, auth):
        from app.intelligence.registry.models.provider import ProviderRecord
        from app.intelligence.registry.types.deployment import DeploymentType
        from app.intelligence.registry.types.provider import ProviderType
        return ProviderRecord(
            provider_id="test",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=auth,
            connection=self._connection(base_url="https://api.example.com"),
        )

    # -------------------------------------------------------------------------
    # Explicit api_key auth may use the ADR-0017 derived env fallback
    # -------------------------------------------------------------------------

    def test_explicit_api_key_auth_allows_derived_env_fallback(self):
        from app.intelligence.registry.models.provider import AuthConfig
        auth = AuthConfig(type=AuthType.API_KEY, api_key_env=None)
        result = self.validator.validate_providers([self._provider(auth)])
        errors = list(result)
        self.assertEqual(len(errors), 0, f"Unexpected errors: {[e.message for e in errors]}")

    # -------------------------------------------------------------------------
    # aws auth
    # -------------------------------------------------------------------------

    def test_aws_auth_allows_missing_api_key_env(self):
        from app.intelligence.registry.models.provider import AuthConfig
        auth = AuthConfig(type=AuthType.AWS, api_key_env=None)
        result = self.validator.validate_providers([self._provider(auth)])
        errors = list(result)
        self.assertEqual(len(errors), 0, f"Unexpected errors: {[e.message for e in errors]}")

    def test_aws_auth_warns_if_api_key_env_provided(self):
        from app.intelligence.registry.models.provider import AuthConfig
        auth = AuthConfig(type=AuthType.AWS, api_key_env="AWS_ACCESS_KEY_ID")
        result = self.validator.validate_providers([self._provider(auth)])
        errors = list(result)
        self.assertGreater(len(errors), 0)
        self.assertTrue(
            any("not used when auth.type is 'aws'" in e.message for e in errors),
            f"Expected 'not used when auth.type is aws' error, got: {[e.message for e in errors]}",
        )

    # -------------------------------------------------------------------------
    # none auth
    # -------------------------------------------------------------------------

    def test_none_auth_allows_missing_api_key_env(self):
        from app.intelligence.registry.models.provider import AuthConfig
        auth = AuthConfig(type=AuthType.NONE, api_key_env=None)
        from app.intelligence.registry.models.provider import ProviderRecord
        from app.intelligence.registry.types.deployment import DeploymentType
        from app.intelligence.registry.types.provider import ProviderType
        provider = ProviderRecord(
            provider_id="test",
            provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED,
            auth=auth,
            connection=self._connection(base_url="http://localhost:11434"),
        )
        result = self.validator.validate_providers([provider])
        errors = list(result)
        self.assertEqual(len(errors), 0, f"Unexpected errors: {[e.message for e in errors]}")

    def test_none_auth_warns_if_api_key_env_provided(self):
        from app.intelligence.registry.models.provider import AuthConfig, ProviderRecord
        from app.intelligence.registry.types.deployment import DeploymentType
        from app.intelligence.registry.types.provider import ProviderType
        auth = AuthConfig(type=AuthType.NONE, api_key_env="SOME_VAR")
        provider = ProviderRecord(
            provider_id="test",
            provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED,
            auth=auth,
            connection=self._connection(base_url="http://localhost:11434"),
        )
        result = self.validator.validate_providers([provider])
        errors = list(result)
        self.assertGreater(len(errors), 0)
        self.assertTrue(
            any("not used when auth.type is 'none'" in e.message for e in errors),
            f"Expected 'not used when auth.type is none' error, got: {[e.message for e in errors]}",
        )


if __name__ == "__main__":
    unittest.main()
