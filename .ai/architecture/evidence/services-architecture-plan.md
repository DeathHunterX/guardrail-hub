# Services Architecture Plan — Second-Pass Review (Package Design)

**Date:** 2026-07-20 · **Revised (third pass):** public API surfaces minimized under the Composition Root Exception (§1a); affected sections: D1, §4, migration steps 2 and 5.
**Baseline:** `services-architecture-audit.md` (first-pass, file-placement audit)
**Scope:** Package design of `app/services/` — public API surfaces, subpackage boundaries, dependency direction. Plan only; no code modified.

Two facts discovered in this pass drive several decisions:

- **F1 — No service package has an `__init__.py` today.** `notification/`, `platform/`, `operations/`, `evaluations/`, `public/`, and the `tools/owasp_zap/` root are all implicit namespace packages; only the ZAP subpackages (`execution/`, `handlers/`, `worker/`, `scenario/`, `suite/`) have façades. Every external consumer (`bootstrap.py`, `main.py`, three routers, `platform_reporter.py`) imports deep file paths. Public-API façades are greenfield work — and the highest-leverage change in this plan, because once externals import from package roots, later file moves stop breaking them.
- **F2 — The codebase has deliberate lazy-import discipline around the ZAP scanner.** `bootstrap.py` and `scan_api_suite.py` both import `ZapApiScanService` lazily, explicitly "to avoid importing the zaproxy-dependent scanner at module load." An eager re-exporting `__init__.py` at the `owasp_zap` package root would silently defeat this. This is the "very strong architectural reason" the Public API Rules allow for an exception.

---

# 1. Final Architecture Decisions

**D1 — Add public-API `__init__.py` façades to every service package (before any file moves).**
Why: This is the mechanism that satisfies "separate public API from implementation" — and sequencing it *first* means steps D2–D5 relocate files without touching non-root external importers. Application modules switch from `from app.services.notification.notification_service import NotificationService` to `from app.services.notification import NotificationService` once; internal layout becomes a private concern thereafter. Two carve-outs: the `owasp_zap` package root gets **no eager façade** (F2, §4), and the composition root is exempt from façade-only imports (§1a) — a façade export exists because a package *offers* something to the application, never merely because `bootstrap.py` constructs it.

**D2 — Restructure `services/notification/` into `models/`, `rendering/`, `policy/`, `subscribers/`, `dispatch/` with only `notification_service.py` at the root.**
Why: Accepts the audit's High-confidence moves and resolves its open judgement call (§2 of the audit) in favor of the full structure. The deciding argument is the Responsibility Rules: `OperationNotifier` and `EventNotificationSubscriber` are event-driven delivery mechanisms wired only by the composition root — implementation, not package API. With them at the root, the root would still mix API and internals; with them in `dispatch/`/`subscribers/`, the root contains exactly the one true application service. Each subpackage has a real responsibility (no `utils/`-style buckets), and the internal dependency flow is one-directional: `models ← rendering/policy ← dispatch ← notification_service` consumers.

**D3 — Move `evaluations/zap_scan_runner.py` → `services/tools/owasp_zap/sync_runner.py`.**
Why: Confirms the audit. The file imports `ZapClient` and encodes the ZAP scan sequence; the tool-coupling rule outranks "it's the evaluations context's detail" because `EvaluationService` already receives it as an injected callable — the dependency direction (`evaluations` depends on an abstraction, `bootstrap` binds the ZAP implementation) is *cleaner* after the move, not just tidier.

**D4 — Consolidate the ZAP execution engine: `handlers/` → `execution/handlers/`, `worker/dispatcher.py` → `execution/dispatcher.py`, `worker/worker_service.py` → package root; dissolve `worker/`.**
Why: Resolves both audit judgement calls, in favor of moving. The contract (`handler.py`, `registry.py`), its implementations (`handlers/`), and the loop that drives them (`dispatcher.py`) are one responsibility — the execution engine — currently spread across three sibling packages. `worker_service.py` is the opposite case: a true application service imported by a router, which per the Responsibility Rules belongs at the package root, not inside an implementation subpackage. After D4 the tool root reads as: four application services + one sync runner + three engines (`execution/`, `scenario/`, `suite/`). The counter-argument from the audit (dispatcher also owns the heartbeat sweep, a worker-pool concern) is real but weaker: the sweep is 25 lines of the dispatcher's 310, and both loops share lifecycle (`start`/`stop`), so splitting them by concern would create the abstraction the constraints warn against.

