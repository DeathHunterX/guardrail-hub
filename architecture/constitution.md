# Guardrail Hub — Architecture Constitution

Status: **Active — binding**
Owner: Loi Phan
Since: 2026-07-10 · Grounded in [ADR-0005](../.ai/decisions/0005-architecture-hardening-refactor.md)

---

## 0. Authority & Scope

This Constitution is a **permanent repository rule**. Every human and AI contributor MUST follow it. It is the umbrella over the machine-checked units in [`.ai/standards/`](../.ai/standards/README.md) and the always-loaded [`.ai/guardrails/core.md`](../.ai/guardrails/core.md); where this document states a rule in prose, the corresponding `.ai/` unit is the enforcement point. Nothing here may be *loosened* by a lower document — a lower document may only *tighten*.

Precedence when sources conflict (highest first), per [`AGENTS.md`](../AGENTS.md): **Guardrails → this Constitution / Standards → Decisions (ADRs) → Intelligence → Examples → Playbooks/Templates → Memory.** A safety-relevant gap escalates to a human; it is never guessed.

Changing this Constitution — or any architectural *role*, dependency direction, or standard it names — requires a new **ADR** (`.ai/decisions/`) and, for `.ai/` structure, an **RFC** (`.ai/governance/rfcs/`). There is no informal-edit path. Any change MUST leave `python .ai/tools/aios.py check` passing.

The words **MUST**, **MUST NOT**, **SHOULD**, **MAY** are used in the RFC-2119 sense.

---

## 1. Architectural Principles

1. **Separation of concerns is non-negotiable.** Knowledge (what is true), policy (what is forbidden), and action (what code does) stay in separate places. A file has exactly one responsibility.
2. **Organize by architectural role, then by tool — never by convenience.** Code lives where its *role* dictates (`routers/`, `services/`, …), sub-partitioned by audience or tool. Feature/tool code is a vertical slice across those roles, not a new top-level bucket.
3. **Dependencies point in one direction only:** `routers → services → {integrations, dao, helpers, constants} → core`. Lower layers never import higher ones.
4. **Depend on contracts, not implementations.** Services depend on the DAO interface and on hexagonal **ports**, never on a concrete backend, SDK, or channel adapter.
5. **The edge is thin.** Routers are HTTP adapters; adapters are transport shims. Business logic lives only in `services/` (and the domain core). A router that contains an `if` about business meaning is a defect.
6. **Additive evolution.** New tools, channels, and backends are added by satisfying existing patterns/ports — never by editing the pattern itself. New roles are ADR-level events.
7. **Traceability over confidence.** Every posture/security claim traces to real execution or a declared source (Guardrail [G3](../.ai/guardrails/core.md)); inference is labelled, never presented as fact ([G5](../.ai/guardrails/core.md)).
8. **The map must match the territory.** [`.ai/intelligence/`](../.ai/intelligence/README.md) is the single source of truth about what exists. **Documentation drift is an architectural defect** and blocks a change from being "done."
9. **Verify by tooling, never by hand.** `aios check` + `py_compile` are the gates. Behavior is preserved across refactors.

---

## 2. Repository Folder Responsibilities

| Path | Responsibility | Rule |
|---|---|---|
| `mcp-server/` | The Python/FastAPI backend — the substantially-built product. | All backend rules (§3–§7) apply here. |
| `web/` | Next.js marketing/app frontend (feature-module architecture). | Governed by the `frontend-*` standards (§8). |
| `mobile/`, `api/` | Reserved scaffolds. | MUST stay empty until a real vertical slice + ADR exists. No speculative files. |
| `.ai/` | The AIOS: guardrails, standards, decisions, intelligence, router. | Meta-lane only. Changes need RFC/ADR. |
| `architecture/` | Design docs, one subfolder per subsystem; this Constitution. | Each subsystem owns a `README.md`; link to `.ai/`, don't restate it. |
| `docs/` | Published product docs (VitePress). | No source-of-truth architecture here — that is `.ai/` + `architecture/`. |

