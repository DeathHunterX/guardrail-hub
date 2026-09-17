# 0017 — Container & Orchestrated Credential Delivery

Status: **Accepted and closed for Phase 5** — ratified 2026-08-22 by the backend owner (Loi Phan). The original acceptance authorized Phase 5B only. **Amendment 1 was ratified 2026-09-09 by the repository owner (Loi Phan)** and supersedes Decision H and the stale Phase 5 sequencing limitations identified in §8 and §11. **Final owner ratification was explicitly recorded 2026-09-13 by the repository owner (Loi Phan), closing Phase 5** at implementation/test HEAD `8161ca8ff8def37ad662378f9c0e062f0b3d2efc`.
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

**Decision H — `setup` scope (historical; superseded by Amendment 1 when ratified).** The original decision was: `guardrail-hub setup` remains the **local** credential-provisioning mechanism (e.g. Windows). It is **not** the container secret-provisioning mechanism; container credentials are owned by the deployment platform/operator. A future non-interactive `guardrail-hub setup --check` preflight may be added, but it is deferred to Phase 5E and is not part of this ADR. Amendment 1 preserves deployment-platform ownership for externally managed secrets but corrects the false implication that a read-only runtime backend requires validation-only host setup.

**Decision I — Bootstrap defect ownership.** A pre-existing wiring defect exists: `mcp-server/app/bootstrap.py:630` constructs `ProviderManager(catalog)` against the current `(factory, catalog, credential_store=None)` signature, so no `CredentialStore` is injected and runtime credential resolution is unreachable in production. This is a known, pre-existing runtime defect — **not** an architectural redesign and **not** part of this ADR's implementation. It will be repaired in Phase 5D, without altering `_resolve_and_attach_credential()` semantics. This ADR does not modify `bootstrap.py`.

## 4A. Amendment 1 — Phase 5 credential setup contract correction

**Amendment status:** Ratified 2026-09-09 by the repository owner (Loi Phan); final owner ratification and Phase 5 closure recorded 2026-09-13. This section is the controlling Phase 5 setup contract wherever it conflicts with historical Decision H, §7, §8, or §11. Historical text remains in place for traceability.

**Scope classification:** **PHASE 5 CONTRACT CORRECTION + PHASE 5 MISSING OPERATOR PROVISIONING CONTRACT.** This is not authorization for a generic secret-management platform.

### H1 — Provisioning and runtime consumption are separate planes

Phase 5 distinguishes two planes with different authority and mutability:

```text
PROVISIONING PLANE
Host/operator tooling
    -> securely creates or replaces an approved deployment credential source

RUNTIME CONSUMPTION PLANE
MCP runtime
    -> reads the already-provisioned credential through its selected backend
```

Runtime use of credential backends remains consumption-oriented. The Windows runtime reads Windows Credential Manager; the file backend reads `<secrets_dir>/<provider_id>`; the env backend reads the externally managed process environment; AWS/Bedrock uses the AWS SDK credential chain. The MCP runtime does not provision deployment secrets. The Windows backend's existing write operations remain available to operator setup; this does not grant the running MCP service a provisioning role. The file and env backend implementations remain strictly read-only.

`guardrail-hub setup` MAY provision a credential only when it runs in a recognized operator-controlled **host** context and has an approved persistence target. The approved Phase 5 targets are Windows Credential Manager for Windows-local execution and the protected project secret directory for the recognized Guardrail Hub Docker Compose project. In externally managed or runtime-mounted contexts, setup remains validation-only.

Therefore:

```text
read-only runtime backend
    !=
validation-only operator setup
```

The runtime file backend remains read-only even when host-side setup creates or replaces the source file that Compose later mounts read-only.

### H2 — Preferred credential persistence hierarchy

Phase 5 establishes this preference order by deployment type:

```text
Windows local
    -> Windows Credential Manager

Guardrail Hub Docker Compose
    -> protected host file secret
    -> mounted read-only into MCP

Generic Docker / Podman
    -> externally managed file or container secret

Kubernetes
    -> Secret or other projected secret volume

Env backend
    -> explicit externally managed compatibility mode

AWS/Bedrock
    -> AWS SDK credential chain
```

Environment mode remains supported but is not the preferred persistence mechanism for provider API keys. File delivery is preferred for container deployments where it is available.

### H3 — `api_key_env` and `.env`

`api_key_env` is environment-credential **locator metadata**. It is not a secret value, a persistence mechanism, or an instruction to use `.env`. The selected backend determines where the actual credential is obtained.

For example:

```yaml
provider_id: nvidia-nim
auth:
  type: api_key
  api_key_env: NVIDIA_API_KEY
```

resolves as:

```text
Windows backend -> GuardrailHub:nvidia-nim
File backend    -> <secrets_dir>/nvidia-nim
Env backend     -> NVIDIA_API_KEY
```

Only env mode consults `api_key_env`; Windows and file identity remain `provider_id`. The deterministic fallback from Decision E remains applicable when env mode is selected and `api_key_env` is absent.

Guardrail Hub setup MUST NOT write provider API keys into `.env`. `.env` MUST NOT be documented as the preferred storage mechanism for LLM provider credentials. An env backend may consume a credential injected by CI/CD, a process supervisor, a container platform, or a deliberate development compatibility workflow, but that external injection is distinct from Guardrail Hub persisting the secret.

### H4 — Guardrail Hub Docker Compose host contract

The supported local Compose source layout is:

```text
mcp-server/
|-- secrets/
|   `-- <provider_id>
`-- docker-compose.yml
```

The Compose runtime contract is:

```text
host ./secrets
    -> container /run/secrets
    -> read-only mount
    -> ContainerFileCredentialBackend
```

For NVIDIA NIM:

```text
host:      mcp-server/secrets/nvidia-nim
container: /run/secrets/nvidia-nim
```

The filename is `provider_id`, never `api_key_env`. The local default may mount the protected directory as one read-only source so adding a configured provider does not require a separate Compose declaration. Native Docker/Compose secrets remain valid for externally managed deployments and are not replaced by this local workflow.

### H5 — Setup execution contexts and supported invocation

The repository packages the CLI through the `guardrail-hub = "app.cli:main"` project script. The guaranteed checkout-local host invocation is run from `mcp-server/`:

```text
uv run guardrail-hub setup
```

`guardrail-hub setup` is also supported when the project has been installed or its virtual environment is active; Phase 5 does not assume a global installation.

| Execution context | Approved persistence target | Setup behavior |
|---|---|---|
| Windows local host | Windows Credential Manager target `GuardrailHub:<provider_id>` | Prompt using hidden input, test the candidate, then persist only on success; reuse an existing credential unless reconfiguration is explicit. |
| Recognized Guardrail Hub Compose project host | Project-anchored `mcp-server/secrets/<provider_id>` | Prompt using hidden input, test the candidate, then provision the protected host source file only on success. |
| Inside the running MCP container | None writable; runtime mount only | Validate/preflight only; MUST NOT write `/run/secrets`. |
| Generic Linux host | None unless an approved host provisioning target is explicitly established | Do not guess a location; require external provisioning or an explicit supported project context. |
| Kubernetes pod | None writable; projected Secret only | Validate only; no Kubernetes API integration. |
| CI/CD or env-managed environment | None; environment is externally managed | Validate only; never create or mutate environment variables. |
| AWS/Bedrock deployment | AWS SDK credential chain | Detect/validate chain availability only; never route AWS credentials through the API-key `CredentialStore`. |

### H6 — Compose host recognition and write authority

Write authority comes from an approved provisioning context, not from platform guessing:

1. Explicit supported project or deployment configuration is authoritative.
2. A recognized Guardrail Hub Compose project structure may establish the host source only when setup can anchor the directory to that project and verify the approved read-only container mapping.
3. Container markers may improve validation messaging but MUST NOT grant write authority.
4. Presence of a generically named `docker-compose.yml`, a `/run/secrets` directory, or a platform value alone is insufficient authority to write.
5. Ambiguity MUST fail safely or prompt for an explicit operator choice; it must never silently select a persistence target.

When Windows-local and Compose-host setup are both plausible, setup must offer an explicit choice. It must not silently write to Windows Credential Manager when the intended runtime is Compose, nor write a project file when Windows-local execution was selected.

### H7 — NVIDIA NIM acceptance contract

Given `provider_id = nvidia-nim`, `api_key_env = NVIDIA_API_KEY`, and an operator who already holds an NVIDIA NIM API key:

**Windows local:** the operator runs the supported setup command, selects Windows-local if a choice is required, enters the key through a hidden prompt, and setup tests the candidate before storing it under `GuardrailHub:nvidia-nim`. A failed test leaves any existing credential unchanged. The Windows runtime reads that Credential Manager target.

