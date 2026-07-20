# Architecture Audit — `mcp-server/app/services/`

**Date:** 2026-07-20
**Scope:** Every `.py` file under `app/services/` (39 files, ~4,700 LOC). Review only — no code was modified, no imports rewritten, no folders created.
**Method:** Each file was read in full and classified against the Service Layer Rules (services orchestrate use cases and workflows; DTOs, enums, renderers, throttles, registries, strategies, adapters, pure domain models, and protocols usually belong elsewhere). Consumers were verified by grep (`bootstrap.py` and `main.py` are the composition roots).

---

## 0. Governance constraint (read first)

The Active standard `.ai/standards/architecture/backend-layering@1.0.0` fixes the top-level roles as `routers/, services/, integrations/, dao/, schemas/, helpers/, constants/, core/` and states under **Exceptions**: *"A genuinely new architectural role is a Decision-level change, not an ad-hoc new top-level folder."*

Consequently:

- Creating top-level `domain/`, `execution/`, `notification/`, `presentation/`, or `shared/` folders **requires an ADR + a version bump of the layering standard** (same path ADR-0005 took). This report therefore recommends **subpackage moves inside `services/`** as the default, and flags where a top-level layer would be the ideal end-state if the team ratifies it.
- The `infrastructure/` layer in the audit brief already exists in this codebase under the name `integrations/` (Slack lives in `integrations/chat/slack/`, ZAP transport in `integrations/owasp_zap/`). No new infrastructure folder is needed.
- The `tools/` layer already exists as `services/tools/<tool>/` (standard R2/R3).

---

## 1. Per-file audit

### 1.1 `services/notification/` (7 files, ~1,130 LOC — flat)

**services/notification/notification.py**
→ Move to `services/notification/models/notification.py`
Reason: A single frozen dataclass (`Notification`) — a pure DTO, the message shape the service delivers. No behavior, no orchestration. It is, however, the public boundary type of the notification API, so it belongs *with* the notification context, just not loose beside the service.
Confidence: **High**

**services/notification/operation_progress.py**
→ Move to `services/notification/models/operation_progress.py`
Reason: Pure domain model — `LifecyclePhase` enum, `ScanFindings` and `OperationProgress` frozen dataclasses. Zero orchestration, zero I/O, explicitly documented as "the single, vocabulary-neutral shape the notification layer understands." This is exactly the "dataclasses/enums/pure domain models" category the service rules exclude. (If a top-level `domain/` is ever ratified by ADR, this file is the strongest candidate to seed it.)
Confidence: **High**

**services/notification/renderer.py**
→ Move to `services/notification/rendering/renderer.py`
Reason: Pure rendering logic (`OperationNotificationRenderer`, `humanize_stage`, progress bars, icon/wording tables). Deterministic model→text transformation with no application workflow and no I/O. This is presentation-layer code; it only imports the progress model.
Confidence: **High**

**services/notification/throttle.py**
→ Move to `services/notification/policy/throttle.py`
Reason: `ProgressThrottle` is a pure, stateful throttling algorithm (stage-change / 10% / 30s gate) with an injectable clock. It is a policy, not a service — no coordination of repositories, workers, or external systems.
Confidence: **High**

**services/notification/event_subscriber.py**
→ Move to `services/notification/subscribers/event_subscriber.py`
Reason: `EventNotificationSubscriber` is thin glue: template-render a `DomainEvent`, hand it to `NotificationService`. It is an event-subscription adapter rather than an application service, but it does invoke a workflow (delivery), so it sits at the edge of the service layer rather than outside the package. Subpackage move only.
Confidence: **Medium**

**services/notification/operation_notifier.py**
→ Move to `services/notification/dispatch/operation_notifier.py` (stays in `services`)
Reason: This is real application logic — the capability-aware delivery strategy (update-vs-new-message, throttling, per-operation state, background refresh ticker, best-effort error handling). It orchestrates the renderer, throttle, and `NotificationService`. Correctly a service-layer unit; the move is purely organizational (461 lines of implementation detail hidden behind a package boundary).
Confidence: **High** (belongs in services) / **Medium** (that the subfolder is worth it — see §3.1)