**D5 — Delete dead files: `scan_web_application.py`, `scan_interactive_web_session.py` (0 bytes), and the `suite/openapi.py` re-export shim.**
Why: Stubs confirmed unreferenced; ADR-0005 precedent. The shim: with `suite/__init__.py` already acting as the package façade, a second aliasing layer is redundant — `suite/__init__.py` and `orchestrator.py` import `extract_endpoints` from `app.schemas.tools.owasp_zap.openapi_spec` directly (a legal `services → schemas` dependency). Correct `intelligence/module-map.md` in the same change (it lists the stubs as implemented under wrong names — a G5 accuracy fix).

**D6 — Remove `fastapi.HTTPException` from the three ZAP submit services.**
Why: Services deciding HTTP status codes is a transport concern leaking into the application layer — the inverse of the layering standard's "no business logic in routers." Design: services raise domain errors (`InvalidScanRequestError`, `ScanInitializationError` — defined in `app/core/exception.py`, which already owns custom exception handling); `routers/mcp/owasp_zap_router.py` (or a FastAPI exception handler registered in `core/exception.py`) maps them to the identical 400/500 responses. Behavior-preserving; isolated as its own migration step because it changes code, not just layout.

**D7 — Tests keep importing internals directly.**
Why: The test tree white-box-tests implementation units (`test_throttle.py`, `test_renderer.py`, …). Forcing tests through public façades would either bloat the façades or weaken the tests. Tests update paths when files move (mirroring the new structure) but are exempt from the "import the package root" rule.

## 1a. The Composition Root Exception

A package's public API answers one question: *what do other application modules depend on?* The composition root does not count as "another application module" — its entire responsibility is to know concrete implementations and wire them together. `bootstrap.py` (and `main.py`'s startup/shutdown hooks, which are the same boundary) may therefore import implementation files by their full internal path:

```python
# Allowed, inside bootstrap.py only:
from app.services.notification.dispatch.operation_notifier import OperationNotifier
from app.services.notification.subscribers.event_subscriber import EventNotificationSubscriber
from app.services.tools.owasp_zap.execution.dispatcher import OwaspZapDispatcher
from app.services.tools.owasp_zap.execution.handlers import build_api_scan_operation
```

The consequence for façade design: **"bootstrap imports it" is not a reason to export it.** An earlier draft of §4 exported `OperationNotifier`, `EventNotificationSubscriber`, and `LifecyclePhase` from the notification façade, and the dispatcher + handler factories from the execution façade, purely because the composition root constructs them. Those exports would have advertised wiring internals as stable contracts — every symbol in a façade is an implicit compatibility promise and a coupling opportunity for future code. §4 below is revised accordingly: façades carry only the application-facing contract; the composition root reaches past them by design, and accepts the corresponding maintenance cost (its deep imports are updated when internals move — visible in migration steps 3–5).

The exception applies to **nothing else**. Routers, services, `platform/`, and any future application module depend only on package façades or explicit abstractions (ports, injected callables). A non-root module needing a today-internal symbol is a design signal to evaluate deliberately — either the symbol graduates into the façade as a real contract, or the module is asking for something it shouldn't have.

---

# 2. Rejected Recommendations

**R1 — Unify the duplicated card rendering (notification renderer vs. `PlatformReporter._render`). Rejected for now.**
The duplication is ~40 lines and *intentional divergence*, not drift: the operation renderer explicitly dropped column alignment ("reads like a log; a labelled line reads like a product field") while the platform card keeps aligned columns and a header/divider layout. A shared card abstraction today would need a home that violates the no-new-top-level-layers constraint (`shared/`), or would deepen `platform → notification` coupling from API-level (uses `Notification` + `NotificationService`) to presentation-level. Trigger to revisit: a second transport, or a third card style — then via ADR.

**R2 — Extract rendering out of `platform_reporter.py` into its own module. Rejected for now.**
With R1 rejected, extraction would produce a one-consumer, one-file module purely for symmetry — abstraction without a second reason to change. The file is 256 lines and coherent. Revisit alongside R1.

**R3 — Split `suite/reporter.py` into rendering vs. persistence. Rejected for now.**
Single consumer (`SuiteOrchestrator`), already internal to `suite/`, and no second output format on the horizon. The render methods are individually testable as-is (`test_suite_reporting.py` exists). Splitting now is speculative generality.

**R4 — Promote `execution/` (or `domain/`, `presentation/`) to a top-level layer. Rejected.**
Constraint-mandated, and independently correct: every execution unit is ZAP-scoped in name and imports `ZapWorkerInfo` from ZAP schemas. Promotion is a real future option *when a second tool arrives*, and is precisely what the layering standard's Exceptions clause reserves for an ADR.

**R5 — Move `health_service.py` TCP probing to `integrations/`. Rejected.**
Probing *is* the health use case; the private helpers are small. A relocation would add a layer hop for zero readability gain.

