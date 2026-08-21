# 0017 — Container & Orchestrated Credential Delivery

Status: **Accepted** — ratified 2026-08-22 by the backend owner (Loi Phan). Acceptance authorizes Phase 5B (§8) to begin; not yet implemented, and no later phase is authorized by this record.
Owner: Loi Phan
Date: 2026-08-21
Relates to: [Decision 0009](0009-execution-capability.md) (the same refusal to abstract over a set of one — here, one backend serves Docker, Podman and orchestrated deployments); [Decision 0012](0012-runtime-boundary.md) (its four-condition Scope test is what classifies this backend as application code, **not** a runtime boundary); [Decision 0007](0007-domain-layer-justification.md) (the present-tense-evidence standard this ADR is held to).
Numbering: assigned **0017**, not 0013, because 0013–0016 are reserved for the planned intelligence-layer ADR sequence (see [architecture/intelligence-layer.md](../architecture/intelligence-layer.md) §7: 0013 Intelligence Layer Architecture, 0014 Provider & Routing, 0015 Inference Runtime, 0016 Inference Policy). Taking 0013 would have collided with that reservation in an append-only log.

---

## 1. Context

Guardrail Hub already has an in-process credential seam: a `CredentialStore` delegating to a `CredentialBackend` with a synchronous `get/set/delete(provider_id)` contract (`mcp-server/app/intelligence/credentials/base.py`). Runtime resolution is implemented — `ProviderManager._resolve_and_attach_credential()` fetches by `provider_id` and attaches a masked `ProviderCredential` (`mcp-server/app/intelligence/providers/provider_manager.py`) — and the secret value is masked in `repr`/`str` and never named in exceptions (`mcp-server/app/intelligence/providers/credential.py`, `base.py`).

Today only one backend exists. The factory `build_default_credential_backend()` returns the Windows Credential Manager backend on `win32` and otherwise **raises** — a deliberate fail-closed posture whose own docstring states that a security product "must not persist secrets in the clear without an explicit, ratified decision (ADR)" (`mcp-server/app/intelligence/credentials/backend_factory.py`). There is therefore no supported way to run the server under Linux containers, which is the primary deployment target.

Environment variables are not a safe default credential store: their values are visible via `/proc/<pid>/environ`, surfaced by `docker inspect` / `podman inspect`, and inherited by every child process — and this application spawns scanner/JMeter subprocesses, widening that exposure. Docker secrets, Podman secrets, and Kubernetes secret volumes all instead surface a secret as a **file**, conventionally under `/run/secrets/<name>`. That single shared shape is the portability insight behind this decision.

The full evidence base is the Phase 5A audit: `mcp-server/docs/phase-5a-final-audit-and-refinement.md` (ratification-facing) and `mcp-server/docs/phase-5a-container-credential-architecture-audit.md` (long-form). This ADR records the decisions and constraints; it does not reproduce that evidence.

## 2. Problem

How should an API-key credential reach a provider adapter when Guardrail Hub runs in a Docker, Podman, or generic orchestrated (file-mounted) deployment, without weakening the existing fail-closed security posture, without leaking secrets into configuration or the process environment, and without introducing orchestrator-specific SDKs? The credential seam and its `provider_id`-keyed contract must remain unchanged; only *how the secret is sourced* is in question.

## 3. Alternatives considered

- **(a) Environment variables as the default Linux mechanism.** Rejected as a *default*. Env delivery has a materially larger exposure surface (process environment, inspect output, subprocess inheritance). It is retained only as an explicit, caveated opt-in (Decision F).
- **(b) Separate `Docker`, `Podman`, `Kubernetes`, and `Orchestrated` backend classes.** Rejected. All four would resolve `provider_id` to a file under a directory and differ *only by that directory string*. This is the "abstraction over a set of one (repeated four times)" that [Decision 0009](0009-execution-capability.md) refused and that [decision-policy](../standards/core/decision-policy.md) names a **Speculative L4** anti-pattern. One backend with a configurable secrets directory covers all three targets (Decision B).
- **(c) Runtime secret-manager integration (Kubernetes SDK, HashiCorp Vault, CSI driver APIs).** Rejected for Phase 5. It introduces heavy vendor dependencies to solve a problem the generic file-mount already solves, since CSI and Vault Agent both project secrets onto the filesystem. Left as a possible future backend behind the same seam (Decision C, §7).
- **(d) Automatic backend detection by probing the environment.** Rejected. Silent auto-selection of where to trust secrets from is exactly the security-relevant behaviour that must be explicit and fail-closed (Decision D).
- **(e) Do nothing / keep Windows-only.** Rejected: it leaves the primary deployment target unsupported.

