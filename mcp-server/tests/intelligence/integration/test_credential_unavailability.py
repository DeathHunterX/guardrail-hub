"""Regression tests for graceful LLM credential unavailability."""

from types import SimpleNamespace
import unittest
from unittest import mock
from unittest.mock import MagicMock

from app.core.startup import run_startup_sequence
from app.intelligence.credentials import (
    CredentialBackendError,
    CredentialStore,
    InMemoryCredentialBackend,
)
from app.intelligence.exceptions import (
    LLMConfigurationError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMUnavailableError,
)
from app.intelligence.inference.services.llm_service import LLMService
from app.intelligence.ports.chat import ChatMessage, ChatResponse
from app.intelligence.providers.base_provider import BaseProviderRuntime
from app.intelligence.providers.provider_factory import ProviderFactory
from app.intelligence.providers.provider_manager import ProviderManager
from app.intelligence.registry.catalog.catalog import ModelCatalog
from app.intelligence.registry.models.model import ModelRecord, ModelType
from app.intelligence.registry.models.provider import (
    AuthConfig,
    AuthType,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType


UNAVAILABLE_MESSAGE = (
    "LLM functionality is unavailable because no LLM credentials "
    "have been configured."
)


class _ChatProvider(BaseProviderRuntime):
    """Network-free provider used to exercise the real manager lifecycle."""

    @property
    def provider_id(self):
        return self._record.provider_id

    @property
    def provider_type(self):
        return self._record.provider_type.value

    @property
    def capabilities(self):
        return self._record.capabilities

    def validate_configuration(self):
        if self._record.provider_id == "invalid-provider":
            raise LLMConfigurationError("invalid non-credential configuration")

    async def start(self):
        if self._record.provider_id == "lifecycle-provider":
            raise RuntimeError("non-credential lifecycle failure")
        await super().start()

    async def chat(self, messages, options):
        return ChatResponse(
            content=f"response from {self.provider_id}",
            model=options.model,
            finish_reason="stop",
        )


class _BrokenCredentialBackend(InMemoryCredentialBackend):
    def get(self, provider_id: str) -> str:
        raise CredentialBackendError(provider_id, "credential backend unavailable")


def _provider(
    provider_id: str,
    provider_type: ProviderType,
    deployment: DeploymentType,
    *,
    auth_type: AuthType = AuthType.NONE,
    priority: int,
) -> ProviderRecord:
    return ProviderRecord(
        provider_id=provider_id,
        provider_type=provider_type,
        deployment=deployment,
        auth=AuthConfig(type=auth_type),
        connection=ConnectionConfig(base_url="https://example.test/v1"),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=priority,
    )


def _catalog(*providers: ProviderRecord) -> ModelCatalog:
    catalog = ModelCatalog()
    for provider in providers:
        catalog.register_provider(provider)
        catalog.register_model(
            ModelRecord(
                provider_id=provider.provider_id,
                model_id=f"{provider.provider_id}-model",
                model_type=ModelType.CHAT,
                capabilities=frozenset({Capability.CHAT}),
                context_window=4096,
                priority=provider.priority,
            )
        )
    catalog.freeze()
    return catalog


def _factory() -> ProviderFactory:
    factory = ProviderFactory()
    factory.register(ProviderType.OLLAMA.value, _ChatProvider)
    factory.register(ProviderType.OPENAI_COMPATIBLE.value, _ChatProvider)
    return factory


class TestCredentialUnavailableProviderManager(unittest.IsolatedAsyncioTestCase):
    async def test_api_key_provider_starts_when_credential_is_present(self):
        credentialed = _provider(
            "credentialed-cloud",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.CLOUD,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        backend = InMemoryCredentialBackend()
        backend.set(credentialed.provider_id, "test-only-secret")
        manager = ProviderManager(
            _factory(),
            _catalog(credentialed),
            credential_store=CredentialStore(backend),
        )

        await manager.start()
        try:
            self.assertEqual(manager.list_providers(), [credentialed.provider_id])
            self.assertFalse(
                manager.is_credential_unavailable(credentialed.provider_id)
            )
        finally:
            await manager.stop()

    async def test_missing_api_key_marks_only_affected_provider_unavailable(self):
        missing = _provider(
            "missing-cloud",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.SELF_HOSTED,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        available = _provider(
            "available-local",
            ProviderType.OLLAMA,
            DeploymentType.LOCAL,
            priority=10,
        )
        backend = InMemoryCredentialBackend()
        manager = ProviderManager(
            _factory(),
            _catalog(missing, available),
            credential_store=CredentialStore(backend),
        )

        await manager.start()
        try:
            self.assertTrue(manager.initialized)
            self.assertEqual(manager.list_providers(), [available.provider_id])
            self.assertTrue(manager.is_credential_unavailable(missing.provider_id))
            self.assertFalse(manager.is_credential_unavailable(available.provider_id))
        finally:
            await manager.stop()

    async def test_missing_credential_store_is_nonfatal_for_api_key_provider(self):
        missing = _provider(
            "missing-cloud",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.CLOUD,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        manager = ProviderManager(_factory(), _catalog(missing), credential_store=None)

        await manager.start()
        try:
            self.assertTrue(manager.initialized)
            self.assertEqual(manager.provider_count, 0)
            self.assertTrue(manager.is_credential_unavailable(missing.provider_id))
        finally:
            await manager.stop()

    async def test_unrelated_configuration_failure_remains_fatal(self):
        invalid = _provider(
            "invalid-provider",
            ProviderType.OLLAMA,
            DeploymentType.LOCAL,
            priority=1,
        )
        manager = ProviderManager(_factory(), _catalog(invalid))

        with self.assertRaises(LLMProviderError) as ctx:
            await manager.start()

        self.assertIn("invalid non-credential configuration", str(ctx.exception))
        self.assertFalse(manager.initialized)

    async def test_credential_backend_failure_remains_fatal(self):
        provider = _provider(
            "credentialed-cloud",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.CLOUD,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        manager = ProviderManager(
            _factory(),
            _catalog(provider),
            credential_store=CredentialStore(_BrokenCredentialBackend()),
        )

        with self.assertRaises(LLMProviderError) as ctx:
            await manager.start()

        self.assertIn("credential backend unavailable", str(ctx.exception))
        self.assertFalse(manager.initialized)

    async def test_unrelated_lifecycle_failure_remains_fatal(self):
        lifecycle_failure = _provider(
            "lifecycle-provider",
            ProviderType.OLLAMA,
            DeploymentType.LOCAL,
            priority=1,
        )
        manager = ProviderManager(_factory(), _catalog(lifecycle_failure))

        with self.assertRaises(LLMProviderError) as ctx:
            await manager.start()

        self.assertIn("non-credential lifecycle failure", str(ctx.exception))
        self.assertFalse(manager.initialized)

    async def test_fatal_start_clears_partial_credential_unavailability_state(self):
        missing = _provider(
            "missing-cloud",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.CLOUD,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        invalid = _provider(
            "invalid-provider",
            ProviderType.OLLAMA,
            DeploymentType.LOCAL,
            priority=2,
        )
        manager = ProviderManager(
            _factory(),
            _catalog(missing, invalid),
            credential_store=CredentialStore(InMemoryCredentialBackend()),
        )

        with self.assertRaises(LLMProviderError):
            await manager.start()

        self.assertEqual(manager.credential_unavailable_providers, ())
        self.assertFalse(manager.initialized)


class TestCredentialUnavailableRouting(unittest.IsolatedAsyncioTestCase):
    async def test_implicit_request_uses_eligible_available_provider(self):
        missing_preferred = _provider(
            "missing-preferred",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.SELF_HOSTED,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        available = _provider(
            "available-fallback",
            ProviderType.OLLAMA,
            DeploymentType.LOCAL,
            priority=10,
        )
        catalog = _catalog(missing_preferred, available)
        manager = ProviderManager(
            _factory(),
            catalog,
            credential_store=CredentialStore(InMemoryCredentialBackend()),
        )
        await manager.start()
        try:
            service = LLMService(manager, catalog)
            response = await service.chat([ChatMessage(role="user", content="hello")])
            self.assertEqual(response.content, "response from available-fallback")
            self.assertEqual(response.model, "available-fallback-model")
        finally:
            await manager.stop()

    async def test_request_with_no_usable_provider_raises_common_unavailable_error(self):
        missing = _provider(
            "missing-cloud",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.CLOUD,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        catalog = _catalog(missing)
        manager = ProviderManager(
            _factory(),
            catalog,
            credential_store=CredentialStore(InMemoryCredentialBackend()),
        )
        await manager.start()
        try:
            service = LLMService(manager, catalog)
            with self.assertRaises(LLMUnavailableError) as ctx:
                await service.chat([ChatMessage(role="user", content="hello")])
            self.assertEqual(str(ctx.exception), UNAVAILABLE_MESSAGE)
        finally:
            await manager.stop()

    async def test_explicit_missing_provider_does_not_fall_back(self):
        missing = _provider(
            "missing-cloud",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.CLOUD,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        available = _provider(
            "available-local",
            ProviderType.OLLAMA,
            DeploymentType.LOCAL,
            priority=10,
        )
        catalog = _catalog(missing, available)
        manager = ProviderManager(
            _factory(),
            catalog,
            credential_store=CredentialStore(InMemoryCredentialBackend()),
        )
        await manager.start()
        try:
            service = LLMService(manager, catalog)
            with self.assertRaises(LLMUnavailableError) as ctx:
                await service.chat(
                    [ChatMessage(role="user", content="hello")],
                    provider=missing.provider_id,
                )
            self.assertEqual(str(ctx.exception), UNAVAILABLE_MESSAGE)
        finally:
            await manager.stop()

    async def test_explicit_missing_model_does_not_fall_back(self):
        missing = _provider(
            "missing-cloud",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.CLOUD,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        available = _provider(
            "available-local",
            ProviderType.OLLAMA,
            DeploymentType.LOCAL,
            priority=10,
        )
        catalog = _catalog(missing, available)
        manager = ProviderManager(
            _factory(),
            catalog,
            credential_store=CredentialStore(InMemoryCredentialBackend()),
        )
        await manager.start()
        try:
            service = LLMService(manager, catalog)
            with self.assertRaises(LLMUnavailableError) as ctx:
                await service.chat(
                    [ChatMessage(role="user", content="hello")],
                    model="missing-cloud-model",
                )
            self.assertEqual(str(ctx.exception), UNAVAILABLE_MESSAGE)
        finally:
            await manager.stop()

    async def test_unknown_model_preserves_model_not_found_error(self):
        available = _provider(
            "available-local",
            ProviderType.OLLAMA,
            DeploymentType.LOCAL,
            priority=10,
        )
        catalog = _catalog(available)
        manager = ProviderManager(_factory(), catalog)
        await manager.start()
        try:
            service = LLMService(manager, catalog)
            with self.assertRaises(LLMModelNotFoundError):
                await service.chat(
                    [ChatMessage(role="user", content="hello")],
                    model="unknown-model",
                )
        finally:
            await manager.stop()

    async def test_model_provider_mismatch_preserves_provider_error(self):
        available = _provider(
            "available-local",
            ProviderType.OLLAMA,
            DeploymentType.LOCAL,
            priority=10,
        )
        catalog = _catalog(available)
        manager = ProviderManager(_factory(), catalog)
        await manager.start()
        try:
            service = LLMService(manager, catalog)
            with self.assertRaises(LLMProviderError) as ctx:
                await service.chat(
                    [ChatMessage(role="user", content="hello")],
                    model="available-local-model",
                    provider="different-provider",
                )
            self.assertIn("not 'different-provider'", str(ctx.exception))
        finally:
            await manager.stop()


class TestCredentialUnavailableApplicationStartup(unittest.IsolatedAsyncioTestCase):
    async def test_missing_llm_credential_does_not_block_non_llm_dispatchers(self):
        missing = _provider(
            "missing-cloud",
            ProviderType.OPENAI_COMPATIBLE,
            DeploymentType.CLOUD,
            auth_type=AuthType.API_KEY,
            priority=1,
        )
        catalog = _catalog(missing)
        manager = ProviderManager(
            _factory(),
            catalog,
            credential_store=CredentialStore(InMemoryCredentialBackend()),
        )
        registry_runtime = MagicMock(catalog=catalog)
        dao = MagicMock()
        dao.get_by_status.return_value = []
        operation_service = MagicMock()
        flow = SimpleNamespace(
            operation_service=operation_service,
            notification_service=SimpleNamespace(channels=[]),
            notifier=None,
        )
        zap_dispatcher = MagicMock()
        jmeter_dispatcher = MagicMock()

        with (
            mock.patch(
                "app.bootstrap.build_registry_runtime",
                return_value=registry_runtime,
            ),
            mock.patch(
                "app.core.startup._build_conversation_service",
                return_value=(manager, MagicMock()),
            ),
            mock.patch("app.dao.operation_dao.get_operation_dao", return_value=dao),
            mock.patch(
                "app.bootstrap.build_operation_notification_flow_from_settings",
                return_value=flow,
            ),
            mock.patch(
                "app.bootstrap.build_zap_dispatcher",
                return_value=zap_dispatcher,
            ),
            mock.patch(
                "app.bootstrap.build_jmeter_dispatcher",
                return_value=jmeter_dispatcher,
            ),
        ):
            result = await run_startup_sequence(
                SimpleNamespace(database_provider="POSTGRES")
            )

        self.assertIs(result.provider_manager, manager)
        self.assertTrue(manager.is_credential_unavailable(missing.provider_id))
        zap_dispatcher.start.assert_called_once_with()
        jmeter_dispatcher.start.assert_called_once_with()
        await manager.stop()


class TestConversationUnavailableErrorMapping(unittest.TestCase):
    def test_existing_llm_unavailable_mapping_returns_503(self):
        from app.routers.public.conversation_router import _map_llm_error

        mapped = _map_llm_error(LLMUnavailableError(UNAVAILABLE_MESSAGE))

        self.assertEqual(mapped.status_code, 503)
        self.assertEqual(mapped.detail, UNAVAILABLE_MESSAGE)


if __name__ == "__main__":
    unittest.main()