**R6 — Restructure `platform/`, `operations/`, `public/`, `evaluations/` internally. Rejected.**
One to two files each. The Subpackage Rules cut both ways: subpackages must earn their existence. These packages' only change is D1 (façades).

**R7 — Eager public façade for `services/tools/owasp_zap/` root. Rejected (F2).**
An `__init__.py` re-exporting `ZapApiScanService` would import the zaproxy-dependent module chain at package-import time, breaking the lazy-import discipline `bootstrap.py` and `scan_api_suite.py` deliberately maintain. Consumers continue importing the service *modules* directly (`from app.services.tools.owasp_zap.api_scanner import ZapApiScanService`) — module granularity *is* this package's public API. (A PEP 562 lazy `__getattr__` façade was considered and rejected: cleverness that hides an import-cost decision that should stay visible.)

---

# 3. Package Reorganizations

### 3.1 `services/notification/`

```
Current                              Recommended
notification/                        notification/
    notification.py                      __init__.py          # public API (new)
    notification_service.py              notification_service.py
    event_subscriber.py                  models/
    throttle.py                              __init__.py
    operation_progress.py                    notification.py
    renderer.py                              operation_progress.py
    operation_notifier.py                rendering/
                                             __init__.py
                                             renderer.py
                                         policy/
                                             __init__.py
                                             throttle.py
                                         subscribers/
                                             __init__.py
                                             event_subscriber.py
                                         dispatch/
                                             __init__.py
                                             operation_notifier.py
```

### 3.2 `services/tools/owasp_zap/`

```
Current                              Recommended
owasp_zap/                           owasp_zap/
    api_scanner.py                       api_scanner.py
    scan_api_scenario.py                 scan_api_scenario.py
    scan_api_suite.py                    scan_api_suite.py
    scan_web_application.py   ───X       worker_service.py     # from worker/
    scan_interactive_web_session.py ─X   sync_runner.py        # from services/evaluations/
    execution/                           execution/
        __init__.py                          __init__.py       # façade, updated
        operation_type.py                    operation_type.py
        execution_strategy.py                execution_strategy.py
        handler.py                           handler.py
        registry.py                          registry.py
    handlers/                                dispatcher.py     # from worker/
        __init__.py                          handlers/
        api_scan_handler.py                      __init__.py
        api_scenario_handler.py                  api_scan_handler.py
        api_suite_handler.py                     api_scenario_handler.py
    worker/                                      api_suite_handler.py
        __init__.py               ───X   scenario/             # unchanged
        worker_service.py                suite/
        dispatcher.py                        __init__.py       # façade, updated
    scenario/                                orchestrator.py
        __init__.py                          aggregator.py
        context.py                           findings.py
    suite/                                   reporter.py
        __init__.py                      # suite/openapi.py deleted (shim)
        openapi.py                ───X   # NO eager root __init__.py (F2)
        ...
```

### 3.3 `services/evaluations/`, `services/platform/`, `services/operations/`, `services/public/`

Structure unchanged except: each gains an `__init__.py` façade (D1), and `evaluations/` loses `zap_scan_runner.py` (D3).

---

# 4. Public API Review

**`services/notification/`**
Public (exported via `__init__.py`): `NotificationService`, `Notification`, `UnknownChannelError`.
Rationale: the send-a-notification contract — exactly what the one non-root application consumer (`platform_reporter.py`) depends on, and what any future application module should depend on.
Internal (composition root deep-imports them; §1a): `OperationNotifier` (`dispatch/`), `EventNotificationSubscriber` (`subscribers/`), `LifecyclePhase`, `OperationProgress`, `ScanFindings` (`models/`). Each of these appeared in the earlier draft's façade only because `bootstrap.py` constructs or configures them — the definition of a wiring concern, not a contract. The progress models are borderline: they are the vocabulary a future tool-side producer would map into. They graduate into the façade the day a non-root module needs them; exporting them now would be speculative API.
Internal, no external consumer at all: `OperationNotificationRenderer`, `humanize_stage` (`rendering/`), `ProgressThrottle` (`policy/`), `_OperationState`.

**`services/operations/`**
Public: `OperationService` and the `EVENT_OPERATION_*` constants.
Rationale: the constants stay public on contract grounds, not because bootstrap imports them — they are the published event vocabulary that crosses context boundaries (subscribers match on these names). An event name is an inter-context agreement, which is the opposite of an implementation detail.
Internal: nothing else exists.