## 4. Decision

**Decision A — Secret-source trust.** Guardrail Hub may trust secret **files** mounted under a configured secrets directory on Linux/container deployments, default `/run/secrets/`. This is framed as the **preferred credential-delivery mechanism, with reduced process-environment exposure** relative to environment variables — *not* an absolute security guarantee. Deployment-level risks remain and are out of this mechanism's control: privileged-container access, host compromise, container escape, filesystem/debugger/`exec` access, and incorrect deployment permissions. The mechanism reduces one specific surface (the process environment); it does not by itself make a secret secure.

**Decision B — One container backend.** Ratify exactly one class, `ContainerFileCredentialBackend`, serving Docker, Podman, and generic orchestrated deployments. Its only deployment-specific parameter is the secrets directory. Do **not** create `DockerCredentialBackend`, `PodmanCredentialBackend`, `KubernetesCredentialBackend`, or `OrchestratedCredentialBackend`; separate per-platform classes would duplicate identical behaviour distinguished only by a path (see §3(b)).

**Decision C — Generic mount contract.** The application contract is `provider_id → <secrets_dir>/<provider_id>`. No orchestrator SDK or API integration is introduced: explicitly excluded are the Kubernetes SDK, HashiCorp Vault SDK, Vault runtime pull, CSI-specific application integration, and any orchestrator-specific credential API. Those remain possible *future* backends behind the unchanged credential seam.

**Decision D — Explicit, fail-closed backend selection.** Ratify an explicit selector `GUARDRAILHUB_CREDENTIAL_BACKEND` with conceptual modes `windows | file | env`, and `GUARDRAILHUB_SECRETS_DIR` (default `/run/secrets/`). Selection is explicit. On Linux, an **unset** mode or an **unknown** mode MUST fail closed — no automatic plaintext fallback, no implicit environment fallback, no auto-detection. This preserves the security intent already present in `backend_factory.py`.

**Decision E — `api_key_env` semantics (four-case rule).** `api_key_env` holds the **NAME** of an environment variable, never a secret value.
1. File backend + `api_key_env` present → `api_key_env` is ignored; filename remains `provider_id`.
2. File backend + `api_key_env` absent → no effect; filename remains `provider_id`.
3. Env backend + `api_key_env` present → read the explicitly named environment variable.
4. Env backend + `api_key_env` absent → read a deterministic derived name, e.g. `GUARDRAILHUB_CREDENTIAL__<PROVIDER_ID>`.
When the env backend is disabled (file backend active), `api_key_env` is inert-but-validated configuration metadata.

**Decision F — Environment variables are opt-in only.** An `EnvVarCredentialBackend` may exist as an explicit fallback; it is **never** the default Linux mechanism, and it carries a documented exposure caveat (process-environment visibility, subprocess inheritance — relevant because the app spawns scanner/JMeter subprocesses). Adapters MUST NOT read credential environment variables directly; all resolution stays behind `CredentialStore → CredentialBackend`.

