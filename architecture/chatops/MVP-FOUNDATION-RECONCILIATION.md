# MVP Foundation — Reconciliation & Migration Plan

> **Status: AWAITING APPROVAL. No foundation code has been written.** Per approved direction, the **current `mcp-server/app/` code is the source of truth**; the approved MVP architecture docs are reconciled *to* it, never the reverse. Existing working code (ZAP, routers, services, DAO, prompts, config) must not be broken. This plan compares, classifies, and sequences — and stops for sign-off before any implementation.

Owner: Loi Phan · Date: 2026-07-07 · Role: Senior Engineer (implementing, not architecting)

---

## 1. Method (as directed)

1. Compare current implementation with the approved MVP architecture.
2. Identify where they differ.
3. Classify each difference: **Keep as-is · Rename later · Move later · Refactor now (only if low-risk)**.
4. Produce a backward-compatible migration plan.
5. Implement the MVP foundation incrementally **only after this plan is approved**.

---

## 2. What actually exists today (snapshot)

The `mcp-server/app/` layout is more built-out than the refactor spec assumed, and internally consistent:

```
app/
├── core/
│   ├── config/            # pydantic-settings MIXIN PACKAGE (_app/_auth/_database/_security/_server/tools/_zap) + get_settings()
│   ├── exception.py       # error types
│   └── mcp_logger.py      # logging
├── constants/             # batch.py (BatchType), paths.py (ReportPaths)
├── dao/                   # base.py (ABC) + operation_dao.py (factory) + postgres/ + dynamodb/   ← working, both providers
├── helpers/tools/         # owasp_zap_helpers.py
├── integrations/          # owasp_zap/ (client, configurator, pool); jmeter/ (scaffold)
├── prompts/               # basics/, tools/owasp_zap/
├── routers/               # endpoints.py (aggregator); internal/token_router; mcp/{owasp_zap,playwrights,selenium}_router; public/{health,history}_router
├── schemas/               # internal/{operation,audit_request,token_request}; tools/owasp_zap/*; public/, tools/{playwright,selenium} (scaffold)
├── services/              # public/history_service; tools/owasp_zap/{api,interactive,web}_scanner; internal/, tools/jmeter (scaffold)
├── utils/public/          # logger_utils.py
├── main.py                # FastAPI app + FastApiMCP mount (/mcp), includes health + tools routers
└── (client/, policies/, runner/, security/ — present, largely scaffold)
```

The **ZAP path is fully working** end-to-end (schema → mcp router → service → integration client → ZAP container → report → DAO). Nothing in this plan touches it.

---

## 3. Conventions the foundation MUST adopt (from the code, not the spec)

| Concern | Established convention (source of truth) | Consequence for the foundation |
|---|---|---|
| **Configuration** | `core/config/` mixin package; `from app.core.config import settings`; extend by adding a `_mixin` and listing it in `Settings` | Keep the package. **Do not** create `config.py`. Add settings later only via a new mixin, only when a feature needs them. |
| **Ports / adapters** | `dao/base.py` = `ABC` interface; `dao/operation_dao.get_operation_dao()` = factory selecting provider via `settings.database_provider` | Model new outbound ports the **same way**: `ABC` + (where selection is needed) a factory. Use `ABC`, **not** `typing.Protocol`. |
| **Persistence port location** | Persistence interfaces live in `dao/` (`dao/base.py`), not `core/ports/` | New repository interfaces go under `dao/`, following the existing pattern — the spec's `core/ports/repository_ports.py` is superseded. |
| **Router wiring** | Routers aggregated in `routers/endpoints.py`; MCP tools listed in `MCP_OPERATIONS`; `main.py` includes routers + mounts `/mcp` | Any future router registers through `endpoints.py`; not part of the foundation. |
| **Domain language** | `Operation` (`OperationRecord`, `OperationStatus`, `op_id`) and `batch_type` (the tool/category) | North Star says `Job` / `tool`. Keep the code's language now; treat `Job`/`Evaluation` as target vocabulary with a documented mapping (§5). No rename in the foundation. |
| **Logging** | `core/mcp_logger.py` + `utils/public/logger_utils.py` | Existing logging stays authoritative. No new logging module in the foundation. |
| **helpers vs utils** | Both exist and are distinct (`helpers/` tool-side, `utils/` cross-cutting) | Keep both; don't merge. Add to whichever matches an existing item — only when needed (YAGNI). |

