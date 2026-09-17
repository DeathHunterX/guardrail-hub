"""Unit tests for the credential setup service.

These exercise :class:`CredentialSetupService` in isolation using in-memory
fakes for every port (secret prompt, AWS detector, output). No real terminal,
AWS SDK, or OS keyring is involved, and the secret never passes through real
I/O.

Covered behaviours (mapping to the Phase 4 spec §6):
    - provider without authentication (auth.type none / absent)
    - missing api_key -> prompt -> secure storage
    - existing api_key -> no prompt (already configured)
    - the secret is stored (credential storage)
    - multiple providers configured in one run
    - AWS provider: detected / unavailable (never stored)
    - reconfigure forces a re-prompt for an existing credential
    - empty input -> missing (nothing stored)
    - disabled provider is skipped (never prompted)
    - a non-"not found" backend error propagates
    - secrets never appear in output lines or in outcome detail
"""

import unittest
from typing import List, Optional

from app.intelligence.credentials import (
    CredentialBackend,
    CredentialBackendError,
    CredentialNotFoundError,
    CredentialStore,
    InMemoryCredentialBackend,
)
from app.intelligence.registry.models.provider import (
    AUTH_TYPE_DEFAULT_SENTINEL,
    AuthConfig,
    AuthType,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.provider import ProviderType
from app.intelligence.setup.plan import (
    ProviderAuthKind,
    SetupOperation,
    SetupOutcomeStatus,
)
from app.intelligence.setup.service import CredentialSetupService


# A recognisable fake secret. If this string ever appears in rendered output
# or in an outcome detail, a test fails — that is the leak detector.
_SECRET = "sk-SECRET-do-not-leak-0001"


# ------------------------------------------------------------------
# Fakes for the setup ports
# ------------------------------------------------------------------


class FakeSecretPrompt:
    """Records prompts and returns queued secrets (hidden-input stand-in)."""

    def __init__(self, values: Optional[List[str]] = None) -> None:
        # Values returned in order, one per read_secret() call.
        self._values = list(values) if values is not None else []
        self.prompts: List[str] = []
        self.call_count = 0

    def read_secret(self, prompt_text: str) -> str:
        self.prompts.append(prompt_text)
        self.call_count += 1
        if self._values:
            return self._values.pop(0)
        return ""


class FakeAwsDetector:
    """AWS credential detector stub with a configurable result."""

    def __init__(self, available: bool) -> None:
        self._available = available
        self.call_count = 0

    def is_available(self) -> bool:
        self.call_count += 1
        return self._available


class BufferOutput:
    """Collects rendered output lines for assertions."""

    def __init__(self) -> None:
        self.lines: List[str] = []

    def write_line(self, text: str) -> None:
        self.lines.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class FailingGetBackend(CredentialBackend):
    """Backend whose get() raises a non-"not found" backend error."""

    def get(self, provider_id: str) -> str:
        raise CredentialBackendError(provider_id, "keyring unavailable")

    def set(self, provider_id: str, credential: str) -> None:  # pragma: no cover
        raise CredentialBackendError(provider_id, "keyring unavailable")

    def delete(self, provider_id: str) -> None:  # pragma: no cover
        raise CredentialBackendError(provider_id, "keyring unavailable")


# ------------------------------------------------------------------
# Provider fixtures
# ------------------------------------------------------------------


def make_provider(
    provider_id: str,
    *,
    auth_type=AUTH_TYPE_DEFAULT_SENTINEL,
    api_key_env: Optional[str] = None,
    provider_type: ProviderType = ProviderType.OPENAI_COMPATIBLE,
    deployment: DeploymentType = DeploymentType.CLOUD,
    region: Optional[str] = None,
    enabled: bool = True,
) -> ProviderRecord:
    """Build a ProviderRecord for tests without going through the YAML loader."""
    return ProviderRecord(
        provider_id=provider_id,
        provider_type=provider_type,
        deployment=deployment,
        auth=AuthConfig(type=auth_type, api_key_env=api_key_env),
        connection=ConnectionConfig(base_url="", region=region),
        enabled=enabled,
    )


def build_service(
    *,
    store: CredentialStore,
    prompt: FakeSecretPrompt,
    detector: FakeAwsDetector,
    output: BufferOutput,
    reconfigure=frozenset(),
    operation=SetupOperation.CONFIGURE,
    credential_locations=None,
) -> CredentialSetupService:
    return CredentialSetupService(
        credential_store=store,
        secret_prompt=prompt,
        aws_detector=detector,
        output=output,
        reconfigure=reconfigure,
        operation=operation,
        credential_locations=credential_locations,
    )


# ------------------------------------------------------------------
# No-authentication providers
# ------------------------------------------------------------------


class NoAuthProviderTests(unittest.TestCase):
    """Providers with auth.type none / absent require no credential."""

    def _run_single(self, provider: ProviderRecord):
        store = CredentialStore(InMemoryCredentialBackend())
        prompt = FakeSecretPrompt()
        detector = FakeAwsDetector(available=True)
        out = BufferOutput()
        service = build_service(
            store=store, prompt=prompt, detector=detector, output=out
        )
        report = service.run([provider])
        return report, prompt, out

    def test_explicit_none_requires_no_credential(self):
        provider = make_provider(
            "ollama-local",
            auth_type=AuthType.NONE,
            provider_type=ProviderType.OLLAMA,
            deployment=DeploymentType.SELF_HOSTED,
        )
        report, prompt, out = self._run_single(provider)

        self.assertTrue(report.ok)
        outcome = report.outcomes[0]
        self.assertEqual(outcome.auth_kind, ProviderAuthKind.NONE)
        self.assertEqual(outcome.status, SetupOutcomeStatus.NO_CREDENTIAL_REQUIRED)
        self.assertEqual(prompt.call_count, 0)
        self.assertIn("No credential required", out.text)

    def test_absent_auth_type_requires_no_credential(self):
        # auth.type omitted from YAML -> AUTH_TYPE_DEFAULT_SENTINEL.
        provider = make_provider("legacy-provider")
        report, prompt, out = self._run_single(provider)

        self.assertTrue(report.ok)
        self.assertEqual(
            report.outcomes[0].status, SetupOutcomeStatus.NO_CREDENTIAL_REQUIRED
        )
        self.assertEqual(prompt.call_count, 0)


# ------------------------------------------------------------------
# API-key providers
# ------------------------------------------------------------------


class ApiKeyProviderTests(unittest.TestCase):
    """api_key providers prompt only when missing and store securely."""

    def setUp(self):
        self.store = CredentialStore(InMemoryCredentialBackend())
        self.out = BufferOutput()

    def test_missing_credential_is_prompted_and_stored(self):
        prompt = FakeSecretPrompt(values=[_SECRET])
        detector = FakeAwsDetector(available=False)
        service = build_service(
            store=self.store, prompt=prompt, detector=detector, output=self.out
        )
        provider = make_provider("openai-cloud", auth_type=AuthType.API_KEY)

        report = service.run([provider])

        outcome = report.outcomes[0]
        self.assertEqual(outcome.status, SetupOutcomeStatus.STORED)
        self.assertTrue(report.ok)
        # The prompt was invoked exactly once, using hidden input.
        self.assertEqual(prompt.call_count, 1)
        # Credential storage: the entered secret is now retrievable.
        self.assertEqual(self.store.get("openai-cloud"), _SECRET)

    def test_existing_credential_is_not_prompted(self):
        # Pre-seed a stored credential.
        self.store.set("openai-cloud", _SECRET)
        prompt = FakeSecretPrompt(values=["SHOULD-NOT-BE-USED"])
        detector = FakeAwsDetector(available=False)
        service = build_service(
            store=self.store, prompt=prompt, detector=detector, output=self.out
        )
        provider = make_provider("openai-cloud", auth_type=AuthType.API_KEY)

        report = service.run([provider])

        outcome = report.outcomes[0]
        self.assertEqual(outcome.status, SetupOutcomeStatus.ALREADY_CONFIGURED)
        self.assertTrue(report.ok)
        self.assertEqual(prompt.call_count, 0)
        # The original value is untouched.
        self.assertEqual(self.store.get("openai-cloud"), _SECRET)

    def test_empty_input_reports_missing_and_stores_nothing(self):
        prompt = FakeSecretPrompt(values=["   "])  # whitespace only
        detector = FakeAwsDetector(available=False)
        service = build_service(
            store=self.store, prompt=prompt, detector=detector, output=self.out
        )
        provider = make_provider("openai-cloud", auth_type=AuthType.API_KEY)

        report = service.run([provider])

        outcome = report.outcomes[0]
        self.assertEqual(outcome.status, SetupOutcomeStatus.MISSING)
        self.assertFalse(report.ok)
        # Nothing was stored.
        with self.assertRaises(CredentialNotFoundError):
            self.store.get("openai-cloud")

    def test_reconfigure_forces_reprompt_and_replaces(self):
        self.store.set("openai-cloud", "old-value")
        new_secret = "sk-NEW-SECRET-0002"
        prompt = FakeSecretPrompt(values=[new_secret])
        detector = FakeAwsDetector(available=False)
        service = build_service(
            store=self.store,
            prompt=prompt,
            detector=detector,
            output=self.out,
            reconfigure=frozenset({"openai-cloud"}),
        )
        provider = make_provider("openai-cloud", auth_type=AuthType.API_KEY)

        report = service.run([provider])

        self.assertEqual(report.outcomes[0].status, SetupOutcomeStatus.STORED)
        self.assertEqual(prompt.call_count, 1)
        self.assertEqual(self.store.get("openai-cloud"), new_secret)

    def test_backend_error_on_lookup_propagates(self):
        # A non-"not found" backend failure must not be swallowed.
        store = CredentialStore(FailingGetBackend())
        prompt = FakeSecretPrompt(values=[_SECRET])
        detector = FakeAwsDetector(available=False)
        service = build_service(
            store=store, prompt=prompt, detector=detector, output=self.out
        )
        provider = make_provider("openai-cloud", auth_type=AuthType.API_KEY)

        with self.assertRaises(CredentialBackendError):
            service.run([provider])
        # We never prompted, because the lookup failed first.
        self.assertEqual(prompt.call_count, 0)


class ValidateApiKeyProviderTests(unittest.TestCase):
    """Validation checks externally managed credentials without changing them."""

    def test_missing_credential_is_reported_without_prompting_or_storing(self):
        store = CredentialStore(InMemoryCredentialBackend())
        prompt = FakeSecretPrompt(values=[_SECRET])
        out = BufferOutput()
        service = build_service(
            store=store,
            prompt=prompt,
            detector=FakeAwsDetector(available=False),
            output=out,
            operation=SetupOperation.VALIDATE,
            credential_locations={"openai-cloud": "/run/secrets/openai-cloud"},
        )

        report = service.run(
            [make_provider("openai-cloud", auth_type=AuthType.API_KEY)]
        )

        self.assertEqual(report.outcomes[0].status, SetupOutcomeStatus.MISSING)
        self.assertFalse(report.ok)
        self.assertEqual(prompt.call_count, 0)
        with self.assertRaises(CredentialNotFoundError):
            store.get("openai-cloud")
        self.assertIn("/run/secrets/openai-cloud", out.text)
        self.assertNotIn(_SECRET, out.text)

    def test_existing_credential_validates_without_prompting_or_storing(self):
        backend = InMemoryCredentialBackend()
        backend.set("openai-cloud", _SECRET)
        store = CredentialStore(backend)
        prompt = FakeSecretPrompt(values=["replacement-must-not-be-used"])
        out = BufferOutput()
        service = build_service(
            store=store,
            prompt=prompt,
            detector=FakeAwsDetector(available=False),
            output=out,
            operation=SetupOperation.VALIDATE,
            credential_locations={"openai-cloud": "OPENAI_API_KEY"},
        )

        report = service.run(
            [make_provider("openai-cloud", auth_type=AuthType.API_KEY)]
        )

        self.assertTrue(report.ok)
        self.assertEqual(
            report.outcomes[0].status, SetupOutcomeStatus.ALREADY_CONFIGURED
        )
        self.assertEqual(prompt.call_count, 0)
        self.assertEqual(store.get("openai-cloud"), _SECRET)


# ------------------------------------------------------------------
# AWS providers
# ------------------------------------------------------------------


class AwsProviderTests(unittest.TestCase):
    """AWS providers detect the credential chain and never store anything."""

    def test_aws_detected(self):
        store = CredentialStore(InMemoryCredentialBackend())
        prompt = FakeSecretPrompt()
        detector = FakeAwsDetector(available=True)
        out = BufferOutput()
        service = build_service(
            store=store, prompt=prompt, detector=detector, output=out
        )
        provider = make_provider(
            "bedrock",
            auth_type=AuthType.AWS,
            provider_type=ProviderType.BEDROCK,
            region="us-east-1",
        )

        report = service.run([provider])

        outcome = report.outcomes[0]
        self.assertEqual(outcome.auth_kind, ProviderAuthKind.AWS)
        self.assertEqual(outcome.status, SetupOutcomeStatus.AWS_DETECTED)
        self.assertTrue(report.ok)
        self.assertEqual(detector.call_count, 1)
        # AWS credentials are delegated to the SDK — never prompted or stored.
        self.assertEqual(prompt.call_count, 0)

    def test_aws_unavailable_reports_failure(self):
        store = CredentialStore(InMemoryCredentialBackend())
        prompt = FakeSecretPrompt()
        detector = FakeAwsDetector(available=False)
        out = BufferOutput()
        service = build_service(
            store=store, prompt=prompt, detector=detector, output=out
        )
        provider = make_provider(
            "bedrock",
            auth_type=AuthType.AWS,
            provider_type=ProviderType.BEDROCK,
            region="us-east-1",
        )

        report = service.run([provider])

        outcome = report.outcomes[0]
        self.assertEqual(outcome.status, SetupOutcomeStatus.AWS_UNAVAILABLE)
        self.assertFalse(report.ok)
        self.assertEqual(prompt.call_count, 0)


# ------------------------------------------------------------------
# Disabled providers
# ------------------------------------------------------------------


class DisabledProviderTests(unittest.TestCase):
    """Disabled providers are skipped and never prompted."""

    def test_disabled_api_key_provider_is_skipped(self):
        store = CredentialStore(InMemoryCredentialBackend())
        prompt = FakeSecretPrompt(values=["SHOULD-NOT-BE-USED"])
        detector = FakeAwsDetector(available=True)
        out = BufferOutput()
        service = build_service(
            store=store, prompt=prompt, detector=detector, output=out
        )
        provider = make_provider(
            "openai-cloud", auth_type=AuthType.API_KEY, enabled=False
        )

        report = service.run([provider])

        outcome = report.outcomes[0]
        self.assertEqual(outcome.status, SetupOutcomeStatus.SKIPPED_DISABLED)
        # Disabled providers do not count as failures.
        self.assertTrue(report.ok)
        self.assertEqual(prompt.call_count, 0)


# ------------------------------------------------------------------
# Multiple providers in one run
# ------------------------------------------------------------------


class MultipleProviderTests(unittest.TestCase):
    """One llm.yaml with several providers is configured in a single run."""

    def test_mixed_providers_configured_together(self):
        store = CredentialStore(InMemoryCredentialBackend())
        prompt = FakeSecretPrompt(values=[_SECRET])
        detector = FakeAwsDetector(available=True)
        out = BufferOutput()
        service = build_service(
            store=store, prompt=prompt, detector=detector, output=out
        )
        providers = [
            make_provider(
                "ollama-local",
                auth_type=AuthType.NONE,
                provider_type=ProviderType.OLLAMA,
                deployment=DeploymentType.SELF_HOSTED,
            ),
            make_provider("openai-cloud", auth_type=AuthType.API_KEY),
            make_provider(
                "bedrock",
                auth_type=AuthType.AWS,
                provider_type=ProviderType.BEDROCK,
                region="us-east-1",
            ),
        ]

        report = service.run(providers)

        self.assertTrue(report.ok)
        statuses = {o.provider_id: o.status for o in report.outcomes}
        self.assertEqual(
            statuses["ollama-local"], SetupOutcomeStatus.NO_CREDENTIAL_REQUIRED
        )
        self.assertEqual(statuses["openai-cloud"], SetupOutcomeStatus.STORED)
        self.assertEqual(statuses["bedrock"], SetupOutcomeStatus.AWS_DETECTED)
        # Exactly one prompt (only the api_key provider needed one).
        self.assertEqual(prompt.call_count, 1)
        self.assertEqual(store.get("openai-cloud"), _SECRET)


# ------------------------------------------------------------------
# Secret-leak guardrails
# ------------------------------------------------------------------


class SecretLeakGuardTests(unittest.TestCase):
    """The secret must never appear in rendered output or outcome details."""

    def test_secret_never_appears_in_output_or_outcomes(self):
        store = CredentialStore(InMemoryCredentialBackend())
        prompt = FakeSecretPrompt(values=[_SECRET])
        detector = FakeAwsDetector(available=True)
        out = BufferOutput()
        service = build_service(
            store=store, prompt=prompt, detector=detector, output=out
        )
        provider = make_provider("openai-cloud", auth_type=AuthType.API_KEY)

        report = service.run([provider])

        # Rendered output must not contain the secret anywhere.
        self.assertNotIn(_SECRET, out.text)
        # Nor may any outcome detail carry it.
        for outcome in report.outcomes:
            self.assertNotIn(_SECRET, outcome.detail)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
