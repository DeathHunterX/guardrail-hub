# Phase 5A — Container Credential Architecture Audit

> **Status: audit / preparation only.** No source code was modified. This report ends with a single recommendation and a phased implementation plan; it does **not** implement any phase. Wait for explicit ratification.
>
> **⚠ Refined and superseded for ratification by [`phase-5a-final-audit-and-refinement.md`](./phase-5a-final-audit-and-refinement.md).** That Final Audit is the authoritative ratification artifact. Where the two differ, the Final Audit governs. It refines this document's security wording (§3 candidate D, §11), replaces the permission policy with a hard/advisory split, adds the mandatory **provider-id path-safety invariant** (not present in this draft), tightens the role of `api_key_env` (the file backend never reads it), and replaces the phase breakdown in §16 with the ratified **5A → RATIFY → 5B → 5C → 5D → 5E** structure.
>
> **Scope note (AIOS):** This is a Backend, Product-Lane task (`mcp-server/**`). The change it prepares is classified below against `standards/core/decision-policy.md` (the Change Ladder) and `standards/architecture/runtime-boundary.md`. Claims are marked *[verified]* when traced to a file/line in the repo today and *[inference]* when they are engineering judgement or general container-runtime behaviour (per guardrail G5).

---

## 1. Current Architecture

### 1.1 The two halves: configuration vs. credentials

Guardrail Hub already enforces a hard split between *configuration* (which providers/models exist and **how** each authenticates) and *credential material* (the secret value). This is real and verified in code, not aspirational.

**Configuration path** *(verified)*:

```
config/llm.yaml
      │
      ▼
LLmConfigLoader        app/intelligence/registry/loaders/llm_config_loader.py
      │  (EnvironmentResolver expands ${VAR} placeholders in config values only)
      ▼
CatalogBuilder         app/intelligence/registry/builders/catalog_builder.py
      ▼
frozen ModelCatalog    app/intelligence/registry/catalog/catalog.py
      │  (holds ProviderRecord[] + ModelRecord[])
      ▼
ProviderManager        app/intelligence/providers/provider_manager.py
      ▼
Router / LLMService    app/intelligence/inference/{router,services}
      ▼
Provider Adapters      app/intelligence/providers/adapters/{ollama,openai_compatible,bedrock}.py
```

**Credential path** *(verified)*:

```
guardrail-hub setup            app/cli.py  →  app/intelligence/setup/*
      │  (reads llm.yaml, classifies auth.type, prompts for missing api_key secrets)
      ▼
CredentialStore.set(provider_id, secret)     app/intelligence/credentials/base.py
      ▼
CredentialBackend                            (pluggable)
      └── WindowsCredentialManagerBackend     app/intelligence/credentials/windows_backend.py
              namespace  GuardrailHub:<provider_id>
```

### 1.2 CredentialStore contract *(verified)*

`app/intelligence/credentials/base.py` defines a minimal, provider-scoped, **synchronous** secret store:

- `CredentialBackend` (ABC): `get(provider_id) -> str`, `set(provider_id, str) -> None`, `delete(provider_id) -> None`. "No wildcards, no bulk operations."
- `CredentialStore` — a `@dataclass(frozen=True, slots=True)` wrapping one `_backend`; its `__repr__` shows only the backend type, never a value.
- `InMemoryCredentialBackend` — dict-backed, non-persistent; tests/dev only.
- `WindowsCredentialManagerBackend` — ctypes/`advapi32`, zero third-party deps, blob capped at 512 bytes, `CRED_PERSIST_LOCAL_MACHINE`; raises `CredentialBackendError` on non-Windows.
- Exception tree: `CredentialStoreError(LLMConfigurationError)` → `CredentialNotFoundError`, `CredentialBackendError`.

### 1.3 Backend selection *(verified)*

`app/intelligence/credentials/backend_factory.py` → `build_default_credential_backend(platform=None)`:

- `win32` → `WindowsCredentialManagerBackend()`.
- **any other platform → raises `CredentialBackendError`** ("no persistent secure credential backend is available"). This is a deliberate **fail-closed** decision. Its own docstring states the reason: *"a security product must not persist secrets in the clear without an explicit, ratified decision (ADR)."*

### 1.4 Runtime credential resolution *(verified — and more complete than prior notes assumed)*

Runtime resolution **is implemented** (Phase 3), keyed strictly by `provider_id`:

- `ProviderManager.__init__(factory, catalog, credential_store: Optional[CredentialStore] = None)` (`provider_manager.py:51`).
- `_resolve_and_attach_credential(record, adapter)` (`provider_manager.py:276`):
  - Returns immediately unless `record.auth.type == AuthType.API_KEY` (line 304) — `aws` and `none`/absent resolve nothing.
  - If `self._credential_store is None` → raises `LLMConfigurationError` naming the provider, never the secret (310–314).
  - `api_key = self._credential_store.get(record.provider_id)` (line **317**) — the single point where a secret enters the runtime, keyed by `provider_id`.
  - `CredentialNotFoundError` → `LLMConfigurationError` ("no credential is configured"), `from None` (318–324).
  - `adapter.attach_credential(ProviderCredential(api_key=api_key))` (line 329).