**`services/platform/`**
Public: `PlatformReporter`, `report_startup`, `report_shutdown`.
Rationale: strictly, both consumers (`bootstrap.py`, `main.py` lifespan hooks) sit at the composition boundary, so the §1a test alone would empty this façade. The exports stay because they pass the *contract* test instead: `report_startup`/`report_shutdown` are the package's use-case entry points (invoking a workflow, not wiring one), and `PlatformReporter` is the abstraction `lifecycle.py` documents itself against. An empty façade on a two-file package would be boundary theater.
Internal: rendering helpers, `SLACK_CHANNEL_NAME` (bootstrap should pass the channel explicitly rather than import the constant).

**`services/evaluations/`**
Public: `EvaluationService`, `ScanRunner` (the type alias — it is the injection contract).
Internal: nothing else after D3.

**`services/public/`**
Public: `HealthService`, `HistoryService`.

**`services/tools/owasp_zap/` (root)**
Public: **no eager façade** (R7/F2). The public surface is defined by module path convention: root modules (`api_scanner`, `scan_api_scenario`, `scan_api_suite`, `worker_service`, `sync_runner`) are importable by routers/bootstrap; subpackages are internal to the tool.
`execution/__init__.py` (façade, exports unchanged): keeps exactly the current contract set — `ExecutionStrategy`, `ZapOperation`, `ZapOperationHandler`, `ZapOperationType`, `ZapOperationRegistry`, `UnknownOperationTypeError` — which is what tool services legitimately import (e.g. `api_scanner` uses `ZapOperationType`). The earlier draft added `OwaspZapDispatcher` and the `build_*_operation` factories; revised out per §1a — their only consumer is `bootstrap.py`, which deep-imports `execution/dispatcher.py` and `execution/handlers/` directly. The dispatcher and registration factories are wiring artifacts, not part of the execution contract.
`suite/__init__.py` and `scenario/__init__.py`: keep current exports; `suite` re-exports `extract_endpoints`/`Endpoint` from `app.schemas.tools.owasp_zap.openapi_spec` after the shim deletion.

---

# 5. Migration Order

Each step is independently shippable, behavior-preserving (except step 6, which preserves responses but changes exception types), and ends with the test suite + `python .ai/tools/aios.py check`.

**Step 1 — Deletions (no importers to fix).**
Delete the two 0-byte stubs; delete `suite/openapi.py` and repoint `suite/__init__.py`, `suite/orchestrator.py`, and `tests/.../test_suite_openapi.py` to `app.schemas.tools.owasp_zap.openapi_spec`. Correct `intelligence/module-map.md`.

**Step 2 — Add façades, then repoint non-root externals (no file moves).**
Create `__init__.py` for `notification/`, `platform/`, `operations/`, `evaluations/`, `public/` re-exporting from *current* file locations, with the minimal §4 surfaces. Switch the non-root consumers — `platform_reporter.py` and the public routers — to package-root imports. `bootstrap.py` and `main.py` are the composition boundary (§1a): they keep deep imports and are *not* repointed to façades for wiring internals. After this step every application module is insulated from the subsequent moves; the composition root alone absorbs path updates in steps 3–5, which is its declared cost.

**Step 3 — `notification/` internal restructure.**
Move the five files into `models/`, `rendering/`, `policy/`, `subscribers/`, `dispatch/`; update intra-package imports, the façade's import paths, `bootstrap.py`'s deep imports (`OperationNotifier`, `EventNotificationSubscriber`, `LifecyclePhase` — §1a), and the `tests/services/notification/` mirror. No *application-module* changes (guaranteed by step 2): `platform_reporter.py` and the routers are untouched.

**Step 4 — `zap_scan_runner` → `owasp_zap/sync_runner.py`.**
Move + rename; update the one lazy import in `bootstrap.py` and the `tests/services/evaluations/test_zap_scan_runner.py` mirror (relocate to `tests/services/tools/owasp_zap/`).

**Step 5 — ZAP execution consolidation.**
Move `handlers/` → `execution/handlers/`, `worker/dispatcher.py` → `execution/dispatcher.py`, `worker/worker_service.py` → root; delete `worker/`; update bootstrap's deep imports (dispatcher, handler factories — §1a), `zap_worker_router.py`, and test mirrors. `execution/__init__.py` exports are unchanged (§4); only its internal import paths are untouched by these moves. Largest step — keep it as one atomic change so `worker/` never half-exists.

**Step 6 — Transport-concern removal (code change, own PR).**
Add domain errors to `core/exception.py`; replace `HTTPException` in the three submit services; map in the router / exception handler. Verify identical status codes via the existing request-validation tests.

**Step 7 — Close the loop.**
Update `intelligence/module-map.md` (and `codegraph.md` if maintained) to the final structure; run the full suite + AIOS check once more.

Ordering rationale: deletions first (shrink the surface), façades before moves (decouple externals once, cheaply), one package per step (small diffs, no cross-package merge conflicts), behavior change last and isolated.