**Decision G — Provider-id path safety.** `provider_id`, when used to derive a secret filename, MUST be treated as a single path-safe filename component. The future file backend MUST reject: empty identifiers, whitespace-only identifiers, any `/`, any `\`, any `..` segment, absolute paths, and any resolved path that escapes `secrets_dir`; after resolution, the target MUST be confirmed to reside within `secrets_dir`. This is **defense-in-depth at the backend boundary**, because upstream validation does not provide it today — `mcp-server/app/intelligence/registry/loaders/llm_config_loader.py` accepts any non-empty string as `provider_id`, and neither the registry validator nor `ProviderRecord` constrains its character set. This ADR does **not** redesign `ProviderRecord`/provider-id validation.

**Decision H — `setup` scope.** `guardrail-hub setup` remains the **local** credential-provisioning mechanism (e.g. Windows). It is **not** the container secret-provisioning mechanism; container credentials are owned by the deployment platform/operator. A future non-interactive `guardrail-hub setup --check` preflight may be added, but it is deferred to Phase 5E and is not part of this ADR.

**Decision I — Bootstrap defect ownership.** A pre-existing wiring defect exists: `mcp-server/app/bootstrap.py:630` constructs `ProviderManager(catalog)` against the current `(factory, catalog, credential_store=None)` signature, so no `CredentialStore` is injected and runtime credential resolution is unreachable in production. This is a known, pre-existing runtime defect — **not** an architectural redesign and **not** part of this ADR's implementation. It will be repaired in Phase 5D, without altering `_resolve_and_attach_credential()` semantics. This ADR does not modify `bootstrap.py`.

## 5. Security invariants

These are binding on every implementation phase and are each testable.

- **INV-1 — Provider-id path safety.** As Decision G: reject empty/whitespace, `/`, `\`, `..`, absolute paths, and any resolved path escaping `secrets_dir`; confirm containment after resolution. Mandatory regardless of upstream validation.
- **INV-2 — Explicit, fail-closed selection.** Backend selection is explicit; unset/unknown mode on Linux refuses to start. No silent default, no auto-detection, no clear-text fallback.
- **INV-3 — Container file backend is read-only.** `get(provider_id)` is supported; `set()` and `delete()` MUST raise `CredentialBackendError`. No bulk or model-level APIs. The `get/set/delete(provider_id)` contract shape is otherwise unchanged.
- **INV-4 — Credential identity is `provider_id`, never `model_id`.** Multiple models that reference one provider share a single credential (`mcp-server/app/intelligence/registry/models/model.py:29`).
- **INV-5 — Bounded, regular-file reads.** The backend reads only a regular file within `secrets_dir`, enforces a size cap, and verifies **readability by the current process**. It MUST NOT mandate a fixed UID or `0400` mode — rootless Podman and orchestrated/projected secret volumes legitimately vary. Over-broad permissions are an advisory/audit signal, not a universal hard failure.
- **INV-6 — No secret exposure across any surface.** Secrets MUST NOT appear in `repr`, `str`, exceptions, logs, CLI output, subprocess argv, subprocess environment, or test output. The existing masking (`ProviderCredential` `repr=False` + mask; masked `CredentialStore.__repr__`; provider-id-only error messages) MUST be preserved.
- **INV-7 — Configuration never contains secrets.** `config/llm.yaml`, `ProviderRecord`, `ModelRecord`, `ModelCatalog`, `Router`, and `ChatOptions` MUST NOT contain any secret value. `api_key_env` is a variable *name* only.
- **INV-8 — `api_key_env` semantics are explicit and backend-specific.** Per Decision E: the file backend never reads it; only the opt-in env backend does.
- **INV-9 — Deployment knowledge stays behind the seam.** All Docker/Podman/orchestration specifics live in the backend + factory. Adapters MUST NOT read files or environment variables for credentials directly.
- **INV-10 — Rotation requires restart.** Phase 5 provides no hot rotation; a rotated secret takes effect on process restart. Hot rotation is explicitly deferred.

## 6. Consequences

**Gained.** The primary deployment target (Linux containers) becomes supportable without weakening the fail-closed posture. One backend covers Docker, Podman, and orchestrated deployments, so the next target is a configuration value, not a new class. The credential seam, its contract, and its masking are untouched, so blast radius is confined to a new backend plus an explicit selector.

**Accepted.** The word "backend" gains one more concrete implementation to understand. Deployments must now set `GUARDRAILHUB_CREDENTIAL_BACKEND` explicitly on Linux or the server refuses to start — this is intended friction, chosen over a silent insecure default. File-mount delivery reduces process-environment exposure but is not an absolute guarantee (Decision A); the residual deployment-level risks are documented, not solved here.

**Revisit triggers.** A genuine behavioural divergence between orchestrated and plain-container file mounts (would reopen Decision B). A ratified need for runtime secret-manager pull (would add a new backend under Decision C, not modify this one). A requirement for hot rotation (would supersede INV-10).

## 7. Non-goals

This ADR explicitly excludes: any change to AWS/Bedrock authentication (it stays on the AWS SDK credential chain via `mcp-server/app/intelligence/providers/adapters/bedrock.py`, never the `CredentialStore`); VM-specific credential managers; EC2/Azure/GCP instance-metadata credential systems; Kubernetes SDK integration; Vault SDK integration; CSI-specific application integration; runtime secret-manager pulls; application-side encryption-at-rest; any redesign of the `CredentialBackend` contract; Router changes; Model Registry changes; `ModelCatalog` changes; hot secret rotation; the container backend implementation itself; deployment wiring; and CLI implementation. Those last items are sequenced in §8, not authorized here.

## 8. Implementation boundary

Ratification of this ADR is the gate. The approved sequence, each phase gated by test → audit → ratify:

- **Phase 5B — Container Credential Backend Foundation.** Implement `ContainerFileCredentialBackend`: read-only file access, provider-id path safety (INV-1), bounded regular-file reads (INV-5), and security/masking tests (INV-3, INV-6). Nothing else; no other module imports it yet.
- **Phase 5C — Orchestrated Credential Integration.** Prove the generic `secrets_dir` contract for orchestrated/file-mounted deployments. No orchestrator SDK.
- **Phase 5D — Deployment Integration.** Deployment-aware backend factory selection (`windows | file | env`, fail-closed per INV-2); optional `EnvVarCredentialBackend` (opt-in, Decision F); and repair of the `bootstrap.py:630` wiring (Decision I) — without changing `_resolve_and_attach_credential()` semantics.
- **Phase 5E — Documentation / Deployment UX.** Docker/Podman/orchestrator deployment documentation; `config/llm.yaml` comment cleanup and correction of its dangling "Decision 0014" reference (which points at the reserved *Provider & Routing* ADR, not this one); ignore rules for a `secrets/` directory; optional `guardrail-hub setup --check`.

None of these phases is implemented by this ADR.

## 9. Governance / Change-Ladder classification

Per [decision-policy](../standards/core/decision-policy.md): structurally, introducing a new backend that follows the established `CredentialBackend` pattern is **L2 — Extend** (new unit on an existing pattern; Agent-unilateral in the ordinary case). **However**, this decision also changes *which secret sources the application trusts on Linux*, which is a security-relevant control change. Two policy provisions therefore apply: D2 escalation (the level's security relevance forces an escalation, not silent execution) and the Exceptions clause that "**security and correctness outrank the ladder**." The existing `backend_factory.py` fail-closed posture is itself a security control whose own docstring demands "an explicit, ratified decision (ADR)" before secrets are sourced from anywhere new. Accordingly, **an ADR is mandatory before implementation**, notwithstanding the L2 structural classification.

Runtime-boundary classification: this backend is **not** a runtime boundary. Measured against the four-condition Scope test in [runtime-boundary](../standards/architecture/runtime-boundary.md), it has no own container image, no own process lifecycle, no own external interface, and performs no local execution the server cannot do in-process — and it is imported by the server. Per that standard, "if the server imports it, it belongs in a backend role." It therefore lives under `mcp-server/app/intelligence/credentials/`, alongside the existing backend and factory; no new `app/runtime/` component is created.

No existing accepted decision (0001–0012) governs credentials, LLM authentication, or secrets, so there is no decision conflict. This record is consistent with Guardrail [G1](../guardrails/core.md) (never expose or commit secrets), which every invariant in §5 serves.

## 10. References

AIOS units (existing): [decision-policy](../standards/core/decision-policy.md); [runtime-boundary](../standards/architecture/runtime-boundary.md); [Decision 0007](0007-domain-layer-justification.md); [Decision 0009](0009-execution-capability.md); [Decision 0012](0012-runtime-boundary.md); [guardrails/core.md](../guardrails/core.md); [architecture/intelligence-layer.md](../architecture/intelligence-layer.md) (§7, source of the 0013–0016 reservation).

Repository evidence (source; cited as paths, not links): `mcp-server/app/intelligence/credentials/base.py` (CredentialStore/CredentialBackend, masking); `mcp-server/app/intelligence/credentials/backend_factory.py` (fail-closed factory); `mcp-server/app/intelligence/providers/credential.py` (ProviderCredential masking); `mcp-server/app/intelligence/providers/provider_manager.py` (resolution by `provider_id`); `mcp-server/app/intelligence/registry/loaders/llm_config_loader.py` (provider_id accepted as any non-empty string); `mcp-server/app/intelligence/registry/models/provider.py` (ProviderRecord, `AuthConfig.api_key_env`); `mcp-server/app/intelligence/registry/models/model.py` (models reference a provider); `mcp-server/app/bootstrap.py` (line 630 wiring defect); `mcp-server/app/intelligence/providers/adapters/bedrock.py` (AWS SDK chain, out of scope); `mcp-server/config/llm.yaml` (configuration-only).

Phase 5A audit: `mcp-server/docs/phase-5a-final-audit-and-refinement.md`; `mcp-server/docs/phase-5a-container-credential-architecture-audit.md`.

## 11. Ratification / Acceptance

**Acceptance criteria.** This ADR is Accepted when the backend owner ratifies Decisions A–I and invariants INV-1..INV-10 as written, or with recorded amendments. On acceptance, update the Status line to **Accepted** (with date and ratifier, per the convention of ADRs 0010–0012) and change this record's row in [the decisions index](README.md) from *Proposed* to *Accepted*.

**Sequencing.** Acceptance authorizes **Phase 5B only** to begin (§8). Each subsequent phase re-enters its own test → audit → ratify gate.

**Not authorized by this ADR:** implementing `ContainerFileCredentialBackend` or `EnvVarCredentialBackend`; modifying `backend_factory.py`, `bootstrap.py`, `ProviderManager`, adapters, the CLI, `config/llm.yaml`, or any deployment file; adding `setup --check`; introducing any orchestrator/Vault/CSI SDK; changing the `CredentialBackend` contract; or beginning Phase 5B–5E. This is a governance record; it changes no code.