- `ProviderCredential` (`app/intelligence/providers/credential.py`) is a frozen, `repr=False` dataclass whose `__repr__`/`__str__` are masked to `********`; the adapter reads `.api_key` only when building its HTTP client (`openai_compatible.py` sets the `Authorization: Bearer` header at `start()`).

### 1.5 Auth types and provider identity *(verified)*

`app/intelligence/registry/models/provider.py`:

- `AuthType(str, Enum)`: `API_KEY = "api_key"`, `AWS = "aws"`, `NONE = "none"`.
- `AUTH_TYPE_DEFAULT_SENTINEL = object()` marks "auth.type absent from YAML".
- `AuthConfig`: `type`, `api_key_env: Optional[str]` (**the name of an env var — never the value**), `auth_header: Optional[str]`.
- `ProviderRecord`: `provider_id: str` (a plain string — the credential namespace), `provider_type`, `deployment`, `auth`, `connection`, `capabilities`, `enabled`, `priority`.
- The loader **rejects** a literal `auth.api_key` in YAML (`llm_config_loader.py`, `TypeError: auth.api_key is not permitted…`).

The live `config/llm.yaml` declares three providers: `ollama-local` (`auth.type: none`), `openai-cloud` (`auth.type: api_key`, `api_key_env: OPENAI_API_KEY`), `bedrock` (`auth.type: aws`).

### 1.6 Existing deployment surface *(verified)*

The repo already contains container assets:

- `docker/fastapi/Dockerfile` — `python:3.12-slim`, `uv sync --frozen --no-dev`, `COPY app` + `COPY config` (so **secret-free `llm.yaml` is baked into the image**; that is acceptable), runs `uvicorn` as PID 1. It does **not** run `guardrail-hub setup` and provisions no LLM secret.
- `docker-compose.yml` — the `mcp-server` service reads `env_file: ./.env (required:false)` and an `environment:` block; **it already injects non-LLM secrets via env vars** (`OWASP_ZAP_API_KEY`, `POSTGRES_PASSWORD`, `AWS_REGION`). There is **no** top-level `secrets:` block and **no** credential volume.
- `.dockerignore` and `mcp-server/.gitignore` both exclude `.env`, `.env.*` (keeping `.env.example`), `*.pem`, `*.key`, and `guardrail-runtime/` — so secrets are neither committed nor imaged.

---

## 2. Deployment Problem

Docker, Podman, and orchestrated workloads all run on **Linux**. On Linux:

1. **There is no persistent secure credential backend.** `build_default_credential_backend()` raises `CredentialBackendError` on every non-`win32` platform *(verified)*. WCM is Windows-only by nature.
2. **Any `auth.type: api_key` provider therefore cannot start in a container.** With no store injected, `_resolve_and_attach_credential` raises `LLMConfigurationError`; even with a store, no Linux backend exists to hold the secret *(verified)*. `openai-cloud` is exactly such a provider.
3. **The runtime credential wiring is not connected in production anyway** *(verified, pre-existing defect)*. `app/bootstrap.py:630` calls `ProviderManager(catalog)` — a stale, single-positional call that predates today's `(factory, catalog, credential_store=None)` signature. It passes **no** `credential_store` (and mis-binds `catalog` into the `factory` slot). So even on Windows, the live conversation-service path cannot resolve an API key today. Container support cannot be validated end-to-end until this is fixed.
4. **`api_key_env` is inert and the `llm.yaml` guidance is stale** *(verified)*. The `llm.yaml` header says *"set the variable named in auth.api_key_env before starting the app,"* but no runtime code reads that env var — resolution is by `provider_id` against the `CredentialStore`. Left unreconciled, containers would grow a *second, contradictory* secret channel (env var named `OPENAI_API_KEY`) alongside the real one (store keyed `openai-cloud`).

The consequence: the design is correct and secret-safe for local Windows development, but has **no supported way to deliver an API-key secret to the process inside a container**, and the documentation points operators at a mechanism the code ignores.

**Bedrock is not part of this gap** *(verified)*: `bedrock.py` reads `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN`/region from the environment via the AWS SDK chain and never consults the `CredentialStore`. `auth.type: aws` already works in containers through standard AWS mechanisms and is out of scope (§15).

---

## 3. Candidate Approaches

Candidates are for the **`api_key`** channel only (the `none` and `aws` types need nothing new). "Secret exposure risk" is judged against the six security requirements in §11.

### A. Bake secret into the image (Dockerfile `ENV`/`COPY`, or a committed file)
| Property | Assessment |
|---|---|
| Mechanism | Secret literal in image layer or committed config |
| Docker / Podman / Orchestrated | "works" everywhere |
| Secret exposure risk | **Disqualifying.** Violates guardrail **G1** and image/repository safety; secret is in every registry copy and `docker history`. |
| Rotation | Requires image rebuild + redeploy |
| Operational complexity | Low to do, catastrophic to own |
| Portability | High |
| **Recommendation** | **Reject outright.** Not a candidate; listed only to be explicitly excluded. |