---

## 4. Reconciliation classification

Every material difference between the current code and the approved MVP structure, classified.

| # | Element | Current | MVP spec expectation | Classification | Backward-compat action |
|---|---|---|---|---|---|
| 1 | Config | `core/config/` package | `config.py` | **Keep as-is** | Docs corrected to reference the package; no code change |
| 2 | Persistence interface | `dao/base.py` ABC + factory | `core/ports/repository_ports.py` | **Keep as-is** | New repos follow `dao/base` pattern; spec superseded |
| 3 | DynamoDB provider | implemented + working | "removed (YAGNI)" | **Keep as-is** | Retained; ADR note corrected; runs with `POSTGRES` at MVP |
| 4 | Domain language | `Operation` / `batch_type` | `Job` / `tool` | **Rename later** | Keep code terms now; documented mapping (§5); rename is its own future decision |
| 5 | `core/events/` (in-proc dispatcher) | absent | present | **Refactor now (low-risk, additive)** | New leaf package; nothing imports it yet |
| 6 | `core/ports/` (non-persistence outbound ports) | absent | present | **Refactor now (low-risk, additive)** | New `ABC` interfaces only; no implementations |
| 7 | `observability/` | absent (logging via mcp_logger/utils) | present | **Move later** | Not in the foundation task scope; add when metrics are wired |
| 8 | `routers/webhooks/` | absent | present | **Move later** | Add when a chat adapter exists; no chat code at MVP foundation |
| 9 | `services/{evaluations,identity,assets,notification}` | absent (has `services/tools`, `services/public`) | present | **Move later** | Services are explicitly excluded from the foundation task |
| 10 | `integrations/chat/` | absent | present | **Move later** | No chat code in the foundation |
| 11 | `schemas/domain`, `schemas/chatops` | absent (has `schemas/internal`, `schemas/tools`) | present | **Move later** | Domain model is not in the foundation task scope |
| 12 | ZAP router name | `routers/mcp/owasp_zap_router.py` | `evaluation_router.py` | **Rename later** | Working MCP tool; rename is a separate, explicitly-approved change |
| 13 | ZAP app service | `services/tools/owasp_zap/*` | `services/evaluations/*` | **Move later** | Working; relocation is a later, approved refactor |
| 14 | `constants/`, `helpers/`, `utils/` | exist | "implement constants/helpers" | **Keep as-is** | Already satisfied; extend only when a feature needs it (YAGNI) |
| 15 | Scaffold dirs (`client/`, `policies/`, `runner/`, `security/`, `integrations/jmeter`, playwright/selenium stubs) | present | not referenced | **Keep as-is** | Out of scope; do not touch |

