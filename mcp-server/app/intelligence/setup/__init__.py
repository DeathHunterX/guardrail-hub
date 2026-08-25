"""Credential setup workflow for the ``guardrail-hub setup`` command.

This capability package bootstraps local LLM credentials from the providers
declared in ``config/llm.yaml``. It derives each provider's requirement from
``auth.type`` (never from a hard-coded provider id), prompts only for missing
api_key credentials, and stores them in the CredentialStore. It never writes
llm.yaml, never creates a .env file, and never prints, logs, or raises secrets.

Public API:

    CredentialSetupService  — orchestrates the workflow over provider records
    SetupReport             — aggregate result of a run
    ProviderSetupOutcome    — per-provider result (secret-free by construction)
    SetupOutcomeStatus      — enum of per-provider outcomes
    ProviderAuthKind        — auth kind derived from auth.type
    classify_auth           — AuthConfig -> ProviderAuthKind
    auth_kind_label         — ProviderAuthKind -> display label

Ports (:mod:`.ports`) and concrete adapters (:mod:`.adapters`) are imported
from their submodules by composition roots and tests; they are intentionally
not re-exported here, matching the minimal-façade convention of sibling
capability packages.
"""

from app.intelligence.setup.plan import (
    ProviderAuthKind,
    ProviderSetupOutcome,
    SetupOutcomeStatus,
    SetupReport,
    auth_kind_label,
    classify_auth,
)
from app.intelligence.setup.service import CredentialSetupService

__all__ = [
    "CredentialSetupService",
    "ProviderAuthKind",
    "ProviderSetupOutcome",
    "SetupOutcomeStatus",
    "SetupReport",
    "auth_kind_label",
    "classify_auth",
]