### B. Plaintext file written by the app (e.g., a `secrets.yaml`/`guardrail-runtime/…` the app creates)
| Property | Assessment |
|---|---|
| Mechanism | App persists secrets to its own file store |
| Docker / Podman / Orchestrated | works everywhere |
| Secret exposure risk | High — this is precisely what the fail-closed factory refuses to do without an ADR; app-managed plaintext at rest, no platform guarantees |
| Rotation | App-defined |
| Operational complexity | High — reinvents a secret manager; contradicts existing design intent |
| Portability | High |
| **Recommendation** | **Reject.** Re-creates the very "plaintext fallback" the current architecture forbids. |

### C. Environment variables (`OPENAI_API_KEY` / a `provider_id`-derived name)
| Property | Assessment |
|---|---|
| Mechanism | Secret supplied as a process env var; app reads it |
| Docker | yes (`environment:`/`--env`/`.env`) |
| Podman | yes (`--env`, or `--secret …,type=env`) |
| Orchestrated | yes (K8s `secretKeyRef`) |
| Secret exposure risk | **Elevated, and must not be treated as "secure by default"** *(inference, standard container security)*: visible in `/proc/<pid>/environ`; **inherited by every child process** — material here because the app spawns scanner/JMeter subprocesses; surfaced by `docker inspect`/`podman inspect` (`Config.Env`) and in daemon metadata; prone to landing in crash dumps, `env` diagnostics, and logs; fixed at process start (no in-place rotation) |
| Rotation | Poor — requires process restart |
| Operational complexity | Lowest; already used here for `POSTGRES_PASSWORD`, `OWASP_ZAP_API_KEY` |
| Portability | Highest |
| **Recommendation** | **Fallback only** — acceptable for local dev and low-sensitivity setups, behind an explicit opt-in and a documented caveat. Not the default secure path. |

### D. Mounted secret **file** at a well-known path (Docker secrets / Podman secrets / K8s secret volume)
| Property | Assessment |
|---|---|
| Mechanism | Platform mounts each secret as a file; app reads `<dir>/<provider_id>` |
| Docker | yes — Swarm secrets and Compose `secrets:` both surface at `/run/secrets/<name>` |
| Podman | yes — `podman secret … --secret name` mounts at `/run/secrets/<name>` (mirrors Docker deliberately) |
| Orchestrated | yes — K8s `Secret` as a projected volume is files under a mount path |
| Secret exposure risk | **Preferred — reduced process-environment exposure** *(inference, standard behaviour; not an absolute guarantee)*: the value is **not** in the process environment, so it is not inherited by spawned subprocesses and not shown by `docker/podman inspect` env; tmpfs-backed on Swarm/K8s. Host/container security (privileged containers, bind mounts, container escape, debugger access, node compromise) remain **deployment-level** concerns this mechanism does not by itself solve. |
| Rotation | Good — update the secret/file; picked up on next read (restart today; hot-reload possible later, §7) |
| Operational complexity | Moderate — operator declares secrets + a mount |
| Portability | **High and uniform** — Docker, Podman, and K8s all converge on "a file per secret in a directory" |
| **Recommendation** | **Primary mechanism.** |

### E. Runtime pull from an external secret manager (Vault/orchestrator API at request time)
| Property | Assessment |
|---|---|
| Mechanism | App calls a secret-manager API/SDK |
| Docker / Podman | needs an external manager |
| Orchestrated | yes, but couples app to a specific provider API |
| Secret exposure risk | Low in transit; adds network trust + token bootstrap problem |
| Rotation | Excellent (native) |
| Operational complexity | **High** — new dependency, auth-to-the-auth, violates "don't prematurely lock to an orchestrator" |
| Portability | Low without an adapter per manager |
| **Recommendation** | **Defer.** The `CredentialBackend` seam can accommodate it later as another implementation; not needed to satisfy Docker/Podman/orchestrated now. |

**Verdict:** **D primary, C caveated fallback, A/B rejected, E deferred.** Crucially, D is a *single* mechanism (a file in a directory) that all three targets expose identically — which drives the §4 recommendation to **one** container backend, not a per-runtime family.

---

## 4. Recommended Architecture

One new **read-only** backend keyed by `provider_id`, plus a **deployment-aware** (explicit, not magic) factory. Docker, Podman, and orchestrated deployments share it because they all present secrets as files in a directory; the runtime is selected by the mount path, not by a bespoke class per runtime.