**Net:** only **two** items are "Refactor now" (#5, #6) — both purely additive new leaf packages. Everything else is Keep / Move-later / Rename-later.

---

## 5. Ubiquitous-language reconciliation (`Operation` ↔ `Job`/`Evaluation`)

The code's persistence/domain vocabulary predates the North Star vocabulary:

| North Star term | Current code term | Recommendation |
|---|---|---|
| Job (one execution) | `Operation` / `OperationRecord` / `op_id` | Keep `Operation` in existing code; map `Job ≈ Operation` in docs |
| Tool | `batch_type` (`BatchType`) | Keep `batch_type`; map `tool ≈ batch_type` |
| Status | `OperationStatus` | Keep |

**Recommendation:** do **not** rename now. A rename touches working DAO/schemas/services and is a distinct decision with its own migration. Until then, new foundation code stays vocabulary-neutral (ports/events don't hard-code `Operation` *or* `Job`), so it doesn't lock in either name. Flagged as an open item (§10).

---

## 6. Documentation corrections applied in this reconciliation

Small, source-of-truth doc fixes (no code):

- `FOLDER-STRUCTURE-REFACTOR.md` — reconciliation banner added; `config.py` → `config/` package.
- `MVP-SCOPE.md` — `config.py` → `config/` package reference.
- `ADR-0004` (Proposed) — Evolution Point corrected: DynamoDB **retained**; persistence pluggability already realized via `dao/base.py` + factory; ports live in `dao/`.

---

## 7. The MVP foundation to add now (scoped, additive, non-breaking)

Mapping the foundation task's scope onto the reconciled reality:

| Foundation deliverable | Disposition |
|---|---|
| Create agreed folder structure | Add **only** `core/ports/` and `core/events/` (the two additive packages). **Do not** scaffold empty `services/`, `routers/webhooks/`, `integrations/chat/`, `schemas/domain/` trees — empty folders imply intent that doesn't exist yet (consistent with the earlier "remove deferred empty folders" rule). |
| `__init__.py` where appropriate | For the two new packages only. |
| Empty module placeholders | Limited to the two new packages' files. |
| Implement `config.py` | **Satisfied by the existing `core/config/` package** — no new file. |
| Implement constants | **Satisfied by existing `constants/`** — add nothing now (YAGNI). |
| Implement helper utilities | **Satisfied by existing `helpers/`/`utils/`** — add nothing now (YAGNI). |
| Core event dispatcher skeleton | **New:** `core/events/dispatcher.py` (in-process, in-memory publish/subscribe skeleton) + `core/events/catalog.py` (event-name registry skeleton). Infrastructure only, no business logic. |
| Ports interfaces only | **New:** `core/ports/` with `ABC` interfaces (no implementations): event publisher, notification channel, scanner, chat gateway, ephemeral-state. Persistence port stays as `dao/base.py`. |

Explicitly **not** in this foundation (per the task): no services, routers, DAO/database logic, domain model, or business logic.

Proposed new files (interfaces/skeletons only):

```
app/core/
├── ports/
│   ├── __init__.py
│   ├── event_publisher.py        # ABC: publish(event)
│   ├── notification_channel.py   # ABC: send(message, destination); supports(feature)
│   ├── scanner.py                # ABC: run(request) -> result   (ZAP will implement later)
│   ├── chat_gateway.py           # ABC: outbound send + session-mapping contract
│   └── ephemeral_state.py        # ABC: sessions/idempotency/throttle/cancel (Redis later)
└── events/
    ├── __init__.py
    ├── dispatcher.py             # in-process in-memory pub/sub skeleton (implements event_publisher)
    └── catalog.py                # event-name registry skeleton
```

---

## 8. Backward-compatibility guarantees

- **No existing file is moved, renamed, or deleted** by the foundation step.
- `from app.core.config import settings`, the ZAP MCP path, DAO factory, routers, prompts — all unchanged.
- The two new packages are **leaf additions** that nothing imports yet, so they cannot affect runtime behavior.
- Ports are vocabulary-neutral, so they pre-commit to neither `Operation` nor `Job`.
- After implementation I will run `python .ai/tools/aios.py check` and confirm the app still imports/boots before claiming done.

---

## 9. Incremental migration sequence (post-approval)

Each step compiles, breaks nothing, and is independently reviewable/testable:

1. **Foundation A** — `core/ports/` interfaces (this task).
2. **Foundation B** — `core/events/` dispatcher + catalog skeleton (this task).
3. *(later, each its own approved increment)* domain model (`schemas/domain`, reconciling `Operation`/`Job`) → repositories following `dao/base` → application services → webhook routers + chat integration → observability → the ZAP rename/relocation.

Steps 3+ are **not** part of this foundation and are listed only to show the additive path.

---

## 10. Open decisions — need your ✅ before I write code

1. **Foundation scope** = add only `core/ports/` + `core/events/` (config/constants/helpers already satisfied by existing code; no new files there). Confirm?
2. **Minimal placeholders** — do **not** scaffold empty `services/`, `routers/webhooks/`, `integrations/chat/`, `schemas/domain/` trees now. Confirm? (Or do you want the full empty tree created?)
3. **Ports as `ABC`** in `core/ports/` for non-persistence; persistence stays in `dao/base.py`. Confirm?
4. **Domain language** — keep `Operation`/`batch_type` in code now; defer the `Job`/`Evaluation` rename to its own decision. Confirm?

**⏸ Stopping here. No foundation code written. On your approval of §7 + §10, I'll implement Foundation A and B incrementally and verify with `aios check`.**
