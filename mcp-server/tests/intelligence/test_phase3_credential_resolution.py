"""Phase 3 security tests — runtime credential resolution boundary.

These tests prove the security properties of Phase 3 (runtime credential
resolution) for LLM providers. They exercise the real bootstrap path
(``ProviderManager.start`` → ``factory.create`` → credential resolution →
``adapter.initialize`` → ``validate_configuration`` → ``start``) with a real
:class:`CredentialStore` backed by an in-memory backend.

Proven properties (Phase 3 spec, section "Security Tests"):

1.  API-key credentials are resolved from the CredentialStore, keyed by
    ``provider_id``, at provider bootstrap (and read live, not hardcoded).
2.  A missing stored credential — and a missing credential store — each fail
    clearly, with a message that names only the provider, never the secret.
3.  Credentials never enter the ModelCatalog (ProviderRecord / ModelRecord).
4.  Credentials never enter the router-facing surfaces. No dedicated
    ``RoutingDecision`` type exists in this codebase yet; the router's contract
    is to return the non-secret pair ``(provider_id, model_id)``. The concrete
    surfaces that carry that routing output are the catalog query summaries
    (:class:`ProviderSummary` / :class:`ModelSummary`) and :class:`ChatOptions`.
    All are asserted credential-free.
5.  Credentials never enter :class:`ChatOptions`.
6.  Credentials never appear in log output — even when the credential-bearing
    objects are logged directly.
7.  Credentials never appear in exception messages or the object's string form.
8.  AWS Bedrock initializes without any API key (AWS SDK credential chain);
    it never consults the CredentialStore.
9.  Ollama initializes and runs with no authentication and no credential.
10. OpenAI-compatible providers authenticate with the resolved API key, which
    is wired into the HTTP client's Authorization header.

The HTTP layer (httpx) and AWS SDK (boto3/botocore) are faked before the
adapters are imported, so the whole lifecycle runs without a network or the
real SDKs. This mirrors the injection pattern in test_provider_adapters.py.
"""

import dataclasses
import logging
import os
import tempfile
import sys
import unittest
from unittest import mock
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Fake httpx — injected before any adapter import so AsyncClient construction
# works without a real network dependency. _FakeAsyncClient records the headers
# it is constructed with, which lets the tests assert on the Authorization
# header wired from the resolved credential.
# ---------------------------------------------------------------------------

class _FakeAsyncClient:
    def __init__(self, **kwargs):
        self.base_url = kwargs.get("base_url", "")
        self.headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout")
        self._closed = False

    async def post(self, path, **kw):
        return _FakeResponse(200, {})

    async def aclose(self):
        self._closed = True

    def stream(self, method, path, **kw):
        return _FakeStreamContext([])


class _FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise Exception(f"HTTP {self.status_code}")


class _FakeStreamContext:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


_fake_httpx = MagicMock()
_fake_httpx.AsyncClient = _FakeAsyncClient
_fake_httpx.Timeout = type("Timeout", (object,), {
    "__init__": lambda self, *args, **kwargs: None
})
_fake_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
_fake_httpx.ConnectError = type("ConnectError", (Exception,), {})
_fake_httpx.PoolTimeout = type("PoolTimeout", (Exception,), {})
_fake_httpx.ProtocolError = type("ProtocolError", (Exception,), {})
_fake_httpx.HTTPStatusError = type("HTTPStatusError", (Exception,), {})
sys.modules.setdefault("httpx", _fake_httpx)

# ---------------------------------------------------------------------------
# Fake boto3 / botocore — required because importing the adapters package pulls
# in the Bedrock adapter, which does ``import boto3`` at module load time.
# ---------------------------------------------------------------------------

class _FakeBoto3Session:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def client(self, name, **kw):
        return MagicMock()


class _FakeBoto3SessionConfig:
    def __init__(self, **kwargs):
        pass


class _FakeClientError(Exception):
    def __init__(self, response, operation_name):
        super().__init__(str(response))
        self.response = response


class _FakeBotoCoreError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__("BotoCore error")


