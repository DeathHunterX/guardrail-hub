# Phase 5A — Final Audit & Architecture Refinement (Container Credential Delivery)

**Status:** FINAL — ratification-ready
**Role:** Senior Backend Architect + Security Reviewer
**Scope:** Audit and design only. No application source, deployment configuration, tests, or `llm.yaml` were modified in this phase.
**Supersedes:** `phase-5a-container-credential-architecture-audit.md` where the two differ. The detailed audit remains the long-form evidence record; this report is the authoritative, ratification-facing summary.
**Lane / governance:** AIOS Product Lane, Backend Domain. Guardrails G1 (never expose or commit secrets) and G5 (label inference vs. verified fact) apply throughout.

> **Reading note on evidence labels.** Statements tagged *[verified]* were confirmed by reading the cited file and line. Statements tagged *[inference]* are engineering judgment drawn from that evidence. Per G5 the two are kept distinct.

---

## 1. Executive Verdict

**Phase 5A is READY FOR RATIFICATION.**

The proposed architecture is sound, minimal, and governance-compliant. A single read-only `ContainerFileCredentialBackend` — resolving `provider_id` to a file under a configurable secrets directory (default `/run/secrets/`) — correctly serves Docker, Podman, and orchestrated deployments because all three surface secrets as files at that path *[verified: Docker/Podman/K8s secret semantics; inference: single-backend sufficiency]*. Environment-variable delivery is retained only as an explicit, caveated opt-in. Backend selection is explicit and **fails closed** on an unset or unknown mode under Linux. The credential seam already in the codebase (`CredentialStore` → `CredentialBackend`, keyed by `provider_id`) is preserved unchanged.

All five mandated findings are **resolvable within the design** and have been resolved in this report and the refined detailed audit. None is a blocker. The one HIGH-severity finding — provider-id path safety — is resolved *in design* by a mandatory security invariant (§4) and is carried forward as a hard **precondition** for Phase 5B (§7), not as an obstacle to ratification.

Two governance actions gate implementation: (a) **ADR-0013 must be authored and accepted** before any code is written, because trusting a non-Windows secret source is a security-relevant control change and the existing fail-closed factory explicitly demands a ratified decision *[verified: `backend_factory.py` docstring]*; and (b) the dangling **"Decision 0014"** reference in `llm.yaml` must be corrected during Phase 5E. Neither blocks ratification of the design.

---

## 2. Findings

Severity scale: **BLOCKER** (must fix before ratification) · **HIGH** (must be resolved in design and fixed before the phase it gates) · **MEDIUM** (must be reflected in design/tests) · **LOW** (should address) · **INFORMATIONAL** (context).

No finding is a BLOCKER. Ratification may proceed.

