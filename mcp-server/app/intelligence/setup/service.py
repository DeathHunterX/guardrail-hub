"""CredentialSetupService — the local credential bootstrap workflow.

Given the providers declared in llm.yaml and a CredentialStore, this service:

  1. Enumerates the (enabled) configured providers.
  2. Derives each provider's credential requirement from ``auth.type``.
  3. For api_key providers in configure mode: reuses an existing stored
     credential, or prompts (hidden input) and stores a missing one securely.
  4. For api_key providers in validate mode: checks the selected externally
     managed backend and reports the expected location without prompting/writing.
  5. For aws providers: detects the AWS SDK credential chain; stores nothing.
  6. For none / unauthenticated providers: does nothing.

Security properties (enforced by construction):

  - The secret only ever travels prompt -> CredentialStore.set(); it is never
    placed in an outcome, returned, logged, or included in an exception.
  - Behaviour is keyed off ``auth.type``, never off a hard-coded provider id.
  - llm.yaml is never written; no .env file is created or read.

Configuration loading and validation happen at the CLI boundary; this service
receives already-validated provider records and is pure orchestration over its
injected ports, which makes it fully testable without a terminal, the AWS SDK,
or an OS keyring.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable, List, Mapping, Optional

from app.intelligence.credentials import CredentialNotFoundError, CredentialStore
from app.intelligence.registry.models.provider import ProviderRecord
from app.intelligence.setup.plan import (
    ProviderAuthKind,
    ProviderSetupOutcome,
    SetupOperation,
    SetupOutcomeStatus,
    SetupReport,
    auth_kind_label,
    classify_auth,
)
from app.intelligence.setup.ports import (
    AwsCredentialDetector,
    OutputWriter,
    SecretPrompt,
)


class CredentialSetupService:
    """Runs the credential bootstrap workflow over a set of provider records."""

    def __init__(
        self,
        *,
        credential_store: CredentialStore,
        secret_prompt: SecretPrompt,
        aws_detector: AwsCredentialDetector,
        output: OutputWriter,
        reconfigure: Optional[FrozenSet[str]] = None,
        operation: SetupOperation = SetupOperation.CONFIGURE,
        credential_locations: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Construct the service.

        Args:
            credential_store: Where api_key credentials are stored/retrieved.
            secret_prompt: Hidden-input port used only for missing api_keys.
            aws_detector: Presence check for the AWS SDK credential chain.
            output: User-facing output sink (never receives a secret).
            reconfigure: provider_ids for which an existing api_key credential
                should be replaced (re-prompted) even if one is already stored.
            operation: Configure writable local credentials or validate
                externally managed credentials without prompting or writing.
            credential_locations: Secret-free provider-to-location labels used
                to tell operators where a missing external credential belongs.
        """
        self._store = credential_store
        self._prompt = secret_prompt
        self._aws_detector = aws_detector
        self._output = output
        self._reconfigure = reconfigure or frozenset()
        self._operation = operation
        self._credential_locations = dict(credential_locations or {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, providers: Iterable[ProviderRecord]) -> SetupReport:
        """Configure every provider and return an aggregate report.

        Raises:
            CredentialStoreError: If the credential backend fails (e.g. the OS
                keyring is unavailable). Expected "not found" lookups are
                handled internally and never raise out of this method.
        """
        action = (
            "Validating LLM provider credentials..."
            if self._operation is SetupOperation.VALIDATE
            else "Configuring LLM providers..."
        )
        self._output.write_line(action)

        outcomes: List[ProviderSetupOutcome] = []
        for provider in providers:
            outcomes.append(self._configure_provider(provider))

        report = SetupReport(outcomes=tuple(outcomes))

        self._output.write_line("")
        if report.ok:
            completion = (
                "Validation complete."
                if self._operation is SetupOperation.VALIDATE
                else "Setup complete."
            )
            self._output.write_line(completion)
        else:
            self._output.write_line(
                "Setup incomplete: one or more providers still need credentials "
                "(see messages above)."
            )
        return report

    # ------------------------------------------------------------------
    # Internal — per-provider
    # ------------------------------------------------------------------

    def _configure_provider(self, provider: ProviderRecord) -> ProviderSetupOutcome:
        """Configure a single provider and return its outcome."""
        kind = classify_auth(provider.auth)

        # Header block for this provider (display only; no secrets).
        self._output.write_line("")
        self._output.write_line(provider.provider_id)
        self._output.write_line(f"  Authentication: {auth_kind_label(kind)}")

        # Disabled providers are not configured — they will not run.
        if not provider.enabled:
            return self._report(
                provider,
                kind,
                SetupOutcomeStatus.SKIPPED_DISABLED,
                "- Disabled in configuration; skipped",
            )

        if kind is ProviderAuthKind.API_KEY:
            return self._configure_api_key_provider(provider, kind)
        if kind is ProviderAuthKind.AWS:
            return self._configure_aws_provider(provider, kind)
        return self._report(
            provider,
            kind,
            SetupOutcomeStatus.NO_CREDENTIAL_REQUIRED,
            "✓ No credential required",
        )

    def _configure_api_key_provider(
        self, provider: ProviderRecord, kind: ProviderAuthKind
    ) -> ProviderSetupOutcome:
        """Resolve or prompt-and-store the api_key credential for a provider."""
        provider_id = provider.provider_id
        force_replace = (
            self._operation is SetupOperation.CONFIGURE
            and provider_id in self._reconfigure
        )

        # Reuse an existing credential unless the operator asked to replace it.
        # A CredentialNotFoundError is the expected "needs prompting" signal;
        # any other backend error propagates to the caller unchanged.
        if not force_replace:
            try:
                self._store.get(provider_id)
            except CredentialNotFoundError:
                pass
            else:
                return self._report(
                    provider,
                    kind,
                    SetupOutcomeStatus.ALREADY_CONFIGURED,
                    "✓ Credential already configured",
                )

        if self._operation is SetupOperation.VALIDATE:
            location = self._credential_locations.get(provider_id, provider_id)
            detail = "Credential is not provisioned"
            self._output.write_line(f"  ✗ {detail}")
            self._output.write_line("  Expected externally managed credential:")
            self._output.write_line(f"    {location}")
            return ProviderSetupOutcome(
                provider_id=provider_id,
                auth_kind=kind,
                status=SetupOutcomeStatus.MISSING,
                detail=f"{detail}: {location}",
            )

        # Prompt for the secret using hidden input. The value is used only to
        # store it, and is never echoed, logged, or returned.
        secret = self._prompt.read_secret("  API Key: ")
        if not secret or not secret.strip():
            return self._report(
                provider,
                kind,
                SetupOutcomeStatus.MISSING,
                "✗ No API key entered; credential not stored",
            )

        # Keep the caller frame clean if a setup-plane target fails while
        # persisting the credential. Runtime-backed CredentialStore already
        # applies the same discipline at its delegation boundary.
        try:
            self._store.set(provider_id, secret)
        finally:
            del secret
        return self._report(
            provider,
            kind,
            SetupOutcomeStatus.STORED,
            "✓ Credential stored securely",
        )

    def _configure_aws_provider(
        self, provider: ProviderRecord, kind: ProviderAuthKind
    ) -> ProviderSetupOutcome:
        """Detect AWS credentials via the SDK chain; never store anything."""
        if self._aws_detector.is_available():
            return self._report(
                provider,
                kind,
                SetupOutcomeStatus.AWS_DETECTED,
                "✓ AWS credentials detected",
            )
        return self._report(
            provider,
            kind,
            SetupOutcomeStatus.AWS_UNAVAILABLE,
            "✗ AWS credentials not found; configure the AWS credential chain "
            "(environment, shared config, or IAM role)",
        )

    # ------------------------------------------------------------------
    # Internal — helpers
    # ------------------------------------------------------------------

    def _report(
        self,
        provider: ProviderRecord,
        kind: ProviderAuthKind,
        status: SetupOutcomeStatus,
        detail: str,
    ) -> ProviderSetupOutcome:
        """Emit the outcome line and build the outcome record."""
        self._output.write_line(f"  {detail}")
        return ProviderSetupOutcome(
            provider_id=provider.provider_id,
            auth_kind=kind,
            status=status,
            detail=detail,
        )


__all__ = [
    "CredentialSetupService",
]
