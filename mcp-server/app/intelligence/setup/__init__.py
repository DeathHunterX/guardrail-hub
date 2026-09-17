"""Credential setup primitives for configured-provider operations.

The public CLI uses provider-scoped dashboard, credential, and connection-test
flows. These primitives derive requirements from ``auth.type`` (never a
hard-coded provider ID), never alter ``llm.yaml``, create a ``.env`` file, or
expose credential values. Read-only backends remain read-only.

Public API:

    CredentialSetupService  — orchestrates the workflow over provider records
    SetupReport             — aggregate result of a run
    ProviderSetupOutcome    — per-provider result (secret-free by construction)
    SetupOperation          — legacy service operation retained for direct callers
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
    SetupOperation,
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
    "SetupOperation",
    "SetupOutcomeStatus",
    "SetupReport",
    "auth_kind_label",
    "classify_auth",
]