### Finding 1 — Provider ID → secret-filename path safety
- **Severity:** HIGH (resolved in design; precondition for Phase 5B)
- **Evidence:** `provider_id` is used as the secret filename, but nothing upstream constrains its character set. The loader accepts any non-empty string — `app/intelligence/registry/loaders/llm_config_loader.py:322-324` (`provider_id = data.get("id") or data.get("provider_id")`; rejects only falsy / non-`str`) *[verified]*. The registry validator checks uniqueness, `auth.type` validity, `api_key_env` presence, priority, `base_url`, and referential integrity — but **no** charset or path validation *[verified: `registry_validator.py`]*. `ProviderRecord.provider_id` is a plain `str` with no `__post_init__` guard — `app/intelligence/registry/models/provider.py:116` *[verified]*.
- **Assessment:** A `provider_id` such as `../../etc/shadow`, `/etc/passwd`, or one containing `/` or `\` would, without a guard, cause the backend to read outside the intended secrets directory. This is a real path-traversal exposure, not a hypothetical one, precisely because no layer sanitizes the value today. It must be treated as untrusted input at the backend boundary (defense-in-depth), independent of any expectation that the YAML loader "should" sanitize it.
- **Required action:** Adopt the path-safety invariant in §4 (INV-1). The backend MUST reject empty identifiers, any `/` or `\`, any `..` segment, absolute paths, and any resolved path that escapes `secrets_dir`; it MUST verify the resolved target is within `secrets_dir` after resolution. Encode these as mandatory Phase 5B tests. Do **not** globally redesign `ProviderRecord.provider_id`; repository evidence does not require it *[inference]*.

### Finding 2 — Do not overclaim file-mounted secret security
- **Severity:** MEDIUM (resolved in design)
- **Evidence:** The prior audit described file-mounted delivery as having the "lowest" exposure risk. Refined to "**Preferred — reduced process-environment exposure** *(inference; not an absolute guarantee)*" in the detailed audit §3/§11 *[verified: edit applied]*.
- **Assessment:** File-mount delivery genuinely reduces one specific attack surface — the process environment (`/proc/<pid>/environ`, `docker/podman inspect`, inheritance by spawned subprocesses). It does **not** by itself guarantee secrecy: host/container security, file permissions, privileged containers, bind mounts, container escape, node compromise, and debugger/`exec` access all remain **deployment-level** concerns this mechanism does not solve.
- **Required action:** Frame the claim precisely as "preferred credential-delivery mechanism with reduced process-environment exposure," never as an absolute security guarantee. Already reflected in the design wording; carry the same framing into ADR-0013 and Phase 5E docs.

### Finding 3 — Permission policy: split hard requirements from advisory checks
- **Severity:** MEDIUM (resolved in design)
- **Evidence:** The prior audit implied a fixed mode (e.g. `0400`). Refined to a hard/advisory split in the detailed audit §11 *[verified: edit applied]*.
- **Assessment:** A rigid `0400`/root-owned requirement breaks legitimate targets — rootless Podman, Kubernetes projected volumes, and non-root container users all produce valid secret files with varying ownership and modes. Readability by the *current process* is the property that matters.
- **Required action:** **Hard** requirements: resolved path within `secrets_dir`; target exists; is a regular file; readable by the current process; enforced size cap; fail-closed on any violation; no secret value in exceptions, logs, or `repr`. **Advisory/audit** signals (never hard failures): world-readable bits, unusual permission bits, unexpected ownership. No hard-coded root ownership or fixed UID/mode. Compatible with rootful Docker, rootless Podman, and K8s/projected volumes.

### Finding 4 — `api_key_env` semantics under the file backend
- **Severity:** MEDIUM (resolved in design)
- **Evidence:** `AuthConfig.api_key_env` is the *name* of an environment variable, never the value — `app/intelligence/registry/models/provider.py:72-76` *[verified]*. The file backend derives its filename purely from `provider_id`; detailed audit §8 now states it "**never reads `api_key_env`**" *[verified: edit applied]*.
- **Assessment:** The two delivery mechanisms use `api_key_env` differently, and this must be unambiguous to avoid a false sense that setting `api_key_env` influences the file backend.
- **Required action:** Ratify the four-case rule (§5, Decision E). In short: the **file backend never reads `api_key_env`** (filename = `provider_id`); the optional **env backend** uses `api_key_env` as an explicit env-var name when present, and falls back to a derived name (e.g. `GUARDRAILHUB_CREDENTIAL__<PROVIDER_ID>`) when absent; when the env backend is disabled / the file backend is active, `api_key_env` is inert configuration metadata that is still validated but not consulted.

### Finding 5 — Bootstrap wiring defect (`ProviderManager` built without `CredentialStore`)
- **Severity:** HIGH (existing runtime defect; not a Phase 5A blocker; repaired in Phase 5D)
- **Evidence:** `app/bootstrap.py:630` calls `ProviderManager(catalog)` — a stale single-positional call *[verified]*. The current signature is `ProviderManager(factory, catalog, credential_store: Optional[CredentialStore] = None)` — `app/intelligence/providers/provider_manager.py:51-55` *[verified]*. The resolution path itself is implemented and correct: `_resolve_and_attach_credential` (line 276) returns early for non-`API_KEY` auth (line 304), raises `LLMConfigurationError` when the store is `None` (line 310), fetches by `provider_id` (line 317: `self._credential_store.get(record.provider_id)`), and attaches a masked `ProviderCredential` (line 329) *[verified]*.
- **Assessment:** Because bootstrap passes no store (and mis-binds `catalog` into the `factory` slot), runtime credential resolution is **unreachable in production today — even on Windows**. This is a pre-existing runtime wiring defect, **not** a flaw in the credential architecture. Container support cannot be validated end-to-end until it is fixed.
- **Required action:** Classify as an existing runtime wiring defect. Repair it during **Phase 5D (Deployment Integration)** by constructing the store via the factory and injecting it. The repair MUST NOT change `_resolve_and_attach_credential()` semantics. Do not implement now.

### Finding 6 — Dangling "Decision 0014" reference and stale comment in `llm.yaml`
- **Severity:** LOW (documentation rot; fix in Phase 5E)
- **Evidence:** `config/llm.yaml:58` cites "Reference: Decision 0014, architectural review 2025", but `.ai/decisions/` stops at `0012-runtime-boundary.md` (Status: Proposed) — no 0013 or 0014 exists *[verified]*. `config/llm.yaml:54` comment ("set the variable named in `auth.api_key_env` before starting the app") misdescribes the intended runtime flow (resolve by `provider_id` via `CredentialStore`) *[verified]*.
- **Assessment:** Harmless at runtime but misleading; the ratified decision will in fact be **0013**.
- **Required action:** In Phase 5E, correct the comment to describe the CredentialStore-based flow and repoint the reference to the real ADR-0013. No code behavior changes.

### Finding 7 — Secret masking already correct across surfaces
- **Severity:** INFORMATIONAL (no action; must be preserved)
- **Evidence:** `ProviderCredential` is `@dataclass(frozen=True, slots=True, repr=False)` with `_MASK = "********"`, `__repr__` → `ProviderCredential(api_key=********)`, and `__str__ = __repr__` — `app/intelligence/providers/credential.py` *[verified]*. `CredentialStore.__repr__` is masked (`base.py:192`); `CredentialNotFoundError` and `CredentialBackendError` name only the `provider_id`, never the secret — `base.py` *[verified]*.
- **Assessment:** The masking contract (INV-6, §4) is satisfied today and must remain intact through Phases 5B–5E.
- **Required action:** None now; add regression tests in 5B/5D asserting no secret appears in `repr`/`str`/exceptions/logs.

### Finding 8 — AWS/Bedrock is out of scope and already correct
- **Severity:** INFORMATIONAL (no action)
- **Evidence:** The Bedrock adapter uses boto3 and the standard AWS SDK credential chain (env keys → shared config → IAM role → SSO); region from `AWS_REGION`/`AWS_DEFAULT_REGION`; it never draws from `CredentialStore` — `app/intelligence/providers/adapters/bedrock.py` *[verified]*.
- **Assessment:** `auth.type: aws` correctly bypasses this architecture and must stay untouched.
- **Required action:** None. Explicitly out of scope for all of Phase 5.

---

## 3. Final Architecture

The design cleanly separates four layers. Configuration declares *how* a provider authenticates and never holds a secret; the credential *source* is deployment-specific and lives entirely behind the backend; the credential *store* is the stable in-process seam; and the provider *runtime* receives only a masked credential object.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ CONFIGURATION  (committed; never contains a secret value)                  │
│   config/llm.yaml → ProviderRecord{ provider_id, auth.type, api_key_env }  │
│   • auth.type = api_key | aws | none                                        │
│   • api_key_env = NAME of an env var (never a value)                        │
└───────────────┬───────────────────────────────────────────────────────────┘
                │ provider_id  (identity key — NEVER model_id)
                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ CREDENTIAL SOURCE  (deployment-specific; selected explicitly, fail-closed) │
│                                                                            │
│   GUARDRAILHUB_CREDENTIAL_BACKEND = windows | file | env                   │
│   (unset / unknown on Linux ─────────────────────────► FAIL CLOSED)        │
│                                                                            │
│   ├─ windows → WindowsCredentialManagerBackend      (local dev, unchanged) │
│   ├─ file    → ContainerFileCredentialBackend       (Docker/Podman/orch.)  │
│   │              reads  <secrets_dir>/<provider_id>                         │
│   │              (GUARDRAILHUB_SECRETS_DIR, default /run/secrets/)          │
│   │              READ-ONLY: get() ok; set()/delete() → CredentialBackendError │
│   │              path-safety guard on provider_id (INV-1)                  │
│   └─ env     → EnvVarCredentialBackend (opt-in only; honours api_key_env)  │
│                                                                            │
│   [AWS/Bedrock does NOT pass here — uses the AWS SDK credential chain]      │
└───────────────┬───────────────────────────────────────────────────────────┘
                │ get(provider_id) → str        (raw secret, in-process only)
                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ CREDENTIAL STORE  (stable seam; masked repr; deployment-agnostic)          │
│   CredentialStore → CredentialBackend.get/set/delete(provider_id)          │
│   • Router / LLMService / ModelCatalog / adapters never see this layer     │
└───────────────┬───────────────────────────────────────────────────────────┘
                │ ProviderCredential(api_key=…)  (masked in repr/str/logs)
                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ PROVIDER RUNTIME                                                           │
│   ProviderManager._resolve_and_attach_credential(record):                  │
│     if auth.type != API_KEY: return                                        │
│     if credential_store is None: raise LLMConfigurationError                │
│     api_key = credential_store.get(record.provider_id)                     │
│     adapter.attach_credential(ProviderCredential(api_key))                 │
│   • Multiple ModelRecords sharing a provider_id share ONE credential       │
└────────────────────────────────────────────────────────────────────────────┘
```