**Docker Compose:** the operator runs `uv run guardrail-hub setup` from `mcp-server/` (or `guardrail-hub setup` from an installed project environment), selects the recognized Compose deployment if a choice is required, and enters the key through a hidden prompt. Setup tests the candidate before storing it as the protected host file `./secrets/nvidia-nim`; a failed test leaves any existing file unchanged. Compose mounts the directory read-only; the runtime reads `/run/secrets/nvidia-nim` through the file backend.

The normal Compose journey does not require manually editing `.env` or understanding `NVIDIA_API_KEY`, `GUARDRAILHUB_SECRETS_DIR`, or `/run/secrets`. Those remain advanced deployment details.

### H8 — `--reconfigure` semantics

`guardrail-hub setup --reconfigure <provider_id>` means replace an existing credential only when setup controls an approved writable host target:

- Windows local: hidden prompt, test the candidate, then replace `GuardrailHub:<provider_id>` only on success.
- Recognized Compose host: hidden prompt, test the candidate, then atomically replace `mcp-server/secrets/<provider_id>` only on success.
- Inside an MCP container using the file backend: refuse mutation and validate only.
- Env backend or CI/CD-managed environment: refuse mutation; the environment is externally managed.
- Kubernetes: refuse mutation; the Secret/projected volume is externally managed.
- Generic file-secret deployment: refuse unless a separately explicit, approved host provisioning target has been established.

Reconfiguration does not authorize `.env` mutation or writes to `/run/secrets`.

### H9 — Minimum host-file security contract

The Compose host provisioner is a narrowly scoped setup capability, not a general secret manager. Its implementation MUST satisfy all of the following:

- anchor the root to the recognized Guardrail Hub project secret directory;
- use a validated `provider_id` as the filename and reject traversal or containment escape;
- reject symlink, junction, or reparse-point escape;
- establish least-privilege file and directory permissions appropriate to the host;
- create and replace files atomically, with safe overwrite permitted only through explicit `--reconfigure`;
- enforce a maximum secret size compatible with the runtime file backend;
- add no newline to the entered secret;
- test a candidate credential against only the selected provider before persistence, preserving any existing credential when the test fails;
- place no secret in logs, diagnostics, output, exceptions, subprocess arguments, or process environment;
- keep the directory Git-ignored and excluded from the Docker build context; and
- mount the directory read-only in the MCP container.

No orchestrator SDK, runtime secret-manager pull, generic secret-provider abstraction, or new deployed provisioning service is authorized.

### H10 — Preserved runtime invariants and committed implementation boundary

Amendment 1 changes operator provisioning scope only. It preserves Decisions A-G and I and all existing security invariants in §5. In particular:

- `ContainerFileCredentialBackend` and `EnvVarCredentialBackend` remain read-only;
- Windows and file credential identity remain `provider_id`;
- env identity remains `api_key_env` or the ratified deterministic fallback;
- no provider API key enters `llm.yaml` or normal committed configuration;
- no secret value enters logs or diagnostics;
- backend selection remains explicit, with no implicit fallback and Linux runtime fail-closed behavior preserved;
- AWS credentials remain outside the API-key `CredentialStore` and use the AWS SDK chain; and
- no Kubernetes, Docker, Vault, CSI, or other orchestrator SDK and no hot rotation are introduced.

The committed Phase 5 corrective implementation is confined to the operator/setup and deployment surfaces needed to realize this contract: `app/cli.py`, `app/intelligence/setup/*`, local Compose wiring, setup/deployment documentation, Git/build-context ignore rules, and focused tests. It also contains narrowly scoped supporting changes to credential error reporting, Windows Credential Manager interop, env-name mapping, and non-generative provider connection probes. Those supporting changes do not alter runtime backend mutability, provider/model routing, adapter credential resolution, AWS authentication, or secret identity semantics. Ratification authorizes no broader runtime change; any change to those preserved semantics requires a separate ratified decision.

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
- **INV-9 — Runtime deployment knowledge stays behind the consumption seam.** Within the MCP runtime, Docker/Podman/orchestration-specific credential consumption remains in the backend + factory, and provider adapters MUST NOT read secret files or API-key environment variables directly. Amendment 1 permits narrowly scoped Compose **host provisioning** knowledge in `app/intelligence/setup/*`; it does not move deployment knowledge into provider adapters or change the runtime credential seam.
- **INV-10 — Rotation requires restart.** Phase 5 provides no hot rotation; a rotated secret takes effect on process restart. Hot rotation is explicitly deferred.

## 6. Consequences

**Gained.** The primary deployment target (Linux containers) becomes supportable without weakening the fail-closed posture. One backend covers Docker, Podman, and orchestrated deployments, so the next target is a configuration value, not a new class. The credential seam, its contract, and its masking are untouched, so blast radius is confined to a new backend plus an explicit selector.