```
config/llm.yaml                         (CONFIG ONLY: provider_id, auth.type, api_key_env — NO secrets)
      │
      ▼
LLmConfigLoader → CatalogBuilder → frozen ModelCatalog
      │                                  (ProviderRecord.provider_id, ProviderRecord.auth.type)
      ▼
ProviderManager._resolve_and_attach_credential(record)     [only when auth.type == api_key; keyed by provider_id]
      │  CredentialStore.get(provider_id)
      ▼
CredentialStore ──► CredentialBackend        selected by build_default_credential_backend(mode, ...)
                          │
        ┌─────────────────┼───────────────────────────────┐
        ▼                 ▼                                 ▼
  Windows dev        Container (Linux)                 dev / fallback (opt-in)
  WCM backend        ContainerFileCredentialBackend    EnvVarCredentialBackend
  (read/write;       (READ-ONLY)                       (READ-ONLY; caveated)
   setup writes)     reads <secrets_dir>/<provider_id> resolves api_key_env, else
                     default /run/secrets/…             derived GUARDRAILHUB_CREDENTIAL__<ID>
                          ▲
        ┌─────────────────┼─────────────────┐
   Docker secret     Podman secret     K8s Secret volume
   (/run/secrets)    (/run/secrets)    (projected files)     ← ONE backend, path differs
      │
      ▼
ProviderCredential(api_key=…)  →  adapter.attach_credential()  →  adapter builds authed client

AWS (Bedrock):  auth.type == aws  ──►  AWS SDK credential chain (env/role/config)  [bypasses CredentialStore — unchanged]
```

**Why not the four-way split** (`DockerCredentialBackend` / `PodmanCredentialBackend` / `OrchestratedCredentialBackend`) sketched as the example in the brief: those three would differ only by a directory string. Introducing three classes for one behaviour is **speculative L4** and an explicit anti-pattern under `decision-policy.md` ("Introducing a layer/abstraction for a second implementation that does not exist yet"). There is no present-tense behavioural divergence between them to justify separate types. **One `ContainerFileCredentialBackend` with a configurable `secrets_dir`** carries all three.

---

## 5. Docker Design

**Mechanism:** file-mounted secret, one file per provider, filename = `provider_id`.

- **Delivery.** Define secrets in `docker-compose.yml` and grant them to the `mcp-server` service:
  ```yaml
  secrets:
    openai-cloud:
      file: ./secrets/openai-cloud        # dev; or `external: true` for Swarm-managed
  services:
    mcp-server:
      secrets:
        - openai-cloud                     # → mounted at /run/secrets/openai-cloud
  ```
  Swarm-managed (`external`) secrets are tmpfs-backed and encrypted at rest in Raft; Compose file-secrets are bind-mounted read-only. The **application-facing contract is identical**: a readable file at `/run/secrets/<provider_id>`.