Key properties: one backend class serves all container/orchestrated targets (they differ only by `secrets_dir`, a string); the seam and the resolution logic already exist and are unchanged; deployment knowledge is confined to the backend + factory and never leaks into Router, LLMService, ModelCatalog, or adapters.

---

## 4. Security Invariants

These are binding on all implementation phases. Each is testable.

- **INV-1 — Provider-id path safety (defense-in-depth).** `provider_id`, when used to derive a secret filename, MUST be treated as a single, path-safe filename component. The backend MUST reject: empty/whitespace-only identifiers; any `/` or `\`; any `..` path segment; absolute paths; and any value whose resolved path escapes `secrets_dir`. After resolution, the target MUST be confirmed to reside within `secrets_dir`. This guard is mandatory **regardless** of upstream validation, because none exists today (`llm_config_loader.py:322-324` checks only non-empty `str`). Violations fail closed with an error that names the `provider_id` but never any file contents.
- **INV-2 — Fail-closed backend selection.** Backend selection is explicit via `GUARDRAILHUB_CREDENTIAL_BACKEND` (`windows|file|env`). An unset or unrecognized mode under Linux MUST raise and refuse to start — no silent default, no auto-detection, no clear-text fallback. This preserves the intent of the current `build_default_credential_backend`, which already raises rather than inventing a backend *[verified: `backend_factory.py`]*.
- **INV-3 — Read-only container backend.** `ContainerFileCredentialBackend.get(provider_id)` is supported; `set()` and `delete()` MUST raise `CredentialBackendError`. No bulk, model-level, or write APIs. The `CredentialBackend` contract shape (`get/set/delete(provider_id)`) is otherwise unchanged.
- **INV-4 — Provider identity is `provider_id`, never `model_id`.** Credentials are keyed by `provider_id`; multiple `ModelRecord`s that reference the same provider share one credential — `model.py:29` (`provider_id: str`, "Reference to the provider that hosts this model") *[verified]*.
- **INV-5 — Bounded, regular-file reads.** The backend reads only a regular file within `secrets_dir`, enforces a size cap, and verifies readability by the current process. It does NOT require a fixed mode/UID/ownership. Over-broad permissions are an advisory audit signal, not a hard failure (see Finding 3).
- **INV-6 — No secret exposure across any surface.** The secret value MUST NOT appear in `repr`/`str`, exceptions, logs, CLI output, subprocess environment/argv, or test output. The existing masking (`ProviderCredential` `repr=False` + `_MASK`; masked `CredentialStore.__repr__`; provider-id-only error messages) MUST be preserved *[verified: `credential.py`, `base.py`]*.
- **INV-7 — Configuration never carries secrets.** `llm.yaml`, `ProviderRecord`, `ModelRecord`, `ModelCatalog`, `Router`, and `ChatOptions` MUST NOT contain any secret value. `api_key_env` remains a variable *name* only. The loader already rejects a literal `auth.api_key` *[verified: `llm_config_loader.py`]*.
- **INV-8 — `api_key_env` binding.** The file backend never reads `api_key_env`; only the opt-in env backend may consult it (see §5 Decision E). This prevents a false belief that `api_key_env` affects file-mounted delivery.
- **INV-9 — Deployment knowledge stays behind the seam.** All Docker/Podman/orchestration specifics live in the backend + factory. Adapters MUST NOT read credentials directly from the environment or filesystem.
- **INV-10 — Rotation requires restart.** Phase 5 provides no hot rotation; a rotated secret takes effect on process restart. This is a documented limitation, not a defect.

---

## 5. Final Decisions (what ADR-0013 must ratify)

ADR-0013 ("Container & Orchestrated Credential Delivery") must record and accept the following. It is required because trusting a non-Windows secret source is a security-relevant control change (decision-policy line 103: "Security and correctness outrank the ladder … input validation"), and the current fail-closed factory's own docstring demands "an explicit, ratified decision (ADR)" before secrets are sourced anywhere new *[verified]*.

- **Decision A — Secret-source trust.** The application will trust files mounted under a configured `secrets_dir` (default `/run/secrets/`) as an authoritative credential source on Linux/container deployments, framed as reduced process-environment exposure (not an absolute guarantee; Finding 2).
- **Decision B — One backend, not four.** Exactly one `ContainerFileCredentialBackend` serves Docker, Podman, and orchestrated deployments, parameterized by `secrets_dir`. Separate per-platform backend classes are rejected as **speculative L4** (they would differ only by a directory string; decision-policy line 130) *[verified]*.
- **Decision C — Generic mount contract; no orchestrator SDKs.** Orchestration integration is a generic file-mount contract. No `kubernetes`, `hvac`, or Vault SDK is introduced. Runtime secret-manager pulls (Vault/CSI) are explicitly deferred to a possible future backend behind the same seam.
- **Decision D — Explicit, fail-closed selection.** `GUARDRAILHUB_CREDENTIAL_BACKEND` (`windows|file|env`) + `GUARDRAILHUB_SECRETS_DIR` govern selection; unset/unknown on Linux fails closed (INV-2). No auto-detection.
- **Decision E — `api_key_env` four-case rule (INV-8).** (1) File backend active + `api_key_env` present → `api_key_env` ignored; filename = `provider_id`. (2) File backend active + `api_key_env` absent → no effect; filename = `provider_id`. (3) Env backend active + `api_key_env` present → read that named env var. (4) Env backend active + `api_key_env` absent → read a derived name (e.g. `GUARDRAILHUB_CREDENTIAL__<PROVIDER_ID>`). When the env backend is disabled, `api_key_env` is inert-but-validated config metadata.
- **Decision F — Env delivery is opt-in only.** Environment variables are never the default on Linux and carry a documented caveat. Adapters never read credentials from the environment directly (INV-9).
- **Decision G — Provider-id path-safety invariant (INV-1)** is a ratified security requirement, not an implementation detail.
- **Decision H — `setup` scope.** `guardrail-hub setup` remains the local (Windows) credential-provisioning UX and is explicitly **not** the container mechanism. A non-interactive `setup --check` preflight is optional and belongs to Phase 5E; it is outside the backend architecture itself.
- **Decision I — Bootstrap defect ownership.** The `bootstrap.py:630` wiring defect (Finding 5) is acknowledged as a pre-existing runtime defect to be repaired in Phase 5D without altering `_resolve_and_attach_credential()` semantics.

**Governance classification.** Introducing a new backend *class* that follows the established `CredentialBackend` pattern is **L2 Extend** (unilateral). However, the *selection-policy* change — teaching the application to trust a new secret source — is security-relevant and therefore triggers **D2 escalation** and the ADR requirement above. The backend is **not** a runtime boundary: it fails all four runtime-boundary scope tests (it has no own image/build, no own process lifecycle, no own external interface, no independent local execution) and is imported in-process — "if the server imports it, it belongs in a backend role" (runtime-boundary line 60) *[verified]*. It therefore lives in `app/intelligence/credentials/`, consistent with existing placement. No existing ratified decision (0001–0012) concerns credentials, LLM auth, or secrets, so there is **no decision conflict**; 0013 is the next free number *[verified]*.

---

## 6. Phase 5 Boundary

Ratification is a **gate**, not a phase. Each implementation phase is independently testable and gated by an audit + ratify step; no phase begins before its predecessor is ratified.

```
5A  Audit / Design (this report + detailed audit)
      └─► RATIFY GATE: author & accept ADR-0013  (no code)