**Accepted.** The word "backend" gains one more concrete implementation to understand. Deployments must now set `GUARDRAILHUB_CREDENTIAL_BACKEND` explicitly on Linux or the server refuses to start — this is intended friction, chosen over a silent insecure default. File-mount delivery reduces process-environment exposure but is not an absolute guarantee (Decision A); the residual deployment-level risks are documented, not solved here.

**Revisit triggers.** A genuine behavioural divergence between orchestrated and plain-container file mounts (would reopen Decision B). A ratified need for runtime secret-manager pull (would add a new backend under Decision C, not modify this one). A requirement for hot rotation (would supersede INV-10).

## 7. Non-goals

At original ratification, this ADR explicitly excluded: any change to AWS/Bedrock authentication (it stays on the AWS SDK credential chain via `mcp-server/app/intelligence/providers/adapters/bedrock.py`, never the `CredentialStore`); VM-specific credential managers; EC2/Azure/GCP instance-metadata credential systems; Kubernetes SDK integration; Vault SDK integration; CSI-specific application integration; runtime secret-manager pulls; application-side encryption-at-rest; any redesign of the `CredentialBackend` contract; Router changes; Model Registry changes; `ModelCatalog` changes; hot secret rotation; the container backend implementation itself; deployment wiring; and CLI implementation. Those last items were sequenced in §8 rather than authorized by the original acceptance. Amendment 1 supersedes only the deployment/CLI exclusion needed for the bounded host-setup contract in H10; every other non-goal remains unchanged.

## 8. Implementation boundary

The original ratification established this sequence, with each phase gated by test → audit → ratify:

- **Phase 5B — Container Credential Backend Foundation.** Implement `ContainerFileCredentialBackend`: read-only file access, provider-id path safety (INV-1), bounded regular-file reads (INV-5), and security/masking tests (INV-3, INV-6). Nothing else; no other module imports it yet.
- **Phase 5C — Orchestrated Credential Integration.** Prove the generic `secrets_dir` contract for orchestrated/file-mounted deployments. No orchestrator SDK.
- **Phase 5D — Deployment Integration.** Deployment-aware backend factory selection (`windows | file | env`, fail-closed per INV-2); optional `EnvVarCredentialBackend` (opt-in, Decision F); and repair of the `bootstrap.py:630` wiring (Decision I) — without changing `_resolve_and_attach_credential()` semantics.
- **Phase 5E — Documentation / Deployment UX.** Docker/Podman/orchestrator deployment documentation; `config/llm.yaml` comment cleanup and correction of its dangling "Decision 0014" reference (which points at the reserved *Provider & Routing* ADR, not this one); ignore rules for a `secrets/` directory; optional `guardrail-hub setup --check`.

The ADR itself implemented none of those phases. Later Phase 5 work now exists, so the original “Phase 5B only” sequencing statement is historical rather than a current description of repository state. The 2026-09-09 ratification confirmed the corrected operator-provisioning contract in H1-H10 against commits `106942e` and `e356ef2`. The final 2026-09-13 owner ratification accepts the completed corrective implementation recorded in §11 and closes Phase 5; it authorizes no broader follow-on implementation.

## 9. Governance / Change-Ladder classification