**No folder is created before it holds real code.** Empty scaffold directories and 0-byte stub files are forbidden (this is why `client/`, `policies/`, `runner/`, `security/`, `prompts/`, `utils/`, and the `jmeter/`/`playwright/`/`selenium/` stubs were removed in ADR-0005).

---

## 3. Backend Module Responsibilities (`mcp-server/app/`)

The **only** sanctioned top-level roles under `app/` are below. Adding another role requires an ADR.

| Role | Owns | MUST NOT |
|---|---|---|
| `main.py` | App construction, lifespan/startup wiring, middleware, router mounting, `/mcp` + `/public` mounts. | contain business logic. |
| `bootstrap.py` | Composition root — wires ports to concrete adapters. | be imported by lower layers. |
| `core/` | Lowest shared layer: `config/` (composed mixins), `mcp_logger`, `logger_utils`, `exception`, `events/` (dispatcher), `ports/` (hexagonal port interfaces), `startup`. | import from any layer above it. |
| `routers/` | HTTP/MCP adapters only: parse request → call one service → shape response → map domain errors to status codes. | call `dao/`, `integrations/`, or a runtime singleton directly; hold business logic. |
| `services/` | All business logic and orchestration. Sub-partitioned `public/`, `internal/`, `tools/<tool>/`. | reach into another tool's internals; talk to a concrete DB/SDK directly. |
| `integrations/` | Outbound adapters to external systems (ZAP SDK client, Slack, worker registry/pool/scheduler). | contain product business rules. |
| `dao/` | Persistence via hand-written DAO. `base.py` interface + `postgres/` + `dynamodb/`, selected by `DATABASE_PROVIDER`. | use an ORM; import `services/`/`routers/`; be bypassed by anything on the request path. |
| `schemas/` | Pydantic request/response/record models, split `internal/` + `tools/<tool>/`. | hold logic beyond validation. |
| `helpers/` | Stateless, pure helper functions, tool-scoped under `helpers/tools/<tool>/`. | hold orchestration or state. |
| `constants/` | Enums and constant values. | import upward. |

**Worker-pool split (reference for any pooled external tool):** Registry (source of truth for who is registered) / Scheduler (swappable selection strategy) / Pool Manager (ties them + caches clients) / Dispatcher (background queue-poll + sweep) are **distinct units**. Scheduling logic MUST NOT live in the Registry; helper/orchestration logic MUST NOT live in the Scheduler or Dispatcher beyond its single loop.

**Hexagonal boundary:** cross-domain outbound concerns (events, notifications, future job queue) are defined as abstract **ports** in `core/ports/`; application code depends on the port. Concrete transports (`core/events` in-process dispatcher, `integrations/chat/slack`) are adapters, introduced with their vertical slice.

---

## 4. Dependency Rules (enforced by [backend-layering](../.ai/standards/architecture/backend-layering.md), [persistence-dao](../.ai/standards/architecture/persistence-dao.md))

Allowed import directions (a role may import from any role to its right, never to its left):

```
routers → services → integrations → core
                   ↘  dao         → core
                   ↘  helpers     → core
                   ↘  constants   → core
   (all roles → schemas ; schemas → core only)
```

1. **`core/` imports nothing above it.** (This is why `LoggerUtils` lives in `core/`, not a `utils/` role — it was a `core → utils` inversion.)
2. **Routers → services only.** A router MUST NOT import `dao/`, an `integrations/` singleton (`runtime`), or `WorkerNotRegisteredError`-style domain state, except to *translate* a caught domain exception into an HTTP status. Worker/health precedent: use `ZapWorkerService` / `HealthService`.
3. **Services → the DAO interface (`dao/base.py`), never a concrete backend.** Provider is chosen at runtime by `DATABASE_PROVIDER`, never hard-coded at a call site.
4. **No circular imports.** A change that would make a lower layer import a higher one is rejected, not worked around.
5. **No cross-tool coupling.** `services/tools/<a>` MUST NOT import `services/tools/<b>`. Shared behavior goes to `helpers/`, `core/`, or a shared service — never tool-to-tool.
6. **`web/` and `mcp-server/` share no code.** They are independent apps with independent dependency managers.