5B  Container Credential Backend Foundation (Docker + Podman)
      • ContainerFileCredentialBackend (read-only, path-safe per INV-1)
      • unit + security tests; nothing else imports it yet
      └─► TEST → AUDIT → RATIFY
5C  Orchestrated Credential Integration (Generic Secret Mount Contract)
      • same backend via configurable secrets_dir; NO orchestrator SDK
      └─► TEST → AUDIT → RATIFY
5D  Deployment Integration (Backend Selection + Startup/Runtime Wiring)
      • deployment-aware factory (windows|file|env, fail-closed)
      • optional EnvVarCredentialBackend (opt-in; honours api_key_env)
      • repair bootstrap.py:630 wiring (inject CredentialStore) — no change
        to _resolve_and_attach_credential() semantics
      └─► TEST → AUDIT → RATIFY
5E  Documentation / Deployment UX
      • compose/Dockerfile/(optional) K8s secret wiring docs
      • fix llm.yaml comment + dangling "Decision 0014" → 0013
      • add secrets/ to .gitignore/.dockerignore
      • optional guardrail-hub setup --check preflight
      └─► FINAL AUDIT → RATIFY → COMMIT → PHASE 5 CLOSED
```

Boundary rules: backend implementation is Phase **5B**, not 5C — do not turn backend implementation into Phase 5C. The env backend belongs to 5D (it is part of backend *selection*), not to a separate phase. The bootstrap repair belongs to 5D (Deployment Integration), not to the backend foundation. Do not create implementation-file-oriented subphases between these boundaries.

---

## 7. Implementation Preconditions (before Phase 5B)

All of the following MUST hold before a single line of Phase 5B code is written:

1. **ADR-0013 is accepted**, recording Decisions A–I (§5). The fail-closed factory's own docstring makes this a hard gate *[verified]*.
2. **INV-1 (provider-id path safety) is written into the Phase 5B test plan** as mandatory cases: reject `..`, `/`, `\`, absolute paths, empty/whitespace ids, and any resolved path escaping `secrets_dir`; confirm containment after resolution.
3. **The read-only contract (INV-3) is specified as tests**: `get()` succeeds on a present, readable, regular file within `secrets_dir`; `set()`/`delete()` raise `CredentialBackendError`.
4. **The masking regression (INV-6) is specified as tests**: no secret in `repr`/`str`/exceptions/logs for the new backend.
5. **Fail-closed selection (INV-2) is specified** for Phase 5D but its expected behavior is agreed now: unset/unknown mode on Linux refuses to start.
6. **Test runner confirmed:** Phase 5B tests run via `PYTHONPATH=. python3 -m unittest` (this repo does not use pytest).
7. **No scope creep:** the `bootstrap.py:630` fix is explicitly deferred to 5D; AWS/Bedrock remains untouched; `llm.yaml` edits are deferred to 5E.

---

## 8. Final Recommendation

**Ratify Phase 5A and proceed to author ADR-0013.** Adopt a single read-only, file-based `ContainerFileCredentialBackend` that resolves `provider_id` to `<secrets_dir>/<provider_id>` (default `/run/secrets/`), selected by an explicit, deployment-mode-aware factory that fails closed on an unset/unknown mode under Linux, and shared unchanged by Docker, Podman, and orchestrated deployments. Enforce the provider-id path-safety invariant (INV-1) at the backend as defense-in-depth, since no upstream layer constrains the identifier today. Keep environment-variable delivery as an explicit, caveated opt-in that honours `api_key_env`, and keep `llm.yaml` strictly configuration. Do not build per-platform backend classes (speculative L4). Ratify these decisions as **ADR-0013** before writing code, then — during Phase 5D — repair the pre-existing `bootstrap.py:630` wiring so a `CredentialStore` is injected into `ProviderManager`, without which container credential support cannot be validated end-to-end. **No implementation is authorized by this report; stop after ratification of the design and await explicit direction to begin Phase 5B.**

---

*End of Phase 5A Final Audit. No application source, tests, deployment configuration, or `llm.yaml` were modified. Do not begin Phase 5B until ADR-0013 is ratified.*
