"""Outcome types for the credential setup workflow.

These types record *what happened* for each provider during setup. They are
deliberately secret-free: a :class:`ProviderSetupOutcome` carries a status and a
human-readable, non-secret detail string only — never the credential value. This
is a structural guarantee (there is no field a secret could live in), not a
convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from app.intelligence.registry.models.provider import (
    AUTH_TYPE_DEFAULT_SENTINEL,
    AuthConfig,
    AuthType,
)


class ProviderAuthKind(str, Enum):
    """How a provider authenticates, as far as setup is concerned.

    Derived from ``auth.type`` — setup behaviour is keyed off this, never off a
    hard-coded provider id.
    """

    API_KEY = "api_key"  # Requires an API key stored in the CredentialStore.
    AWS = "aws"  # Uses the AWS SDK credential chain; nothing is stored.
    NONE = "none"  # No credential required.


class SetupOperation(str, Enum):
    """Whether setup may configure credentials or only validate them."""

    CONFIGURE = "configure"
    VALIDATE = "validate"


class SetupOutcomeStatus(str, Enum):
    """The result of attempting to configure one provider."""

    NO_CREDENTIAL_REQUIRED = "no_credential_required"  # auth.type none/absent.
    ALREADY_CONFIGURED = "already_configured"  # api_key already in the store.
    STORED = "stored"  # api_key was prompted for and stored this run.
    AWS_DETECTED = "aws_detected"  # AWS credential chain resolved.
    AWS_UNAVAILABLE = "aws_unavailable"  # AWS credential chain did not resolve.
    MISSING = "missing"  # api_key required but none was provided.
    SKIPPED_DISABLED = "skipped_disabled"  # provider is disabled in llm.yaml.


# Statuses that represent a provider setup did not fully satisfy. The command's
# overall success is the absence of any of these.
_FAILURE_STATUSES = frozenset(
    {SetupOutcomeStatus.MISSING, SetupOutcomeStatus.AWS_UNAVAILABLE}
)


@dataclass(frozen=True, slots=True)
class ProviderSetupOutcome:
    """The result of configuring a single provider.

    Attributes:
        provider_id: The provider this outcome is about.
        auth_kind: The authentication kind derived from ``auth.type``.
        status: What happened for this provider.
        detail: A human-readable, NON-SECRET description of the outcome.
    """

    provider_id: str
    auth_kind: ProviderAuthKind
    status: SetupOutcomeStatus
    detail: str

    @property
    def is_success(self) -> bool:
        """True unless this outcome represents an unmet credential requirement."""
        return self.status not in _FAILURE_STATUSES


@dataclass(frozen=True, slots=True)
class SetupReport:
    """The aggregate result of a setup run across all configured providers."""

    outcomes: Tuple[ProviderSetupOutcome, ...] = ()

    @property
    def ok(self) -> bool:
        """True when every provider outcome is a success."""
        return all(outcome.is_success for outcome in self.outcomes)


def classify_auth(auth: AuthConfig) -> ProviderAuthKind:
    """Map an :class:`AuthConfig` to a :class:`ProviderAuthKind`.

    ``auth.type`` may be an :class:`AuthType` value or the
    ``AUTH_TYPE_DEFAULT_SENTINEL`` (when the field was absent from llm.yaml).
    An absent auth.type is treated as "no credential required", matching the
    provider runtime, which resolves a stored credential only for API_KEY.
    """
    auth_type = auth.type
    if auth_type is AuthType.API_KEY:
        return ProviderAuthKind.API_KEY
    if auth_type is AuthType.AWS:
        return ProviderAuthKind.AWS
    # AuthType.NONE or the "absent" sentinel both mean: nothing to configure.
    if auth_type is AuthType.NONE or auth_type is AUTH_TYPE_DEFAULT_SENTINEL:
        return ProviderAuthKind.NONE
    # Defensive: any unexpected value is treated as "no credential required"
    # rather than silently prompting for a key that will not be used.
    return ProviderAuthKind.NONE


def auth_kind_label(kind: ProviderAuthKind) -> str:
    """Return the human-readable authentication label for display."""
    if kind is ProviderAuthKind.API_KEY:
        return "API Key"
    if kind is ProviderAuthKind.AWS:
        return "AWS"
    return "None"


__all__ = [
    "ProviderAuthKind",
    "ProviderSetupOutcome",
    "SetupOperation",
    "SetupOutcomeStatus",
    "SetupReport",
    "auth_kind_label",
    "classify_auth",
]