---

## 5. Testing Organization

1. **Tests mirror the production source tree.** A test for `app/<path>/<module>.py` lives at `tests/<path>/test_<module>.py`. Flat test directories are forbidden.
2. **Group by architectural domain, not by ad-hoc filename.** e.g. `tests/services/tools/owasp_zap/test_api_scanner.py`, `tests/integrations/owasp_zap/test_pool.py`, `tests/dao/postgres/test_operation_dao.py`.
3. **Cross-module flow/integration tests** live under `tests/flows/`.
4. **Test files are named after the module under test** (`test_channel_adapter.py` for `channel_adapter.py`), not after a vague concept.
5. The suite mirrors the source's package style (namespace packages — no stray `__init__.py`). The current suite is `unittest`-based; introducing a different framework is an ADR-level decision, not an ad-hoc addition.
6. Every non-trivial change MUST leave the suite discoverable and `py_compile`-clean; behavior-changing work adds/updates the mirrored test.

---

## 6. Naming Conventions (enforced by [backend-naming](../.ai/standards/coding/backend-naming.md))

1. **Files:** `snake_case.py`.
2. **Classes:** `PascalCase`. Tool-specific classes use `<Tool><Role>` (`ZapApiScanService`, `OwaspZapPoolManager`, `ZapWorkerService`); generic infrastructure uses `<Role>` (`Settings`, `MCPLogger`, `PostgresDAO`).
3. **Pydantic models for a tool** are tool-prefixed (`ZapApiTarget`, `ZapScanResult`) to avoid collision with a future tool's types.
4. **Logger instances** use the `<ClassName>` form (`MCPLogger("ZapWorkerService")`) — no spaces, no ad-hoc labels.
5. **A new tool follows the ZAP layout exactly:** `schemas/tools/<tool>/`, `services/tools/<tool>/`, `integrations/<tool>/`, `routers/mcp/<tool>_router.py`, `helpers/tools/<tool>_helpers.py`.
6. **Config** is composed mixins: a new category is `core/config/<area>.py` (or `core/config/tools/_<tool>.py`) defining a `<Area>Mixin` added to `Settings`.

---

## 7. Cross-Cutting Code Law

1. **Logging:** all logging goes through `MCPLogger` ([operational/logging](../.ai/standards/operational/logging.md)). Stdlib `logging` and `print()` are forbidden for operational logging.
2. **Never log or commit a secret** ([G1](../.ai/guardrails/core.md)). Never weaken the product's own security controls to ease a task ([G2](../.ai/guardrails/core.md)).
3. **Comments and identifiers are English-only.** Files are UTF-8 and MUST NOT contain NUL bytes or mixed line-ending corruption. (A pre-commit encoding guard is recommended — see ADR-0005 debt.)
4. **Persistence uses the hand-written DAO, never an ORM.** No SQLAlchemy/Alembic without an ADR.
5. **Configuration is environment-driven** via `pydantic-settings`; secrets stay in `.env` (git-ignored), templated in `.env.example`.

---

## 8. Frontend Law (`web/`) — enforced by the `frontend-*` standards

1. Components layer by reuse scope: `components/ui/` (shadcn primitives, CLI-generated — not hand-rolled), `components/common/`, `components/effects/`, `components/layout/`.
2. Page-specific composition lives in `features/<domain>/<name>/` (`<name>.tsx` + `data.ts` + optional `types.ts` + `index.ts`), never in `components/`.
3. Pages are thin App-Router routes using parenthesized route groups; `page.tsx` delegates to its feature module.
4. Hooks live in `web/hooks/` (`use-*.ts`); `lib/` holds non-hook utilities.
5. Site metadata/copy/links live in `config/`, `content/`, `constants/`, cross-cutting types in `types/` — never inlined in components.