- **App side.** `ContainerFileCredentialBackend(secrets_dir="/run/secrets")` implements `get(provider_id)`: first **validate `provider_id` as a path-safe single filename component** (reject empty, any `/` or `\`, any `..` segment, absolute paths, and any resolved path that escapes `secrets_dir`), then read `<secrets_dir>/<provider_id>`, strip a single trailing newline, return; missing file → `CredentialNotFoundError`; not-a-regular-file / unreadable / oversize / path-unsafe → `CredentialBackendError`. Over-broad file permissions are an **advisory** audit signal, not a hard failure (rootless Podman and projected volumes legitimately differ). `set`/`delete` raise `CredentialBackendError` ("credentials are managed by the deployment; this backend is read-only"). See the Final Audit for the exact hard-vs-advisory split and the path-safety invariant.
- **Image.** Unchanged. `llm.yaml` stays baked in (secret-free); **no secret is ever copied into the image** (preserves `.dockerignore` guarantees).
- **Selection.** The container sets an explicit deployment mode (see §8/§12) so the factory returns the file backend instead of failing closed.

---

## 6. Podman Design

**Same backend, same path — no new application concept** (satisfies requirement 12, "Docker and Podman should not require completely different application-level concepts").

- **Delivery.** `podman secret create openai-cloud ./secret.txt` then `podman run --secret openai-cloud …` mounts it at **`/run/secrets/openai-cloud`** — the same path Docker uses. `podman-compose`/Quadlet honour the same `secrets:` semantics.
- **Rootless Podman** *(inference, standard behaviour)*: the secret is mounted inside the user's namespace and owned by the container process UID; the file backend must therefore **not hard-assume root ownership** — it checks *readability by the current process*, not a specific UID, and treats world/group-readable perms as a warning surface, not a hard failure (rootless perms differ from rootful). Store-at-rest for rootless secrets lives under the user's data dir, outside our concern.
- **App side.** Identical to §5. If an operator prefers `--secret name,type=env`, that lands in the §C env fallback path, not the file path.

---

## 7. Orchestrated Container Design

Keep it **generic** — no orchestrator SDK, no Kubernetes API coupling.

- **Abstraction:** "resolve `provider_id` → secret from a directory of secret files, path configurable." A Kubernetes `Secret` mounted as a projected volume is exactly that (files under `spec.volumes[].secret` mountPath); so is any future orchestrator that mounts secrets as files. The **same `ContainerFileCredentialBackend`** serves it; only `secrets_dir` changes (e.g. `/var/run/secrets/guardrail-hub`).
- **Env-based orchestration** (`secretKeyRef`) maps to the §C `EnvVarCredentialBackend` with the same `provider_id` keying and the same caveats.
- **Rotation** *(inference)*: file-mounted orchestrator secrets update in place (with a sync delay). Because adapters read the key once at `start()` *(verified)*, rotation currently takes effect **on pod restart**. In-place, restart-free rotation would require reading at request time (or a refresh hook) in the adapter/`ProviderManager` — deliberately **out of scope** for the minimal design and flagged as future work (§16, optional), not built now.
- **Non-coupling:** no `kubernetes`/`hvac` client is introduced. Runtime pull from Vault/CSI (§3E) remains a *possible future backend behind the same seam*, not part of this phase.

---

## 8. Provider Credential Mapping

The identity is `provider_id`, and only `provider_id` (never `model_id`) — already true in code *(verified, `provider_manager.py:317`)*.

```
llm.yaml  provider_id: "openai-cloud"        (config; declares auth.type: api_key)
      │        (identity — deterministic, model-independent)
      ▼
deployment secret         file  /run/secrets/openai-cloud            (Docker/Podman/K8s)
                     or   env   OPENAI_API_KEY (from api_key_env) / GUARDRAILHUB_CREDENTIAL__OPENAI_CLOUD
      ▼
CredentialStore.get("openai-cloud")
      ▼
ProviderManager._resolve_and_attach_credential(record)   (auth.type == api_key ⇒ resolve)
      ▼
ProviderCredential(api_key=…)  →  adapter.attach_credential()
```

**Naming rules:**
- **File backend:** secret name == `provider_id`; path = `<secrets_dir>/<provider_id>`, subject to the path-safety invariant (see §5 and the Final Audit). The file backend **never reads `api_key_env`** — the filename is derived purely from `provider_id`. An optional configurable prefix (mirroring WCM's `GuardrailHub:` namespace) is available for shared secret stores; default none.
- **Env fallback:** to end the current `api_key_env` inconsistency, the env backend resolves the env var **named by the provider's `api_key_env`** when present (so `openai-cloud` → `OPENAI_API_KEY`), else a deterministic derived name `GUARDRAILHUB_CREDENTIAL__<PROVIDER_ID>` with `-`→`_`, uppercased. The `provider_id → env-name` map is injected at **composition time**, so the backend keeps the unchanged `get(provider_id)` contract.
- **Contract shape unchanged:** every backend still implements exactly `get/set/delete(provider_id)`. Nothing about routing, `ModelRecord`, `ProviderRecord`, `Router`, or `ChatOptions` changes.

This yields **one identity, one value per provider** — no duplicated secrets, and `llm.yaml`'s `api_key_env` finally becomes meaningful instead of a contradictory second source of truth.

---

## 9. `llm.yaml` Contract

**Remains in `llm.yaml` (config only):** `providers[].id` (provider_id), `type`, `deployment`, `enabled`, `priority`, `connection.{base_url,region}`, `auth.type` (`api_key|aws|none`), `auth.api_key_env` (the **name** of an env var), `auth.auth_header`, and the full `models[]` block.

**Must NEVER appear in `llm.yaml`** (and today does not — the loader actively rejects the first item): `auth.api_key` or any literal key/token/secret; AWS access keys/session tokens; bearer values; file paths *containing* secrets; anything that is a credential *value* rather than a *reference*.

**Required documentation fix (doc-only, not a schema change):** the current header comment — *"For api_key: set the variable named in auth.api_key_env before starting the app"* and *"Reference: Decision 0014"* — is inaccurate and dangling:
- Runtime resolution is by `provider_id` via `CredentialStore`, not by reading `api_key_env` *(verified)*.
- **"Decision 0014" does not exist** — `.ai/decisions/` stops at `0012` *(verified)*; the next free number is **0013**.

The comment should describe the real flow (setup/WCM locally; mounted secret file keyed by `provider_id` in containers; env named by `api_key_env` only as a caveated fallback) and cite the ADR proposed in §14 once ratified.

---

## 10. `guardrail-hub setup` Behavior

`setup` is an interactive, hidden-input prompt that **writes** to a persistent secure store *(verified, `app/cli.py` + `setup/service.py`)*. Its role by environment:

- **Local Windows dev:** unchanged and canonical. Prompts for missing `api_key` secrets, writes to WCM keyed by `provider_id`, detects the AWS chain for `aws`, does nothing for `none`. Never writes `llm.yaml`, never creates `.env`, never logs a secret.
- **Docker / Podman / Orchestrated:** `setup` should **not** run inside the container to provision secrets. There is no TTY, and the container secret source is **read-only** and owned by the deployment (Docker/Podman/K8s secret objects created by the operator/CI, outside the app). The `ContainerFileCredentialBackend.set/delete` therefore raise "managed by deployment."
- **Recommended `setup` evolution (optional, §16):** add a non-interactive **`guardrail-hub setup --check`** (a.k.a. doctor) that loads `llm.yaml`, and for every enabled `api_key` provider asserts the current backend can `get(provider_id)` — **without printing the value**. This gives containers a deterministic, fail-closed *preflight* (exit non-zero if any required secret is absent) usable as an init-container/CI gate, reusing the existing exit-code contract.

**Net:** local development keeps its convenient interactive provisioning; container deployments receive secrets entirely through deployment configuration and only *verify* them via `--check`.

---

## 11. Security Analysis

| Concern | File-mount (recommended) | Env fallback | Notes |
|---|---|---|---|
| **Image leakage** | Safe — secret never copied in; `llm.yaml` baked in is secret-free *(verified `.dockerignore`)* | Safe if not set via Dockerfile `ENV` | Never use Dockerfile `ENV`/`ARG` for secrets |
| **Repository leakage** | Safe — `secrets/`, `.env*` gitignored *(verified)*; recommend adding `secrets/` to `.gitignore`/`.dockerignore` | Safe — `.env*` gitignored | Enforced by existing ignores + G1 output scan |
| **Environment leakage** | **Not in env** — not in `/proc/environ`, `inspect` env, or inherited by spawned scanners | **Exposed** in `/proc/<pid>/environ`, `docker/podman inspect`, child processes | Chief reason file-mount is primary |
| **Filesystem leakage** | tmpfs on Swarm/K8s (RAM only); Compose file bind is read-only. File ownership/perms vary by runtime (rootful vs rootless vs projected volume), so the backend verifies **readability by the current process**, not a fixed mode/UID | n/a | Over-broad perms are an advisory signal, not a hard failure |
| **Logs** | `ProviderCredential` masks `repr`/`str` to `********` *(verified)*; store `repr` shows backend type only *(verified)*; errors name provider, never secret *(verified)* | same masking applies | Preserve — add a logging test (§13) |
| **Process inspection** | Value lives in a file the process reads on demand; not on the argv/env of any process | On env of the process **and its children** | Avoid passing secrets as CLI args anywhere |
| **Rotation** | Update secret/file → effective on restart; hot-reload is future work (§7) | Requires restart | Neither leaks during rotation |
| **Provider-id path safety** | **Hard requirement:** `provider_id` is validated as a single path-safe filename before use; separators, `..`, absolute paths, and any path escaping `secrets_dir` are rejected (fail-closed). Defense-in-depth — the loader does *not* restrict `provider_id` characters (`llm_config_loader.py:322-324` only checks non-empty string) | n/a (env-name derivation is composition-time) | Do not rely on upstream sanitization |
| **Permissions** | **Hard:** target exists, is a regular file, is readable by the process, within size cap. **Advisory:** world/group-readable, unusual bits, ownership anomalies (logged, not fatal). No hard-coded root/UID or `0400` requirement | OS-level env, no per-secret perms | Compatible with rootful Docker, rootless Podman, K8s projected volumes |
| **Crash/debug dumps** | Minimized — secret is a short-lived local string, masked object elsewhere | Env is captured by most crash/reporting tooling | Ensure no `/debug` route echoes env |

**Fail-closed (requirement 10):** every path preserves it. Missing/unreadable container secret → `CredentialNotFoundError`/`CredentialBackendError` → `LLMConfigurationError` at provider init, naming only the provider *(verified pattern)*. No silent downgrade to unauthenticated. The factory continues to **refuse** any implicit plaintext behaviour that isn't the ratified file/env mechanism.

---

## 12. Required Code Changes

*Listed for planning only — not modified in this phase.*

**New files**
- `app/intelligence/credentials/container_backend.py` — `ContainerFileCredentialBackend(CredentialBackend)`: read-only `get(provider_id)` from `<secrets_dir>/<provider_id>` (default `/run/secrets`); optional name prefix; `set`/`delete` raise; permission + size sanity checks; no value in any exception/log.
- `app/intelligence/credentials/env_backend.py` *(optional, fallback)* — `EnvVarCredentialBackend(CredentialBackend)` constructed with a `provider_id → env_var_name` map (honours `api_key_env`, else derived name); read-only.
- Test modules per §13.

**Modified files**
- `app/intelligence/credentials/backend_factory.py` — make selection **explicit and deployment-aware**: read a deployment mode (env var, e.g. `GUARDRAILHUB_CREDENTIAL_BACKEND=windows|file|env`, plus `GUARDRAILHUB_SECRETS_DIR`) rather than pure OS sniffing; `win32`→WCM (unchanged); `file`→`ContainerFileCredentialBackend`; `env`→`EnvVarCredentialBackend`; unknown/unset on Linux→**still fail closed**.
- `app/intelligence/credentials/__init__.py` and `base.py` `__all__` — export the new backend(s).
- `app/bootstrap.py` (~line 630) — **fix the stale wiring**: construct the store via the factory and pass it: `ProviderManager(factory=…, catalog=…, credential_store=store)`. Required for *any* runtime credential resolution (Windows or container). *(This is a pre-existing defect surfaced by the audit; see §2.3.)*
- `config/llm.yaml` — correct the stale header comment and dangling "Decision 0014" reference (doc-only, §9).
- `docker/fastapi/Dockerfile` / `docker-compose.yml` / (optional) K8s manifests — add secret mount wiring and the deployment-mode env. *(Deployment config, not application source.)*
- `mcp-server/.gitignore` / `.dockerignore` — add a `secrets/` dev directory to the ignore set.

**Explicitly unchanged** (§18): `CredentialStore` public contract; `CredentialBackend.get/set/delete` shape; `WindowsCredentialManagerBackend`; `ProviderManager` resolution *logic* (only its construction is wired); `Router`, `LLMService`, `ModelCatalog`, `ProviderRecord`/`ModelRecord`, adapters, `ProviderCredential`, `ChatOptions`.

---

## 13. Required Tests

Run with the project runner (`PYTHONPATH=. python3 -m unittest …`; not pytest). Windows-only assertions stay `@skipIf(sys.platform != "win32")`.

**Unit — container file backend** (`tests/intelligence/test_container_credential_backend.py`)
- `get()` returns file contents keyed by `provider_id`; strips exactly one trailing newline.
- Missing file → `CredentialNotFoundError`; unreadable → `CredentialBackendError`.
- `set`/`delete` → `CredentialBackendError` ("read-only/managed by deployment").
- Permission sanity: over-broad perms flagged; rootless process-readable perms accepted (no hard UID assumption).
- Configurable `secrets_dir` and optional prefix honoured (parametrise Docker `/run/secrets` vs. a K8s mount path → proves §7 portability).

**Unit — env fallback backend** — `get()` resolves via injected `api_key_env` map, else derived name; missing → `CredentialNotFoundError`; read-only.

**Unit — factory** — mode `file`/`env` returns the right backend; `win32` unchanged; unset/unknown on Linux still raises `CredentialBackendError` (fail-closed).

**Security** — `repr`/`str` of `ProviderCredential`, `CredentialStore`, and both new backends never reveal a value; missing/oversize/permission errors contain provider id but no secret; a logging test asserts no secret substring reaches a captured log handler.

**Integration** — mirror `test_phase3_credential_resolution.py`: `ProviderManager.start()` with `CredentialStore(ContainerFileCredentialBackend(tmp_dir))` resolves an `api_key` provider and attaches the credential; absent secret → deterministic `LLMConfigurationError`.

**Bootstrap regression** — `build_conversation_service` constructs `ProviderManager` with a store and the corrected signature (guards the §2.3 defect from returning).

---

## 14. ADR Requirements

**One ADR is required before implementation — propose `0013`** (next free number; note `llm.yaml` already dangles a non-existent "0014"). Rationale it must ratify:

1. **Trusting a non-Windows secret source.** The current fail-closed factory *explicitly defers this to a ratified decision* — introducing the file/env backend is that decision.
2. **Change-Ladder classification** (`decision-policy.md`): the new **backend class** is **L2 (Extend)** — another instance of the established `CredentialBackend` pattern. But **changing `build_default_credential_backend`'s selection policy** (what the system trusts as a secret source on Linux) touches ratified fail-closed behaviour and is **security-relevant**, which under **D2** ("the gap is safety-/security-relevant") **escalates to an ADR** regardless of the low structural blast radius. Security outranks the ladder.
3. **Decisions the ADR fixes:** file-mount as primary + env as caveated fallback; `provider_id`→secret-name mapping and the **resolution of `api_key_env`'s role** (wire it as the env-fallback name vs. deprecate it); read-only-in-container semantics; `setup`'s scope (local provisioning vs. container `--check`); the explicit deployment-mode selector (opt-in, not auto-magic).
4. **Runtime-boundary check** (`runtime-boundary.md`): the backend is **not** a runtime boundary — it fails all four scope tests (no own image, no own lifecycle, no own external interface, no local execution). It is ordinary application code under `app/intelligence/credentials/`. No `app/runtime/` placement, consistent with the Phase-4 setup-CLI placement.

The `bootstrap.py` wiring fix (§2.3) is a **defect repair**, not an architecture change, and does not itself need an ADR — but it should ship *with* this work so container support is verifiable.

---

## 15. Non-Goals

Explicitly **out of scope** for this architecture and its implementation phases:

- **AWS EC2 VM credential architecture**; **Azure VM credential architecture**; **GCP VM credential architecture**.
- **Cloud VM-specific secret agents / instance-metadata credential managers** of any provider.
- Provider-specific VM credential managers.
- Any change to **AWS/Bedrock** authentication — it stays on the AWS SDK credential chain (env/role/config), untouched.
- **Unrelated LLM architecture changes**: no routing changes, no `Router`/routing-strategy changes.
- **Model registry redesign**; no changes to `ModelCatalog`, `ProviderRecord`, `ModelRecord`, or the loader/builder beyond the `llm.yaml` comment fix.
- **Kubernetes-specific APIs / SDKs** (no `kubernetes`/`hvac` client); orchestration stays generic (file-mount).
- **Runtime secret-manager pull** (Vault/CSI, §3E) — deferred; possible future backend behind the same seam.
- **Restart-free hot rotation** of an in-use API key — noted as future work, not built.
- Changing the `CredentialBackend` `get/set/delete(provider_id)` contract shape or adding app-side encryption-at-rest.

---

## 16. Implementation Phase Breakdown

*No phase is implemented now. This section is superseded by §6 of the Final Audit; it is restated here so this document does not carry a contradictory plan. Ratification is a **gate**, not a phase.*

```
PHASE 5A  Audit / Design (this document + Final Audit)
    │
    ▼  RATIFY  (accept ADR-0013 — no code)
    │
    ▼
PHASE 5B  Container Credential Backend Foundation (Docker + Podman)
    │        ContainerFileCredentialBackend (read-only, path-safe) + unit/security tests
    ▼  TEST → AUDIT → RATIFY
PHASE 5C  Orchestrated Credential Integration
    │        Generic secret-mount contract (configurable secrets_dir); no orchestrator SDK
    ▼  TEST → AUDIT → RATIFY
PHASE 5D  Deployment Integration
    │        Deployment-aware backend selection (windows|file|env, fail-closed) +
    │        optional EnvVarCredentialBackend + fix bootstrap.py:630 wiring
    ▼  TEST → AUDIT → RATIFY
PHASE 5E  Documentation / Deployment UX
    │        compose/Dockerfile/K8s wiring docs; llm.yaml comment + "Decision 0014" fix;
    │        .gitignore secrets/; optional guardrail-hub setup --check
    ▼  FINAL AUDIT → RATIFY → COMMIT → PHASE 5 CLOSED
```

- **RATIFY gate (no code):** accept ADR-0013 (see §14 / Final Audit §5). Deliverable is `.ai/decisions/0013-*.md` only. Nothing under `app/**`, `config/**`, `docker/**` changes here.
- **Phase 5B — Container Credential Backend Foundation (Docker + Podman).** New `app/intelligence/credentials/container_backend.py` (`ContainerFileCredentialBackend`, read-only, provider-id path-safe) + exports + unit/security tests. Forbidden: touching the factory, bootstrap, adapters, provider/registry code. One backend serves both Docker and Podman (`/run/secrets/<provider_id>`).
- **Phase 5C — Orchestrated Credential Integration.** Prove the *same* backend serves orchestrated deployments via a configurable `secrets_dir` (generic secret-mount contract). No `kubernetes`/`hvac`/Vault SDK. Likely test-only + doc, unless a genuine behavioural divergence is discovered and justified.
- **Phase 5D — Deployment Integration.** Deployment-aware `backend_factory` selection (`windows|file|env`, unset/unknown Linux → **fail closed**); optional `EnvVarCredentialBackend` (opt-in, honours `api_key_env`); and repair of the pre-existing `bootstrap.py:630` wiring so a `CredentialStore` is injected into `ProviderManager`. Must **not** change `_resolve_and_attach_credential()` semantics.
- **Phase 5E — Documentation / Deployment UX.** compose/Dockerfile/(optional) K8s secret wiring; correct the `llm.yaml` header comment and dangling "Decision 0014" reference; add `secrets/` to `.gitignore`/`.dockerignore`; optional non-interactive `guardrail-hub setup --check` preflight.

**Do not** create implementation-file-oriented subphases between these boundaries, and **do not** begin Phase 5B until ADR-0013 is ratified.

---

## 17. Final Recommendation

Introduce **one** read-only, file-based `ContainerFileCredentialBackend` that resolves `provider_id` → `<secrets_dir>/<provider_id>` (default `/run/secrets/`), selected by an **explicit deployment-mode-aware** `build_default_credential_backend` that **fails closed** on an unset/unknown mode under Linux (no auto-detection), and shared unchanged by **Docker, Podman, and orchestrated** deployments (all three surface secrets as files at that path). The backend MUST treat `provider_id` as a **path-safe single filename component** — rejecting empty identifiers, any `/` or `\`, any `..` segment, absolute paths, and any resolved path that escapes `secrets_dir` — as a defense-in-depth control, because no upstream loader or validator currently constrains the character set (`llm_config_loader.py:322-324` checks only for a non-empty string). Keep environment variables as a **caveated, opt-in fallback** (honouring `api_key_env`) for local dev only, and keep `llm.yaml` strictly configuration. **Do not** create separate `Docker`/`Podman`/`Orchestrated` backend classes — they would differ only by a directory string and constitute speculative L4. Ratify this as **ADR-0013** before writing code (the fail-closed factory explicitly requires it, and the selection-policy change is security-relevant), and — during the Deployment Integration phase (5D) — **fix the stale `bootstrap.py:630` wiring** so a `CredentialStore` is actually injected into `ProviderManager` (an existing runtime wiring defect, not part of the credential architecture, and without changing `_resolve_and_attach_credential()` semantics), without which container support cannot be validated end-to-end.

---

*End of Phase 5A audit. No files were modified. Do not proceed to Phase 5B until ADR-0013 is ratified.*