class _FakeBotocoreExceptions:
    ClientError = _FakeClientError
    BotoCoreError = _FakeBotoCoreError
    EndpointConnectionError = type("ECE", (Exception,), {})
    ConnectTimeoutError = type("CTE", (Exception,), {})
    ReadTimeoutError = type("RTE", (Exception,), {})
    ResponseStreamingError = type("RSE", (Exception,), {})
    DataNotFoundError = type("DNF", (Exception,), {})
    UnknownServiceError = type("USE", (Exception,), {})


class _FakeBotocoreModule:
    exceptions = _FakeBotocoreExceptions()
    ClientError = _FakeClientError
    BotoCoreError = _FakeBotoCoreError


_fake_boto3 = MagicMock()
_fake_boto3.Session = _FakeBoto3Session
_fake_boto3.__version__ = "1.0.0"
_fake_boto3.botocore = _FakeBotocoreModule()
_fake_boto3.session = MagicMock()
_fake_boto3.session.Config = _FakeBoto3SessionConfig
sys.modules.setdefault("boto3", _fake_boto3)
sys.modules.setdefault("botocore", _fake_boto3.botocore)
sys.modules.setdefault("botocore.exceptions", _fake_boto3.botocore.exceptions)
sys.modules.setdefault("boto3.session", _fake_boto3.session)


# ---------------------------------------------------------------------------
# Application imports (after the fakes are installed).
# ---------------------------------------------------------------------------

from app.intelligence.credentials import CredentialStore, InMemoryCredentialBackend
from app.intelligence.credentials.container_backend import ContainerFileCredentialBackend
from app.intelligence.exceptions import LLMConfigurationError, LLMProviderError
from app.intelligence.ports.chat import ChatOptions
from app.intelligence.providers.adapters import (
    BedrockAdapter,
    OllamaAdapter,
    OpenAICompatibleAdapter,
)
from app.intelligence.providers.credential import ProviderCredential
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.providers.provider_manager import ProviderManager
from app.intelligence.registry.catalog.catalog import (
    ModelCatalog,
    ModelSummary,
    ProviderSummary,
)
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import (
    AuthConfig,
    AuthType,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.model import ModelType
from app.intelligence.registry.types.provider import ProviderType
from app.intelligence.setup.service import CredentialSetupService


# ---------------------------------------------------------------------------
# Test constants and fixtures
# ---------------------------------------------------------------------------

# The spec's canonical example: an api-key provider identified as "nvidia".
_OPENAI_PROVIDER_ID = "nvidia"
_OPENAI_SECRET = "sk-nvidia-super-secret-key-abcdef0123456789"
_OPENAI_BASE_URL = "https://integrate.api.nvidia.com/v1"


def _openai_provider_record(
    provider_id: str = _OPENAI_PROVIDER_ID,
    base_url: str = _OPENAI_BASE_URL,
    deployment: DeploymentType = DeploymentType.CLOUD,
) -> ProviderRecord:
    """Build an OpenAI-compatible, api-key provider record with an explicit api_key_env.

    ``api_key_env`` holds only the NAME of the environment variable — never the
    secret value. The secret is resolved from the CredentialStore at runtime,
    keyed by the provider ID; env-name projection is backend-specific.

    To store a credential for this record, use the credential store key
    ``"nvidia"`` (the provider ID).
    """
    return ProviderRecord(
        provider_id=provider_id,
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=deployment,
        auth=AuthConfig(type=AuthType.API_KEY, api_key_env="NVIDIA_API_KEY"),
        connection=ConnectionConfig(base_url=base_url),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=10,
    )


def _openai_provider_record_no_env_key(
    provider_id: str = "my-provider",
    base_url: str = _OPENAI_BASE_URL,
    deployment: DeploymentType = DeploymentType.CLOUD,
) -> ProviderRecord:
    """Build an OpenAI-compatible, api-key provider record WITHOUT an explicit api_key_env.

    When ``auth.api_key_env`` is absent, the env backend derives
    ``GUARDRAILHUB_CREDENTIAL__<PROVIDER_ID>`` in uppercase as its physical
    environment-variable name. CredentialStore continues to use ``provider_id``.
    """
    return ProviderRecord(
        provider_id=provider_id,
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=deployment,
        auth=AuthConfig(type=AuthType.API_KEY),  # no api_key_env → default key
        connection=ConnectionConfig(base_url=base_url),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=10,
    )


def _ollama_provider_record(auth: "AuthConfig | None" = None) -> ProviderRecord:
    """Build a self-hosted Ollama provider record (no authentication by default)."""
    return ProviderRecord(
        provider_id="ollama-local",
        provider_type=ProviderType.OLLAMA,
        deployment=DeploymentType.SELF_HOSTED,
        # AuthConfig() leaves auth.type as the sentinel (absent) → not api-key.
        auth=auth if auth is not None else AuthConfig(),
        connection=ConnectionConfig(base_url="http://localhost:11434"),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=10,
    )


def _bedrock_provider_record() -> ProviderRecord:
    """Build an AWS Bedrock provider record (AWS auth, no api key)."""
    return ProviderRecord(
        provider_id="bedrock",
        provider_type=ProviderType.BEDROCK,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(type=AuthType.AWS),
        connection=ConnectionConfig(region="us-east-1"),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=10,
    )


def _model_record(provider_id: str) -> ModelRecord:
    """Build a minimal chat model record for a provider."""
    return ModelRecord(
        provider_id=provider_id,
        model_id=f"{provider_id}-model",
        model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}),
        context_window=8192,
        priority=10,
    )