**services/notification/notification_service.py**
→ Keep at `services/notification/notification_service.py`
Reason: Textbook application service: routes a notification to a registered channel port (`NotificationChannel`), exposes capabilities, delegates delivery. Coordinates external systems through ports, contains no SDK code. This is the package's stable public API and should remain at the package root.
Confidence: **High**

### 1.2 `services/operations/` (1 file)

**services/operations/operation_service.py**
→ Keep at `services/operations/operation_service.py`
Reason: The canonical application service of the codebase — owns the Operation lifecycle, coordinates the DAO and the `EventPublisher` port, publishes a domain event per transition. Pure orchestration; deliberately tool-, HTTP-, and notification-agnostic. The event-name constants (`EVENT_OPERATION_*`) are acceptable co-located constants (they *are* the service's contract).
Confidence: **High**

### 1.3 `services/platform/` (2 files)

**services/platform/platform_reporter.py**
→ Keep in `services/platform/`, but flag: extract the rendering
Reason: The class itself is a legitimate service (decides when to log vs. notify, fans lifecycle events to logger + `NotificationService`, best-effort semantics). However ~60 lines (`_render`, `_HEADER`, `_DIVIDER`, emoji titles, label padding) are pure presentation embedded in the service — the same smell `renderer.py` solves for operation cards. Also hard-codes `SLACK_CHANNEL_NAME = "slack"` as a default, leaking transport vocabulary into a service default. The file stays; the rendering should eventually move to a `rendering/` module beside it (or reuse a shared card-rendering helper with `renderer.py` — see §4.3).
Confidence: **Medium** (manual judgement on the split)

**services/platform/lifecycle.py**
→ Keep at `services/platform/lifecycle.py`
Reason: Pure use-case sequencing (`report_startup`, `report_shutdown`) over an injected reporter. Application workflow with no I/O of its own — precisely what the service layer is for.
Confidence: **High**

### 1.4 `services/evaluations/` (2 files)

**services/evaluations/evaluation_service.py**
→ Keep at `services/evaluations/evaluation_service.py`
Reason: Orchestrates a use case: create → start → run injected `scan_runner` → complete/fail, all through `OperationService`. Clean service. (Whether the *package* should exist long-term is a separate question — it is a synchronous alternative to the queued dispatch path and is wired only in `bootstrap.py`; see §3.4.)
Confidence: **High**

**services/evaluations/zap_scan_runner.py**
→ Move to `services/tools/owasp_zap/` (e.g. `services/tools/owasp_zap/sync_runner.py`)
Reason: Tightly coupled to OWASP ZAP — imports `ZapClient` and encodes the ZAP scan sequence (passive → spider → active → alerts). The audit brief is explicit: tool-coupled code stays inside the tool package. The evaluations service would keep receiving it by injection (it already does — `ScanRunner` is a callable), so the move costs one import in `bootstrap.py`. Counter-argument for staying: it is the evaluations context's private execution detail. The coupling rule wins.
Confidence: **Medium**

### 1.5 `services/public/` (2 files)

**services/public/health_service.py**
→ Keep at `services/public/health_service.py`
Reason: Backs the health endpoints so the router stays a thin adapter (it cites the layering standard in its own docstring). The TCP-probing internals (`_tcp_check`, `_postgres_target`) are infrastructure-flavored, but they are small, private, and probing *is* this service's use case. Extracting them to `integrations/` would add a layer without adding clarity.
Confidence: **Medium**

**services/public/history_service.py**
→ Keep at `services/public/history_service.py`
Reason: Thin application service over the DAO for history queries. Exactly where the layering standard wants it.
Confidence: **High**

### 1.6 `services/tools/owasp_zap/` — top level (5 files)

**services/tools/owasp_zap/api_scanner.py**
→ Keep in `services/tools/owasp_zap/` (candidate for internal split — see §3.6)
Reason: The core scan service: submit path (`init_api_scan`) + two ~110-line worker methods orchestrating client, helpers, DAO, and `OperationService`. Correct layer, correct tool package. Two flags: (1) it imports `fastapi.HTTPException` — HTTP status decisions belong in the router, not a service (see §4.1); (2) `zap_scan_worker` / `zap_full_scan_worker` are near-duplicates.
Confidence: **High**

**services/tools/owasp_zap/scan_api_scenario.py**
→ Keep in `services/tools/owasp_zap/`
Reason: Service orchestrating the scenario workflow: submit path + replay/scan execution composing `ScenarioContext`, `ZapClient`, helpers, `OperationService`. Same `HTTPException` flag as above.
Confidence: **High**

**services/tools/owasp_zap/scan_api_suite.py**
→ Keep in `services/tools/owasp_zap/`
Reason: Thin orchestration service — submit path + delegation to `SuiteOrchestrator`. Same `HTTPException` flag.
Confidence: **High**

**services/tools/owasp_zap/scan_web_application.py**
→ Delete (0 bytes)
Reason: Empty file. ADR-0005 already deleted this class of stub ("0-byte stubs were deleted"); these two survived. The router exposes a `scan_web_application` endpoint that is intentionally not implemented — nothing imports this file. Note: `intelligence/module-map.md` lists `interactive_scanner.py, web_scanner.py` as Implemented, which matches neither the filenames nor reality — the intelligence map has drifted and should be corrected alongside the deletion.
Confidence: **High**

**services/tools/owasp_zap/scan_interactive_web_session.py**
→ Delete (0 bytes)
Reason: Identical situation to `scan_web_application.py`.
Confidence: **High**

### 1.7 `services/tools/owasp_zap/execution/` (5 files)

**execution/operation_type.py** (enum), **execution/execution_strategy.py** (enum), **execution/handler.py** (protocol + registry-entry dataclass), **execution/registry.py** (execution registry), **execution/__init__.py** (façade)
→ Keep in `services/tools/owasp_zap/execution/`
Reason: Individually these are exactly the artifact types the service rules exclude from services — an operation-type enum, an execution strategy, a handler protocol, an execution registry. But they are **already isolated in a dedicated `execution/` subpackage** with a clean façade, which is the audit brief's own remedy. The remaining question is whether they should be a *top-level* `execution/` layer. They should not, yet: every unit is ZAP-scoped by name and `handler.py` imports `ZapWorkerInfo` from the ZAP schemas — the seam is tool-coupled in practice. Promote to a generic top-level layer (via ADR, per §0) only when a second tool needs the same engine; until then, promotion would be premature `shared/`.
Confidence: **High** (acceptable as-is) / **Medium** (on deferring promotion)

### 1.8 `services/tools/owasp_zap/handlers/` (4 files)

**handlers/api_scan_handler.py**, **handlers/api_scenario_handler.py**, **handlers/api_suite_handler.py**, **handlers/__init__.py**
→ Keep, but consider relocating to `execution/handlers/` (manual judgement)
Reason: These are adapters (the rules say adapters usually live outside services) plus `build_*_operation` registration factories. They exist solely to satisfy the `execution/` contract, and their only consumer is `bootstrap.py`'s registry construction. They are correctly *not* mixed into the services they wrap. Two clean options: (a) leave as a sibling package (current state — acceptable), or (b) nest under `execution/handlers/` so the contract and its implementations live together and the tool root shrinks. Either is defensible; (b) reads better as the tool grows.
Confidence: **Medium**

### 1.9 `services/tools/owasp_zap/worker/` (3 files)

**worker/worker_service.py**
→ Keep at `services/tools/owasp_zap/worker/worker_service.py`
Reason: True application service — coordinates the Worker Registry (integration) and the Operations DAO across layers; single home for the "worker died → fail its operation" rule shared by the router and the dispatcher. Belongs in services, in the tool package.
Confidence: **High**

**worker/dispatcher.py**
→ Manual judgement: keep in `worker/`, or move to `execution/dispatcher.py`
Reason: `OwaspZapDispatcher` is the execution engine's dispatch loop — the audit brief files "dispatcher" under the execution layer, and its closest collaborators (`ZapOperationRegistry`, `ZapOperation`, `ExecutionStrategy`) all live in `execution/`. Argument for staying: it also owns the heartbeat sweep, which is worker-pool lifecycle, and `worker/`'s own `__init__.py` frames the package as "lifecycle service + queue dispatcher." Both placements are coherent; co-locating dispatch with the registry it routes through (`execution/`) is the more principled cut, at the cost of splitting the two background-loop owners.
Confidence: **Medium**

**worker/__init__.py**
→ Keep (façade re-export; follows the dispatcher if it moves).
Confidence: **High**

### 1.10 `services/tools/owasp_zap/scenario/` (2 files)

**scenario/context.py**
→ Keep at `services/tools/owasp_zap/scenario/context.py`
Reason: Pure domain/workflow logic (topological ordering, `${var}` placeholder resolution, cookie/JWT propagation) — deliberately ZAP-free and deterministic. Not a service, but it is *already* isolated in a dedicated subpackage with a façade, which is the correct treatment for tool-scoped domain logic. Moving it to a global `domain/` would strip its context: it operates on `ScenarioStep` schemas specific to this tool.
Confidence: **High**

**scenario/__init__.py** → Keep (façade). Confidence: **High**

### 1.11 `services/tools/owasp_zap/suite/` (7 files)

**suite/orchestrator.py**
→ Keep at `services/tools/owasp_zap/suite/orchestrator.py`
Reason: Fan-out/fan-in orchestration over child operations — application workflow through injected collaborators. Belongs in services.
Confidence: **High**

**suite/aggregator.py**
→ Keep in `suite/`
Reason: Pure, ZAP-free aggregation of child outcomes into the report structure (`EndpointOutcome` DTO + roll-up function). Domain logic of the suite context, correctly isolated beside its orchestrator.
Confidence: **High**

**suite/findings.py**
→ Keep in `suite/`
Reason: Pure derivation helpers (overall risk, dedup, recommendations, executive summary). Same rationale as `aggregator.py`.
Confidence: **High**

**suite/reporter.py**
→ Manual judgement: keep, or split render vs. persist
Reason: `to_markdown` / `to_json` / `to_sarif` are pure presentation (the brief's "Markdown rendering" category); `save()` mixes in filesystem writes, `settings`, public-URL construction, and logging. The SARIF/ZAP mapping is tool-coupled, so the file stays inside the tool package rather than a generic `presentation/` layer — but the rendering (pure) and persistence (I/O) halves have different reasons to change. If the suite grows another output format, split into `suite/rendering.py` + a small persister; today the single file is tolerable.
Confidence: **Medium**

**suite/openapi.py**
→ Manual judgement: keep, or delete the indirection
Reason: A 16-line re-export of `schemas.tools.owasp_zap.openapi_spec`. Its stated purpose (stable import path, single source of truth) is real but thin; it is one more file whose content is zero. Deleting it means the orchestrator imports from `schemas/` directly — arguably *more* honest about where the parser lives. Low stakes either way.
Confidence: **Low**

**suite/__init__.py** → Keep (façade). Confidence: **High**
**execution/__init__.py**, **handlers/__init__.py** → covered above with their packages.

---

## 2. Summary buckets

### Files that should definitely move

| File | Destination | Type of move |
|---|---|---|
| `notification/operation_progress.py` | `notification/models/` | Subpackage (pure domain model) |
| `notification/notification.py` | `notification/models/` | Subpackage (DTO) |
| `notification/renderer.py` | `notification/rendering/` | Subpackage (presentation) |
| `notification/throttle.py` | `notification/policy/` | Subpackage (algorithm/policy) |
| `evaluations/zap_scan_runner.py` | `services/tools/owasp_zap/` | Cross-package (ZAP-coupled) |
| `tools/owasp_zap/scan_web_application.py` | **delete** | Dead 0-byte stub (per ADR-0005 precedent) |
| `tools/owasp_zap/scan_interactive_web_session.py` | **delete** | Dead 0-byte stub (per ADR-0005 precedent) |

### Files that are acceptable where they are

`notification/notification_service.py`, `operations/operation_service.py`, `platform/lifecycle.py`, `evaluations/evaluation_service.py`, `public/health_service.py`, `public/history_service.py`, `tools/owasp_zap/api_scanner.py`, `tools/owasp_zap/scan_api_scenario.py`, `tools/owasp_zap/scan_api_suite.py`, all of `execution/` (already correctly sub-packaged), `worker/worker_service.py`, `scenario/context.py`, `suite/orchestrator.py`, `suite/aggregator.py`, `suite/findings.py`, and all façade `__init__.py` files.

### Files requiring manual architectural judgement

| File | Question |
|---|---|
| `notification/operation_notifier.py` & `event_subscriber.py` | Worth their own `dispatch/` / `subscribers/` subpackages, or leave at package root once the four High-confidence moves shrink the flat listing? |
| `platform/platform_reporter.py` | Extract the embedded card rendering (and the hard-coded `"slack"` default) — now, or when a second transport appears? |
| `tools/owasp_zap/worker/dispatcher.py` | `worker/` (current) vs. `execution/` (where its collaborators live)? |
| `tools/owasp_zap/handlers/` | Sibling package (current) vs. nested `execution/handlers/`? |
| `tools/owasp_zap/suite/reporter.py` | Split pure rendering from filesystem persistence? |
| `tools/owasp_zap/suite/openapi.py` | Keep the re-export shim or import from `schemas/` directly? |
| `services/evaluations/` as a package | Long-term: is the synchronous evaluation path a distinct bounded context, or a variant of the operations flow that will fold into it? |

---

## 3. Package Organization Review

### 3.1 `services/notification/`

**Current structure:** 7 files flat, ~1,130 LOC.
**Problems:** Five distinct responsibilities interleaved at one level — application API (service), delivery strategy (notifier), presentation (renderer), policy (throttle), models (2 files), event glue (subscriber). The renderer and notifier are the two largest files; a reader cannot tell the public API (`NotificationService`, `Notification`) from internals without opening files.
**Recommended structure:**

```
services/notification/
    notification_service.py        # public API (stays at root)
    models/
        notification.py
        operation_progress.py
    rendering/
        renderer.py
    policy/
        throttle.py
    subscribers/
        event_subscriber.py
    dispatch/
        operation_notifier.py
```

**Reasoning:** Matches the natural dependency flow (models ← rendering/policy ← dispatch ← service) and hides implementation behind package boundaries; `bootstrap.py` is the only external consumer of the internals, so import churn is ~6 lines plus the test mirror (`tests/services/notification/`). A defensible lighter variant: do only `models/` + `rendering/` + `policy/` and leave the two orchestrating units (notifier, subscriber) at the root beside the service.
**Estimated improvement:** **High**

### 3.2 `services/platform/`

**Current structure:** 2 files (`platform_reporter.py`, `lifecycle.py`).
**Problems:** None structural. The only issue is *within* `platform_reporter.py` (embedded rendering — §1.3).
**Recommended structure:** Keep flat. If the rendering is extracted, add a single `rendering.py` module beside it, not a subpackage.
**Reasoning:** Two closely related files; subpackages here would be over-engineering.
**Estimated improvement:** **Low**

### 3.3 `services/operations/` and `services/public/`

**Current structure:** 1 and 2 files respectively.
**Problems:** None.
**Recommended structure:** Unchanged.
**Reasoning:** Small, single-responsibility packages with clear names.
**Estimated improvement:** **Low**

### 3.4 `services/evaluations/`

**Current structure:** 2 files.
**Problems:** Not size — identity. The package duplicates the create→start→run→complete flow that the dispatcher path also drives, and half its code (`zap_scan_runner.py`) is ZAP-coupled and recommended to move (§1.4). After that move it holds a single generic service.
**Recommended structure:** Flat, one file — fine. Track the open question of whether `EvaluationService` eventually merges into `operations/` or grows into a real bounded context (benchmark suites, scheduled evaluations).
**Estimated improvement:** **Low** (structure) — the value is in the `zap_scan_runner` move.

### 3.5 `services/tools/owasp_zap/` (root)

**Current structure:** 5 root files (3 services + 2 empty stubs) + 4 subpackages (`execution/`, `handlers/`, `worker/`, `scenario/`, `suite/`).
**Problems:** (1) Dead 0-byte stubs at the root. (2) `handlers/` and `execution/` are two halves of one concern (contract + implementations) presented as siblings. (3) `dispatcher.py` sits in `worker/` while everything it routes through sits in `execution/`. (4) `api_scanner.py` at 442 lines mixes the submit path with two near-duplicate ~110-line worker methods.
**Recommended structure (target, after ratifying the judgement calls in §2):**

```
services/tools/owasp_zap/
    api_scanner.py            # scan_api service (submit + execution)
    scan_api_scenario.py      # scenario service
    scan_api_suite.py         # suite service
    sync_runner.py            # moved from services/evaluations/zap_scan_runner.py
    execution/
        operation_type.py
        execution_strategy.py
        handler.py
        registry.py
        dispatcher.py         # moved from worker/ (judgement call)
        handlers/             # moved from ../handlers/ (judgement call)
            api_scan_handler.py
            api_scenario_handler.py
            api_suite_handler.py
    worker/
        worker_service.py
    scenario/
        context.py
    suite/
        orchestrator.py
        aggregator.py
        findings.py
        reporter.py
```

**Reasoning:** The package is already the best-organized area of `services/` — the subpackage-per-concern pattern (execution seam, scenario engine, suite engine) is exactly what this audit would otherwise recommend. The remaining wins are consolidation (execution concern in one subtree) and deleting dead files. The `api_scanner.py` duplication is a refactor concern, not a structure concern — out of scope here.
**Estimated improvement:** **Medium**

### 3.6 `execution/`, `scenario/`, `suite/`, `worker/`, `handlers/` (internals)

Covered in §1.7–§1.11 and §3.5. All are appropriately sized (2–7 files), have façade `__init__.py` docstrings that state their contracts, and need no further subdivision. Estimated improvement from touching them beyond §3.5: **Low**.

---

## 4. Cross-cutting findings (outside the move/keep question)

**4.1 `fastapi.HTTPException` raised inside services.** `api_scanner.py`, `scan_api_scenario.py`, and `scan_api_suite.py` raise HTTP exceptions from their submit paths. HTTP status semantics belong to `routers/`; services should raise domain errors the router translates. This violates the spirit of layering rule R4 (services should not know their transport) even though no import-direction rule is broken. Worth a follow-up task independent of any file moves.

**4.2 Intelligence drift.** `intelligence/module-map.md` lists `interactive_scanner.py, web_scanner.py` as Implemented in the ZAP package; the actual files are `scan_interactive_web_session.py` / `scan_web_application.py` and both are 0 bytes. Correct the map when deleting the stubs (G5: the map currently presents a stub as fact).

**4.3 Two card-rendering implementations.** `notification/renderer.py` (operation cards) and the `_render` block in `platform/platform_reporter.py` (platform cards) implement the same "header / labelled fields / divider / footer" layout independently. If both are ever touched together, extract one card-layout helper — a genuine `shared/` candidate, but per the brief: not prematurely.

**4.4 Migration mechanics (when executed).** Order: (1) delete the two stubs + fix the intelligence map; (2) notification subpackage moves (update `bootstrap.py`, `platform_reporter.py` imports + `tests/services/notification/` mirrors); (3) `zap_scan_runner` move (update `bootstrap.py` + `tests/services/evaluations/` mirror); (4) the §2 judgement calls, each as its own small change. Every step should end with `python .ai/tools/aios.py check` and the test suite. Any top-level-layer ambition (`domain/`, `execution/`, `presentation/`) goes through an ADR first, per the layering standard's Exceptions clause.