Per [decision-policy](../standards/core/decision-policy.md): structurally, introducing a new backend that follows the established `CredentialBackend` pattern is **L2 — Extend** (new unit on an existing pattern; Agent-unilateral in the ordinary case). **However**, this decision also changes *which secret sources the application trusts on Linux*, which is a security-relevant control change. Two policy provisions therefore apply: D2 escalation (the level's security relevance forces an escalation, not silent execution) and the Exceptions clause that "**security and correctness outrank the ladder**." The existing `backend_factory.py` fail-closed posture is itself a security control whose own docstring demands "an explicit, ratified decision (ADR)" before secrets are sourced from anywhere new. Accordingly, **an ADR is mandatory before implementation**, notwithstanding the L2 structural classification.

Amendment 1 is **L4 — Evolve architecture** because it changes the accepted operator/security contract in historical Decision H. Repository-owner ratification is therefore required to reconcile and accept the already committed corrective implementation. That code may fit existing setup and deployment seams at L2/L3, but the lower structural level does not remove the authority requirement created by changing a ratified contract.

Runtime-boundary classification: this backend is **not** a runtime boundary. Measured against the four-condition Scope test in [runtime-boundary](../standards/architecture/runtime-boundary.md), it has no own container image, no own process lifecycle, no own external interface, and performs no local execution the server cannot do in-process — and it is imported by the server. Per that standard, "if the server imports it, it belongs in a backend role." It therefore lives under `mcp-server/app/intelligence/credentials/`, alongside the existing backend and factory; no new `app/runtime/` component is created.

No existing accepted decision (0001–0012) governs credentials, LLM authentication, or secrets, so there is no decision conflict. This record is consistent with Guardrail [G1](../guardrails/core.md) (never expose or commit secrets), which every invariant in §5 serves.

## 10. References

AIOS units (existing): [decision-policy](../standards/core/decision-policy.md); [runtime-boundary](../standards/architecture/runtime-boundary.md); [Decision 0007](0007-domain-layer-justification.md); [Decision 0009](0009-execution-capability.md); [Decision 0012](0012-runtime-boundary.md); [guardrails/core.md](../guardrails/core.md); [architecture/intelligence-layer.md](../architecture/intelligence-layer.md) (§7, source of the 0013–0016 reservation).

Repository evidence (source; cited as paths, not links): `mcp-server/app/intelligence/credentials/base.py` (CredentialStore/CredentialBackend, masking); `mcp-server/app/intelligence/credentials/backend_factory.py` (fail-closed factory); `mcp-server/app/intelligence/providers/credential.py` (ProviderCredential masking); `mcp-server/app/intelligence/providers/provider_manager.py` (resolution by `provider_id`); `mcp-server/app/intelligence/registry/loaders/llm_config_loader.py` (provider_id accepted as any non-empty string); `mcp-server/app/intelligence/registry/models/provider.py` (ProviderRecord, `AuthConfig.api_key_env`); `mcp-server/app/intelligence/registry/models/model.py` (models reference a provider); `mcp-server/app/bootstrap.py` (line 630 wiring defect); `mcp-server/app/intelligence/providers/adapters/bedrock.py` (AWS SDK chain, out of scope); `mcp-server/config/llm.yaml` (configuration-only).

Phase 5A audit: `mcp-server/docs/phase-5a-final-audit-and-refinement.md`; `mcp-server/docs/phase-5a-container-credential-architecture-audit.md`.

## 11. Ratification / Acceptance and Phase 5 Closure

**Original acceptance.** Decisions A–I and invariants INV-1..INV-10 were accepted on 2026-08-22. The decisions index already records ADR-0017 as Accepted.

**Amendment 1 acceptance criteria.** The repository owner ratifies H1-H10 as the controlling Phase 5 credential setup contract, confirms that historical Decision H is superseded, and confirms the H10 implementation boundary. The 2026-09-09 ratification satisfied this contract-acceptance gate; the decisions-index status remains Accepted.

**Final owner ratification.** The repository owner (Loi Phan) explicitly ratified the completed Phase 5 implementation on 2026-09-13. This is the owner-acceptance gate following the clean-head audit verdict: **PASS — PHASE 5 IS READY FOR OWNER RATIFICATION**.

**Final implementation evidence.** The ratified implementation/test HEAD is `8161ca8ff8def37ad662378f9c0e062f0b3d2efc` (`test(intelligence): reorganize and clean test suite`). The final corrective range is commits `acd9eb6` through `8161ca8` (inclusive): `acd9eb6`, `7ad5bdc`, `96efb50`, `b8e1c9d`, `119f74f`, `0329d75`, `0cc1442`, `ed70c94`, and `8161ca8`. This final ratification accepts that bounded implementation as aligned with Amendment 1 H1-H10 and its preserved runtime invariants.

**Closure status.** Phase 5 is closed. This closure records governance acceptance of the completed work only; it does not start Phase 6 or authorize further implementation.

**Known non-blocking debt excluded from this closure.** The following items remain outside Phase 5 closure criteria and are not Phase 5 blockers: AIOS source-hash drift maintenance; legacy broader-suite test debt; archived corrupted-repository cleanup; and the local-only untracked `.claude/settings.local.json`. No intelligence source-hash baseline is updated by this closure record.

**Still not authorized:** any further runtime credential-backend or adapter change beyond the narrow, already committed H10 support; changing the credential-backend contract, `bootstrap.py`, `ProviderManager`, model routing, AWS authentication, or credential identity semantics; putting secrets in `config/llm.yaml` or `.env`; adding `setup --check` without separate justification; introducing any orchestrator/Vault/CSI SDK; or implementing hot rotation. This amendment is a governance record and changes no production code.