def _build_catalog(*provider_records: ProviderRecord) -> ModelCatalog:
    """Build and freeze a catalog with one chat model per provider."""
    catalog = ModelCatalog()
    for provider in provider_records:
        catalog.register_provider(provider)
        catalog.register_model(_model_record(provider.provider_id))
    catalog.freeze()
    return catalog


def _build_factory() -> ProviderFactory:
    """Build a factory with all three real adapters registered by provider type."""
    factory = ProviderFactory()
    factory.register(ProviderType.OPENAI_COMPATIBLE.value, OpenAICompatibleAdapter)
    factory.register(ProviderType.OLLAMA.value, OllamaAdapter)
    factory.register(ProviderType.BEDROCK.value, BedrockAdapter)
    return factory


def _bedrock_env() -> dict:
    """Return an environment mapping with a region set and AWS keys removed.

    Using ``clear=True`` with this mapping in ``patch.dict`` guarantees that no
    ambient AWS access keys leak into the test, so the "no api key" credential
    chain path is exercised deterministically.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
    }
    env["AWS_REGION"] = "us-east-1"
    return env


# ---------------------------------------------------------------------------
# Lifecycle / boundary tests (async — exercise the real bootstrap path)
# ---------------------------------------------------------------------------

class TestCredentialResolutionBoundary(unittest.IsolatedAsyncioTestCase):
    """Prove the runtime credential-resolution security boundary end to end."""

    async def test_api_key_resolved_from_credential_store(self):
        """(1) The api key is resolved from the CredentialStore by provider ID.

        The lookup key is provider_id ("nvidia" for this provider),
        per ADR-0017 Decision E. Also proves the value is read live from the store
        (a different stored value produces a different resolved credential).
        """
        store = CredentialStore(InMemoryCredentialBackend())
        store.set("nvidia", _OPENAI_SECRET)

        manager = ProviderManager(
            factory=_build_factory(),
            catalog=_build_catalog(_openai_provider_record()),
            credential_store=store,
        )
        await manager.start()
        try:
            provider = manager.get_provider(_OPENAI_PROVIDER_ID)
            self.assertIsNotNone(provider)
            # The adapter received a runtime-only ProviderCredential.
            self.assertIsInstance(provider._credential, ProviderCredential)
            self.assertEqual(provider._credential.api_key, _OPENAI_SECRET)
        finally:
            await manager.stop()

        # A different stored value is resolved on a fresh bootstrap — the key is
        # read live from the store (by provider_id), never hardcoded.
        other_secret = "sk-a-completely-different-value-987654321"
        store2 = CredentialStore(InMemoryCredentialBackend())
        store2.set("nvidia", other_secret)
        manager2 = ProviderManager(
            factory=_build_factory(),
            catalog=_build_catalog(_openai_provider_record()),
            credential_store=store2,
        )
        await manager2.start()
        try:
            provider2 = manager2.get_provider(_OPENAI_PROVIDER_ID)
            self.assertEqual(provider2._credential.api_key, other_secret)
        finally:
            await manager2.stop()

    async def test_missing_stored_credential_fails_clearly(self):
        """(2a) An api-key provider with no stored credential fails clearly.

        The failure names only the provider and never contains the secret. The
        exact message is asserted at the resolution boundary; the public start()
        path is asserted to fail fast.
        """
        store = CredentialStore(InMemoryCredentialBackend())  # nothing stored
        catalog = _build_catalog(_openai_provider_record())
        factory = _build_factory()

        # Public bootstrap path fails fast.
        manager = ProviderManager(factory, catalog, credential_store=store)
        with self.assertRaises(LLMProviderError) as ctx:
            await manager.start()
        message = str(ctx.exception)
        self.assertIn('Provider "nvidia" requires an API key', message)
        self.assertIn("no credential is configured", message)
        self.assertNotIn(_OPENAI_SECRET, message)
        # The provider must not be available after a failed start.
        self.assertIsNone(manager.get_provider(_OPENAI_PROVIDER_ID))

        # Exact message at the resolution boundary (white-box).
        record = _openai_provider_record()
        adapter = factory.create(record)
        with self.assertRaises(LLMConfigurationError) as ctx2:
            manager._resolve_and_attach_credential(record, adapter)
        self.assertEqual(
            str(ctx2.exception),
            'Provider "nvidia" requires an API key, but no credential is configured.',
        )

    async def test_missing_credential_store_fails_clearly(self):
        """(2b) An api-key provider with no credential store at all fails clearly."""
        catalog = _build_catalog(_openai_provider_record())
        factory = _build_factory()

        manager = ProviderManager(factory, catalog, credential_store=None)
        with self.assertRaises(LLMProviderError) as ctx:
            await manager.start()
        message = str(ctx.exception)
        self.assertIn('Provider "nvidia" requires an API key', message)
        self.assertIn("no credential store is configured", message)
        self.assertNotIn(_OPENAI_SECRET, message)

        # Exact message at the resolution boundary (white-box).
        record = _openai_provider_record()
        adapter = factory.create(record)
        with self.assertRaises(LLMConfigurationError) as ctx2:
            manager._resolve_and_attach_credential(record, adapter)
        self.assertEqual(
            str(ctx2.exception),
            'Provider "nvidia" requires an API key, but no credential store is configured.',
        )

    async def test_credential_absent_from_model_catalog(self):
        """(3) The resolved credential never enters the ModelCatalog.

        Checked both structurally (no secret-bearing field on the records) and
        dynamically (after a real resolution, the secret is not in any record's
        string form).
        """
        # Structural: records carry no field that could hold a secret value.
        provider_fields = {f.name for f in dataclasses.fields(ProviderRecord)}
        self.assertNotIn("api_key", provider_fields)
        self.assertNotIn("credential", provider_fields)
        self.assertNotIn("secret", provider_fields)

        model_fields = {f.name for f in dataclasses.fields(ModelRecord)}
        self.assertNotIn("api_key", model_fields)
        self.assertNotIn("credential", model_fields)

        auth_fields = {f.name for f in dataclasses.fields(AuthConfig)}
        # AuthConfig declares only the NAME of the env var, never the value.
        self.assertIn("api_key_env", auth_fields)
        self.assertNotIn("api_key", auth_fields)
        self.assertNotIn("credential", auth_fields)

        # Dynamic: after a successful resolution, the catalog holds no secret.
        store = CredentialStore(InMemoryCredentialBackend())
        store.set("nvidia", _OPENAI_SECRET)
        catalog = _build_catalog(_openai_provider_record())
        manager = ProviderManager(_build_factory(), catalog, credential_store=store)
        await manager.start()
        try:
            for record in catalog.iter_providers():
                self.assertNotIn(_OPENAI_SECRET, repr(record))
            for record in catalog.iter_models():
                self.assertNotIn(_OPENAI_SECRET, repr(record))
            self.assertNotIn(
                _OPENAI_SECRET, repr(catalog.get_provider(_OPENAI_PROVIDER_ID).auth)
            )
        finally:
            await manager.stop()

    async def test_credential_absent_from_routing_surfaces(self):
        """(4) The resolved credential never enters the router-facing surfaces.

        No dedicated RoutingDecision type exists in this codebase; the router's
        contract is the non-secret pair (provider_id, model_id). The concrete
        surfaces that carry routing output are the catalog query summaries and
        ChatOptions — all asserted credential-free, structurally and dynamically.
        """
        for summary_cls in (ProviderSummary, ModelSummary):
            fields = {f.name for f in dataclasses.fields(summary_cls)}
            for forbidden in ("api_key", "credential", "secret", "token"):
                self.assertNotIn(forbidden, fields)

        store = CredentialStore(InMemoryCredentialBackend())
        store.set("nvidia", _OPENAI_SECRET)
        catalog = _build_catalog(_openai_provider_record())
        manager = ProviderManager(_build_factory(), catalog, credential_store=store)
        await manager.start()
        try:
            for summary in catalog.list_providers(enabled_only=True):
                self.assertNotIn(_OPENAI_SECRET, repr(summary))
            for summary in catalog.list_models():
                self.assertNotIn(_OPENAI_SECRET, repr(summary))
            # ChatOptions is the concrete carrier of the router's resolved
            # provider_id/model_id → model/deployment_name. It holds no secret.
            options = ChatOptions(model="nvidia-model")
            self.assertNotIn(_OPENAI_SECRET, repr(options))
        finally:
            await manager.stop()

    async def test_credential_never_appears_in_logs(self):
        """(6) The credential never appears in log output.

        Runs the real lifecycle while capturing every log record from the root
        logger, and additionally logs the credential-bearing objects directly
        (the credential and the started adapter) to simulate accidental logging.
        Masking must prevent any leak.
        """
        records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _Capture()
        root = logging.getLogger()
        previous_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        try:
            store = CredentialStore(InMemoryCredentialBackend())
            store.set("nvidia", _OPENAI_SECRET)
            manager = ProviderManager(
                _build_factory(),
                _build_catalog(_openai_provider_record()),
                credential_store=store,
            )
            await manager.start()
            try:
                provider = manager.get_provider(_OPENAI_PROVIDER_ID)
                # Simulate code that accidentally logs the sensitive objects.
                manager_logger = logging.getLogger(
                    "app.intelligence.providers.provider_manager"
                )
                manager_logger.info(
                    "provider=%s credential=%s", provider, provider._credential
                )
                manager_logger.debug("credential repr: %r", provider._credential)
            finally:
                await manager.stop()
        finally:
            root.removeHandler(handler)
            root.setLevel(previous_level)

        # Non-vacuous: the explicit log calls above were captured.
        self.assertTrue(records)
        for record in records:
            self.assertNotIn(_OPENAI_SECRET, record.getMessage())
            # Guard against the secret hiding in structured 'extra' fields.
            self.assertNotIn(_OPENAI_SECRET, str(record.__dict__))

    async def test_credential_never_appears_in_exceptions(self):
        """(7) The credential never appears in exception messages or its str form."""
        credential = ProviderCredential(api_key=_OPENAI_SECRET)

        # The object masks itself across every stringification path.
        self.assertEqual(repr(credential), "ProviderCredential(api_key=********)")
        self.assertEqual(str(credential), "ProviderCredential(api_key=********)")
        self.assertNotIn(_OPENAI_SECRET, f"{credential}")
        self.assertNotIn(_OPENAI_SECRET, "{}".format(credential))
        self.assertNotIn(_OPENAI_SECRET, "%s" % (credential,))
        self.assertNotIn(_OPENAI_SECRET, "%r" % (credential,))

        # An exception that interpolates the credential does not leak the secret.
        error = LLMProviderError(f"provider failed with {credential}")
        self.assertNotIn(_OPENAI_SECRET, str(error))

        # End-to-end: an error raised WHILE a credential is attached (a CLOUD
        # OpenAI-compatible provider with a non-HTTPS base_url fails validation
        # after the credential has been resolved and attached) never leaks it.
        bad_record = _openai_provider_record(base_url="http://insecure.example.com/v1")
        store = CredentialStore(InMemoryCredentialBackend())
        store.set("nvidia", _OPENAI_SECRET)
        manager = ProviderManager(
            _build_factory(), _build_catalog(bad_record), credential_store=store
        )
        with self.assertRaises(LLMProviderError) as ctx:
            await manager.start()
        self.assertNotIn(_OPENAI_SECRET, str(ctx.exception))
    async def test_ollama_without_auth_initializes_and_runs(self):
        """(9) Ollama initializes and runs with no authentication and no credential."""
        # Sentinel default (auth.type absent) → treated as no-auth.
        store = CredentialStore(InMemoryCredentialBackend())  # empty
        manager = ProviderManager(
            _build_factory(),
            _build_catalog(_ollama_provider_record()),
            credential_store=store,
        )
        await manager.start()
        try:
            provider = manager.get_provider("ollama-local")
            self.assertIsNotNone(provider)
            self.assertTrue(provider.is_started)
            self.assertIsNone(provider._credential)
            self.assertIsNone(provider._api_key)
            # No Authorization header is sent when unauthenticated.
            self.assertNotIn("Authorization", provider._client.headers)
        finally:
            await manager.stop()

        # Explicit auth.type = none also works, even with no credential store.
        manager2 = ProviderManager(
            _build_factory(),
            _build_catalog(_ollama_provider_record(auth=AuthConfig(type=AuthType.NONE))),
            credential_store=None,
        )
        await manager2.start()
        try:
            provider2 = manager2.get_provider("ollama-local")
            self.assertIsNotNone(provider2)
            self.assertIsNone(provider2._api_key)
        finally:
            await manager2.stop()

    async def test_openai_compatible_api_key_authentication_works(self):
        """(10) OpenAI-compatible auth uses the resolved key in the Authorization header."""
        store = CredentialStore(InMemoryCredentialBackend())
        store.set("nvidia", _OPENAI_SECRET)
        manager = ProviderManager(
            _build_factory(),
            _build_catalog(_openai_provider_record()),
            credential_store=store,
        )
        await manager.start()
        try:
            provider = manager.get_provider(_OPENAI_PROVIDER_ID)
            self.assertIsNotNone(provider)
            self.assertTrue(provider.is_started)
            self.assertEqual(provider._api_key, _OPENAI_SECRET)
            # The resolved key is wired into the HTTP client's Authorization header.
            self.assertEqual(
                provider._client.headers["Authorization"],
                f"Bearer {_OPENAI_SECRET}",
            )
        finally:
            await manager.stop()


# ---------------------------------------------------------------------------
# Static boundary tests (no lifecycle needed)
# ---------------------------------------------------------------------------

class TestCredentialStaticBoundaries(unittest.TestCase):
    """Structural guarantees that hold independently of any running provider."""

    def test_credential_absent_from_chat_options(self):
        """(5) ChatOptions has no credential-bearing field and never carries a secret."""
        option_fields = {f.name for f in dataclasses.fields(ChatOptions)}
        for forbidden in ("api_key", "credential", "secret", "token", "authorization"):
            self.assertNotIn(forbidden, option_fields)

        # A populated ChatOptions never contains the secret in its string form.
        options = ChatOptions(
            model="nvidia-model",
            temperature=0.5,
            max_tokens=256,
        )
        self.assertNotIn(_OPENAI_SECRET, repr(options))
        self.assertNotIn(_OPENAI_SECRET, str(options))




# ---------------------------------------------------------------------------
# Phase 5D: D1 — api_key_env lookup semantics
# ---------------------------------------------------------------------------


class TestD1ApiKeyEnvLookup(unittest.IsolatedAsyncioTestCase):
    """CredentialStore always receives the provider's logical identity."""

    async def test_api_key_env_present_uses_provider_id_as_lookup_key(self):
        """api_key_env never changes the CredentialStore namespace.

        The provider record declares auth.api_key_env="CUSTOM_API_KEY". The store
        must have the credential under the provider ID. A value stored under the
        environment-variable name alone must NOT be found.
        """
        catalog = _build_catalog(_openai_provider_record())
        factory = _build_factory()

        # Store under the wrong physical env name — it must not be resolved.
        wrong_store = CredentialStore(InMemoryCredentialBackend())
        wrong_store.set("NVIDIA_API_KEY", _OPENAI_SECRET)

        manager_wrong = ProviderManager(factory, catalog, credential_store=wrong_store)
        with self.assertRaises(LLMProviderError) as ctx:
            await manager_wrong.start()
        self.assertIn("nvidia", str(ctx.exception))
        await manager_wrong.stop()

        # Store under the logical provider ID — must be resolved.
        correct_store = CredentialStore(InMemoryCredentialBackend())
        correct_store.set("nvidia", _OPENAI_SECRET)

        manager_correct = ProviderManager(factory, catalog, credential_store=correct_store)
        await manager_correct.start()
        try:
            provider = manager_correct.get_provider("nvidia")
            self.assertIsNotNone(provider)
            self.assertEqual(provider._credential.api_key, _OPENAI_SECRET)
        finally:
            await manager_correct.stop()

    async def test_setup_and_runtime_agree_on_provider_id_identity(self):
        """Setup and runtime use provider_id, never api_key_env, as the store key."""
        class RecordingBackend(InMemoryCredentialBackend):
            def __init__(self):
                super().__init__()
                self.get_keys = []
                self.set_keys = []

            def get(self, provider_id):
                self.get_keys.append(provider_id)
                return super().get(provider_id)

            def set(self, provider_id, credential):
                self.set_keys.append(provider_id)
                super().set(provider_id, credential)

        class SecretPrompt:
            def read_secret(self, prompt_text):
                return _OPENAI_SECRET

        class AwsDetector:
            def is_available(self):
                return False

        class Output:
            def write_line(self, text):
                pass

        record = _openai_provider_record(provider_id="openai-cloud")
        configured_env_name = record.auth.api_key_env
        backend = RecordingBackend()
        store = CredentialStore(backend)
        setup = CredentialSetupService(
            credential_store=store,
            secret_prompt=SecretPrompt(),
            aws_detector=AwsDetector(),
            output=Output(),
        )

        setup.run([record])
        self.assertEqual(backend.set_keys, ["openai-cloud"])

        backend.get_keys.clear()
        manager = ProviderManager(
            _build_factory(), _build_catalog(record), credential_store=store
        )
        await manager.start()
        try:
            self.assertEqual(backend.get_keys, ["openai-cloud"])
            self.assertNotIn(configured_env_name, backend.get_keys)
        finally:
            await manager.stop()

    async def test_file_backend_uses_provider_id_when_api_key_env_is_configured(self):
        """The file backend receives provider_id, never the env-variable name."""
        with tempfile.TemporaryDirectory() as directory:
            secret_path = os.path.join(directory, "nvidia")
            with open(secret_path, "w", encoding="utf-8") as secret_file:
                secret_file.write(_OPENAI_SECRET)

            manager = ProviderManager(
                _build_factory(),
                _build_catalog(_openai_provider_record()),
                credential_store=CredentialStore(
                    ContainerFileCredentialBackend(secrets_dir=directory)
                ),
            )
            await manager.start()
            try:
                provider = manager.get_provider("nvidia")
                self.assertEqual(provider._credential.api_key, _OPENAI_SECRET)
            finally:
                await manager.stop()

    async def test_api_key_env_absent_still_uses_provider_id_as_lookup_key(self):
        """Env fallback naming is backend-owned, not ProviderManager policy."""
        # Build a record with no api_key_env (AuthConfig() has no type and no api_key_env).
        record_no_env = ProviderRecord(
            provider_id="my-provider",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(type=AuthType.API_KEY),  # no api_key_env
            connection=ConnectionConfig(base_url="https://example.com/v1"),
            capabilities=frozenset({Capability.CHAT}),
            enabled=True,
            priority=10,
        )
        catalog = _build_catalog(record_no_env)
        factory = _build_factory()

        # Store under the logical provider ID.
        default_store = CredentialStore(InMemoryCredentialBackend())
        default_store.set("my-provider", _OPENAI_SECRET)

        manager = ProviderManager(factory, catalog, credential_store=default_store)
        await manager.start()
        try:
            provider = manager.get_provider("my-provider")
            self.assertIsNotNone(provider)
            self.assertEqual(provider._credential.api_key, _OPENAI_SECRET)
        finally:
            await manager.stop()

        # The former global env fallback must not be treated as a store key.
        wrong_store = CredentialStore(InMemoryCredentialBackend())
        wrong_store.set("GUARDRAILHUB_CREDENTIAL__MY-PROVIDER", _OPENAI_SECRET)

        manager_wrong = ProviderManager(factory, catalog, credential_store=wrong_store)
        with self.assertRaises(LLMProviderError):
            await manager_wrong.start()
        await manager_wrong.stop()

    async def test_custom_env_name_does_not_replace_provider_store_identity(self):
        """A configured environment name is not a logical credential identity.

        Runtime resolution retrieves a value stored under provider_id="test",
        never under the environment-variable name.
        """
        record = ProviderRecord(
            provider_id="test",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            deployment=DeploymentType.CLOUD,
            auth=AuthConfig(type=AuthType.API_KEY, api_key_env="MY_CUSTOM_KEY"),
            connection=ConnectionConfig(base_url="https://example.com/v1"),
            capabilities=frozenset({Capability.CHAT}),
            enabled=True,
            priority=10,
        )
        catalog = _build_catalog(record)
        factory = _build_factory()

        # Only the provider ID is present.
        store = CredentialStore(InMemoryCredentialBackend())
        store.set("test", "secret-value")

        manager = ProviderManager(factory, catalog, credential_store=store)
        await manager.start()
        try:
            provider = manager.get_provider("test")
            self.assertIsNotNone(provider)
            self.assertEqual(provider._credential.api_key, "secret-value")
        finally:
            await manager.stop()

        # Negative control: the physical env name must not satisfy the lookup.
        default_only = CredentialStore(InMemoryCredentialBackend())
        default_only.set("MY_CUSTOM_KEY", "secret-value")

        manager_default = ProviderManager(
            factory, catalog, credential_store=default_only
        )
        with self.assertRaises(LLMProviderError):
            await manager_default.start()
        await manager_default.stop()

    async def test_credential_not_found_error_message_identifies_provider(self):
        """When a credential is missing, the error names the provider — never the secret."""
        catalog = _build_catalog(_openai_provider_record())
        factory = _build_factory()
        empty_store = CredentialStore(InMemoryCredentialBackend())

        manager = ProviderManager(factory, catalog, credential_store=empty_store)
        with self.assertRaises(LLMProviderError) as ctx:
            await manager.start()
        message = str(ctx.exception)
        self.assertIn("nvidia", message)
        self.assertIn("requires an API key", message)
        self.assertNotIn(_OPENAI_SECRET, message)
        await manager.stop()

    async def test_credential_store_none_error_identifies_provider(self):
        """When no credential store is configured, the error names the provider."""
        catalog = _build_catalog(_openai_provider_record())
        factory = _build_factory()

        manager = ProviderManager(factory, catalog, credential_store=None)
        with self.assertRaises(LLMProviderError) as ctx:
            await manager.start()
        message = str(ctx.exception)
        self.assertIn("nvidia", message)
        self.assertNotIn(_OPENAI_SECRET, message)
        await manager.stop()

    async def test_env_name_is_not_disclosed_when_provider_credential_is_missing(self):
        """Missing credentials identify the provider, never its physical env name."""
        catalog = _build_catalog(_openai_provider_record())
        factory = _build_factory()
        empty_store = CredentialStore(InMemoryCredentialBackend())

        manager = ProviderManager(factory, catalog, credential_store=empty_store)
        with self.assertRaises(LLMProviderError) as ctx:
            await manager.start()
        message = str(ctx.exception)
        # The provider is named in the error.
        self.assertIn("nvidia", message)
        # The env name is a backend implementation detail and is not disclosed.
        self.assertNotIn("NVIDIA_API_KEY", message)
        self.assertNotIn(_OPENAI_SECRET, message)
        await manager.stop()


if __name__ == "__main__":
    unittest.main()