---

## 9. Scalability Rules (designed for 15+ tools, 100+ modules, thousands of tests)

1. **Every new tool is a self-contained vertical slice** following the ZAP layout (§6.5). No tool may require editing another tool's files.
2. **Every new notification channel or chat surface is a new adapter** satisfying an existing `core/ports/` port — zero change to the application core.
3. **Pools of external workers self-register;** the server never generates worker addresses from a prefix+count. The Registry is the single source of truth (Kubernetes/Compose-agnostic).
4. **The work queue is the Operations table** (`status=QUEUED`), not in-memory state — queued work survives restarts.
5. **Router registration is additive:** a new tool router is added to `routers/endpoints.py` and, if MCP-exposed, to `MCP_OPERATIONS`; `main.py` stays unchanged.
6. **Tier-0 files stay tiny.** `router/MANIFEST.md` and `guardrails/core.md` are scanned every session — growth there is resisted; detail is addressed on demand, not preloaded.

---

## 10. Modification Rules (the workflow every contributor follows)

1. **Never guess the architecture.** Before changing code, read [`AGENTS.md`](../AGENTS.md), pick your lane, load `guardrails/core.md` + `router/MANIFEST.md` + the Domain Router + the Standards it names, and ground facts in `.ai/intelligence/`.
2. **Do not preserve poor architecture for backward compatibility.** Architecture consistency outranks minimizing file changes. But **external behavior is preserved** across refactors (routes, MCP operation IDs, payload shapes).
3. **Change code and its documentation in the same unit of work.** If a change alters structure, update the affected `.ai/intelligence/` map(s), write/update an ADR, and refresh `architecture/` docs. An out-of-date map is a defect, not a follow-up.
4. **New role / new standard / dependency-direction change ⇒ ADR (+ RFC for `.ai/` structure).** No ad-hoc top-level folders.
5. **Verify before claiming done:** `python .ai/tools/aios.py check` PASSES, `py_compile` is clean across touched code and mirrored tests, no NUL bytes, no stdlib logging, no cross-layer or cross-tool imports introduced.
6. **When a rule and reality disagree, fix reality *or* file an ADR to change the rule — never silently diverge.**

---

## 11. Repository Knowledge Management

Defines which documents are **permanent repository knowledge** (the long-term source of truth, kept synchronized with the implementation) and which are **temporary working artifacts** (scratch output of a single task). The purpose is to keep the repository optimized for both human contributors and AI coding assistants: only documents a future assistant needs to understand the *current* architecture may persist.

### 11.1 Permanent Repository Knowledge

These represent the long-term source of truth and MUST always describe the **current** architecture:

- `AGENTS.md`
- this **Architecture Constitution** (`architecture/constitution.md`)
- **ADRs** (`.ai/decisions/`)
- **`.ai/intelligence/`** (AI knowledge maps)
- **Architecture documentation** (`architecture/**`, subsystem `README.md`s)
- **Sequence diagrams** and **lifecycle documentation**
- **README** files, where applicable

**Outdated permanent documentation is an architectural defect** (restating Principle §1.8). A change that alters the architecture is not "done" until the relevant permanent documents are updated in the same unit of work.

### 11.2 Temporary Working Artifacts

Analysis/planning documents created only to assist during a specific task — e.g.:

- `architecture-understanding.md`
- `refactor-summary.md`
- `migration-report.md`
- `audit-report.md`
- `review-notes.md`
- `implementation-plan.md`
- any other temporary AI analysis/reasoning file

These are **NOT** part of the repository knowledge base. They **MUST NOT** become long-term documentation, and MUST NOT be cited as authoritative.

### 11.3 Lifecycle of Temporary Documents

A temporary document exists **only during the task that generated it**. Once its information has been incorporated into permanent knowledge — the Architecture Constitution, ADRs, `.ai/intelligence/`, architecture documentation, or `AGENTS.md` — the temporary document **MUST be deleted**. It MUST NOT be archived unless it carries significant historical or compliance value **explicitly requested by the project maintainers** (§11.4's carve-out).

### 11.4 AI Context Optimization

This repository is AI-assisted. Every unnecessary document increases **context size**, **token consumption**, **stale knowledge**, and **architectural ambiguity**. Therefore the repository SHOULD contain only documents that future AI assistants need to understand the current architecture. Temporary reasoning, analysis, planning, and refactor reports MUST NOT remain in the repository after their knowledge has been incorporated into permanent documentation.

### 11.5 Documentation Source-of-Truth Priority

When multiple documents describe the architecture, authority runs (highest first):

1. **Architecture Constitution**
2. **ADRs**
3. **`AGENTS.md`**
4. **`.ai/intelligence/`**
5. **Architecture documentation**
6. **Source code**

Temporary documents are **never** authoritative. If a temporary document conflicts with permanent documentation, it is **deleted**, not reconciled. (This orders the *documentation artifacts*; the session rule-precedence of §0 — Guardrails and Standards above the Constitution — still governs rule conflicts.)

### 11.6 Mandatory Cleanup

At the end of **every major architectural task or refactor**, perform a repository cleanup that verifies:

- ✓ Temporary analysis files have been removed.
- ✓ No obsolete architectural reports remain.
- ✓ AI knowledge (`.ai/intelligence/`) reflects the latest implementation.
- ✓ Documentation and code remain synchronized.
- ✓ No stale context is left in the repository.

Repository cleanliness is part of architectural quality. Leaving obsolete temporary documents behind is **repository clutter and an architectural maintenance defect**.

---

## 12. Review Checklist (a change is not mergeable until every box is true)

**Layering & structure**
- [ ] Each new/edited file has exactly one responsibility; no God files.
- [ ] Routers contain no business logic and call **only** services (no `dao/`/`integrations` singletons/DB).
- [ ] Services depend on the DAO interface and on ports, not concrete backends/SDKs/channels.
- [ ] No DAO/registry orchestration leakage; scheduler/dispatcher/registry responsibilities stay separate.
- [ ] No new top-level `app/` role without an ADR; no empty folders or 0-byte stubs added.
- [ ] Dependency direction is `routers → services → integrations|dao → core`; no cycles; no cross-tool imports.

**Conventions**
- [ ] `snake_case` files, `PascalCase`/`<Tool><Role>` classes, tool-prefixed schemas, `<ClassName>` logger names.
- [ ] All logging via `MCPLogger`; no stdlib `logging`/`print`; no secrets logged.
- [ ] Comments/identifiers English-only; file is UTF-8 with no NUL bytes; imports resolve (no stale module paths).
- [ ] A new tool follows the ZAP vertical-slice layout exactly.

**Tests**
- [ ] Tests mirror the source tree, named after the module under test; flow tests in `tests/flows/`.
- [ ] Behavior-changing code has an added/updated mirrored test; suite is `py_compile`-clean.

**Governance & verification**
- [ ] Affected `.ai/intelligence/` maps updated; ADR written for any role/standard/dependency change.
- [ ] `python .ai/tools/aios.py check` passes; static gates clean.
- [ ] Temporary working artifacts from this task were deleted once their knowledge was incorporated into permanent docs (§11).
- [ ] External behavior (routes, MCP operation IDs, payloads) unchanged — or the change is a documented, ADR-backed decision.
- [ ] Guardrails honored: no fabricated results (G3), no unlabelled inference (G5), no weakened security controls (G2), no secret exposure (G1), no unauthorized destructive/outward action (G4).

---

*Amendments to this Constitution are made only by ADR in `.ai/decisions/`, and must leave `aios check` green. This document supersedes any informal architectural understanding and is binding on all future contributors, human and AI.*
