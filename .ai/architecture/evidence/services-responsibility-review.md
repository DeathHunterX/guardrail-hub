# Fourth-Pass Architecture Review — Responsibility, Not Location

**Date:** 2026-07-20
**Scope:** Every significant type in `mcp-server/app/services/`, judged by architectural responsibility. Cross-layer context read: `core/ports/`, `core/events/`, `constants/`, `schemas/`, `integrations/chat/slack/`, `bootstrap.py`.
**Prior passes:** audit (file placement) → plan (package design) → minimization (public API) → refactor (executed) → governance (Standard + ADR-0006).
**Nature of this pass:** adversarial. The question is not "did we implement the plan?" (we did) but "was the plan asking the right question?" It largely was not — passes 1–3 optimized *where files sit*, and that lens is blind to the three most consequential findings below, all of which survived every prior pass untouched.

**Headline:** the package organization is now good. The **responsibility allocation is not**. Three defects — a domain concept defined five times, a transport that re-parses rendered text with regex, and an event payload with no schema — are invisible to a folder-placement review and are exactly the kind of thing that becomes unfixable at scale.

---

## 1. Responsibility Classification

Primary responsibility, layer, and verdict per type. **Layer** uses: Application, Domain, Infrastructure, Presentation, Contracts, Cross-cutting.

### Notification context

| Type | Primary responsibility | Secondary | Layer | Verdict |
|---|---|---|---|---|
| `NotificationService` | Application Service (routing + capability lookup) | — | Application | ✅ Correct. Single responsibility, delegates delivery to a port. |
| `Notification` | DTO (a delivery request) | — | Contracts | ✅ Correct as a DTO. But see §3 — it is a *command*, not a model, and its name suggests otherwise. |
| `OperationProgress` | **Domain Model** (a snapshot of an operation's state) | Presentation carrier (title, target, next_action, debug) | Domain **and** Presentation | ⚠️ **Mixed.** See §2.1 — this is the single most consequential type in the codebase and it has two masters. |
| `LifecyclePhase` | Value Object / Domain enum | — | Domain | ⚠️ Duplicates `OperationStatus` (§3, §6-High-2). |
| `ScanFindings` | Value Object (severity breakdown) | — | Domain | ⚠️ One of **five** definitions of the same concept (§6-Critical-1). |
| `OperationNotificationRenderer` | Renderer / Formatter | Vocabulary owner (`_STAGE_WORDING` maps tool terms → user language) | Presentation | ⚠️ Mixed — the stage vocabulary is a *domain translation table* living in a formatter (§2.2). |
| `ProgressThrottle` | Policy | — | Application (policy) | ✅ Correct. Textbook injectable policy, pure, clock-injected. |
| `OperationNotifier` | Application Coordinator | State Object owner (`_OperationState`), delivery strategy, background Lifecycle (ticker) | Application | ⚠️ **Three responsibilities** (§2.3). The largest file in `services/` (461 LOC) and the most likely future hotspot. |
| `_OperationState` | State Object | — | Application | ✅ Correct as private state; but see §2.3 — its ownership is the smell, not its shape. |
| `EventNotificationSubscriber` | Adapter (event → notification) | — | Application | ✅ Correct. Genuinely thin. **But: dead-ish** — see §6-Medium-3. |
| `UnknownChannelError` | Exception | — | Contracts | ✅ Correct. |

### Operations, Platform, Evaluations, Public

| Type | Primary responsibility | Secondary | Layer | Verdict |
|---|---|---|---|---|
| `OperationService` | Application Service (lifecycle) | Event contract owner (`EVENT_OPERATION_*`), ID Factory (`_default_id_suffix`) | Application | ⚠️ Mildly mixed — ID generation is a Factory concern embedded in a service (§2.4). Otherwise the best-designed type in the codebase. |
| `EVENT_OPERATION_*` | **Event contract** | — | Contracts | ⚠️ Correctly public, wrongly located — a cross-context contract living inside one context's implementation file (§4, §6-High-1). |
| `PlatformReporter` | Application Coordinator (log + notify fan-out) | **Renderer** (`_render`, `_HEADER`, `_DIVIDER`), Transport constant owner (`SLACK_CHANNEL_NAME`) | Application + Presentation | ⚠️ **Mixed** (§2.5). Prior passes deferred this twice; at enterprise scale the deferral no longer holds. |
| `report_startup` / `report_shutdown` | Use Case / Workflow | Configuration assembly (integration status, health string) | Application | ✅ Acceptable. Pure sequencing over an injected reporter. |
| `EvaluationService` | Use Case | — | Application | ✅ Correct — but the *package* is questionable (§6-Medium-1). |
| `ScanRunner` (alias) | Protocol / Contract | — | Contracts | ✅ Correct as an injection seam. |
| `HealthService` | Application Service | **Infrastructure probing** (raw `socket.create_connection`, URL parsing) | Application + Infrastructure | ⚠️ Mixed (§2.6). Prior passes said "leave it"; at scale this is a Gateway. |
| `HistoryService` | Application Service (read model) | — | Application | ⚠️ Correct responsibility, but constructs its own DAO in `__init__` — a Service Locator anti-pattern inconsistent with every other service (§6-High-3). |

### ZAP tool package

| Type | Primary responsibility | Secondary | Layer | Verdict |
|---|---|---|---|---|
| `ZapApiScanService` | Application Service (submit) | **Execution Engine** (two ~110-line scan workers), Thread-pool owner, Singleton | Application + Infrastructure | ⚠️ **Heavily mixed** (§2.7). 442 LOC, module-level `ThreadPoolExecutor`, `__new__` singleton. The #1 maintenance hotspot. |
| `ZapApiScenarioService` | Application Service (submit) | Execution Engine (`_run_scenario`), HTTP Gateway (`_send_step` via httpx), Singleton | Application + Infrastructure | ⚠️ Same pattern; additionally performs **raw outbound HTTP from a service** (§2.7). |
| `ZapApiSuiteService` | Application Service (submit) | Factory (builds `SuiteOrchestrator` per run), Singleton | Application | ✅ Closest to correct of the three — it delegates execution rather than inlining it. This is the shape the other two should converge on. |
| `OwaspZapDispatcher` | Execution Engine (queue loop) | **Worker-pool sweeper** (heartbeat), Observability (health summary) | Application/Infrastructure | ⚠️ Two independent engines in one class (§2.8). |
| `ZapOperation` | Execution Contract (registry entry) | Serialization Policy (`serialize_request`/`deserialize_request`) | Contracts | ⚠️ Mixed but *defensibly* — bundling is the explicit design intent. See §2.9. |
| `ZapOperationHandler` | Protocol / Execution Contract | — | Contracts | ✅ Correct. |
| `ZapOperationRegistry` | Registry | — | Application | ✅ Correct. |
| `ZapOperationType` | Value Object (tool identity) | — | Domain/Contracts | ⚠️ Semantic overlap with `BatchType` (§4, §6-High-2). |
| `ExecutionStrategy` | Value Object (execution semantics) | Routing Policy (`requires_worker`) | Domain/Contracts | ✅ Correct — the property is cohesive with the enum. |
| `ApiScan/Scenario/SuiteHandler` | Adapter | Factory (`build_*_operation`) | Application | ✅ Acceptable. Adapter + its factory is conventional. |
| `ZapWorkerService` | Application Service | — | Application | ✅ Correct. Genuinely cross-layer coordination. |
| `ZapScanRunner` | Gateway (drives ZapClient) | — | Infrastructure | ⚠️ Correct responsibility, wrong layer — an Infrastructure Gateway living in `services/` (§6-Medium-2). |
| `ScenarioContext` | **Domain Model** (workflow state) | Placeholder resolution engine | Domain | ⚠️ Pure domain logic living in `services/` (§3). |
| `ScenarioStepError` | Exception | — | Contracts | ✅ Correct. |
| `SuiteOrchestrator` | Workflow / Application Coordinator | — | Application | ✅ Correct. Well-injected, testable. |
| `EndpointOutcome` | DTO | — | Contracts | ✅ Correct. |
| `aggregate_application_report` / `findings.py` fns | **Domain Service** (pure business rules: risk ranking, dedup, recommendations) | — | Domain | ⚠️ Pure domain logic in `services/` (§3, §5). |
| `SuiteReporter` | Renderer (MD/JSON/SARIF) | **Repository/Gateway** (`save()`: filesystem write + URL construction) | Presentation + Infrastructure | ⚠️ **Mixed** (§2.10). Prior pass deferred; SARIF is a published interop contract, which raises the stakes. |

---

## 2. Mixed Responsibility Report

### 2.1 `OperationProgress` — Domain Model + Presentation DTO ⚠️ **HIGH**
Nineteen fields: `operation_id`/`phase`/`stage`/`progress` are domain state; `title`, `target`, `reference`, `next_action`, `summary`, `debug` are *presentation context*, and the docstring openly organizes them by UI hierarchy ("L1 identity, L2 activity, L3 outcome, L4 infrastructure"). A domain model that knows about display levels is not a domain model.
**Split?** **Yes, eventually.** `OperationProgress` (domain snapshot) + `OperationCard` (presentation view model assembled by the notifier). **Why it matters:** today it forces the notifier to hand-carry presentation state across events (`_OperationState.title/target/report_link`), which is the root cause of §2.3's complexity. **Cost:** touches the renderer, notifier, and bootstrap. Not urgent; do it before a second transport or a web dashboard, which is when the domain/presentation conflation becomes load-bearing.

### 2.2 `renderer.py` — Renderer + domain vocabulary table ⚠️ **MEDIUM**
`_STAGE_WORDING` translates tool stage names ("spider", "active scan") into user language ("Discovering attack surface"). That is a *domain-to-user vocabulary mapping* — knowledge about what ZAP stages mean — living inside a text formatter. When a second tool emits "sast_analysis", a contributor must edit the renderer, coupling every tool's vocabulary to one presentation file.
**Split?** **Yes, cheaply.** The mapping belongs beside the tool (each tool declares its stage vocabulary) or in a composition-root map, exactly as `OPERATION_TITLES` already is in `bootstrap.py`. Note the inconsistency: titles are composed at the root, stage wording is hardcoded in the renderer. Same kind of knowledge, two homes.

### 2.3 `OperationNotifier` — Coordinator + State owner + background Lifecycle ⚠️ **HIGH**
Three responsibilities: (a) event→delivery coordination, (b) per-operation state machine (`_OperationState`, 11 fields), (c) a background refresh thread with `start`/`stop`/`_ticker_loop` and an `RLock`. It also embeds delivery de-duplication (`last_message` comparison) and elapsed-time computation.
**Split?** **Yes.** The ticker is a Lifecycle concern with no conceptual tie to notification strategy — it exists solely to keep an elapsed clock advancing. Extracting it (an injectable `RefreshTicker`) would remove threading from the coordinator entirely and make the strategy logic synchronously testable. This is the file most likely to be simultaneously edited by two teams.

### 2.4 `OperationService` — Service + ID Factory ⚠️ **LOW**
`_default_id_suffix` and the `"{batch_type}:{suffix}"` construction are an ID-generation policy. Note the inconsistency it enables: every ZAP service bypasses it (`op_id = str(uuid4())`), so **two ID formats coexist in production** — prefixed (`api_scan:abc`) and bare UUID. The renderer's `_fallback_reference` exists specifically to paper over this ("drops any `<batch_type>:` prefix").
**Split?** Not a file split — but the *policy* should be singular. Two ID shapes is a latent debugging tax.

### 2.5 `PlatformReporter` — Coordinator + Renderer ⚠️ **MEDIUM**
~60 of 256 lines are card rendering (`_render`, `_HEADER`, `_DIVIDER`, emoji titles, column padding). Also hardcodes `SLACK_CHANNEL_NAME = "slack"` as a default parameter — a transport name as a service default.
**Split?** **Yes**, and my prior pass's "reject for now" was the *organization* answer, not the *responsibility* answer. Responsibility-wise it is unambiguous: a coordinator should not format. Combined with §2.10 and §6-Critical-2, this is one of three independent card-rendering implementations.

### 2.6 `HealthService` — Service + Infrastructure probe ⚠️ **MEDIUM**
Opens raw TCP sockets and parses DB URLs. A service reaching for `socket.create_connection` is doing infrastructure work.
**Split?** **Yes at scale** — a `StorageProbe` gateway in `integrations/`. The service then answers "is the system ready?" by asking a probe, which is the correct shape when a second dependency (Redis, S3, ZAP pool) needs probing — and that day is coming.

### 2.7 The three ZAP scan services — Submit Service + Execution Engine + Infrastructure ⚠️ **CRITICAL**
`api_scanner.py` is the clearest: `init_api_scan` (submit use case, ~60 lines) sits beside `zap_scan_worker` and `zap_full_scan_worker` (~110 lines each of ZAP orchestration), plus a **module-level `ThreadPoolExecutor(max_workers=32)`** and a `__new__`-based singleton. `scan_api_scenario.py` adds raw `httpx` calls. Three distinct responsibilities, plus two infrastructure decisions (threading, singleton lifetime) hardcoded at module scope where no test or deployment can vary them.
**Split?** **Yes — highest-value split in the codebase.** Submit path → service; scan execution → an explicit executor/engine object; thread pool → injected. `ZapApiSuiteService` already demonstrates the target shape (delegates to `SuiteOrchestrator`). The two worker methods are also near-duplicates of each other, so the split pays twice.

### 2.8 `OwaspZapDispatcher` — Queue engine + Heartbeat sweeper ⚠️ **MEDIUM**
Two independent background loops with unrelated triggers, sharing only `start`/`stop`. My third-pass reasoning ("the sweep is only 25 lines") was a size argument, not a responsibility argument — and size arguments are exactly what let files drift. Worth revisiting: the sweep is worker-pool health, the queue loop is dispatch.

### 2.9 `ZapOperation` — Execution Contract + Serialization ✅ **acceptable**
Bundles type, strategy, request model, (de)serialization, and handler. Genuinely multiple responsibilities — but the docstring states the intent: give the Dispatcher exactly one thing to touch. **Do not split.** The alternative leaks request models into the dispatcher. Recorded here so a future reviewer sees it was considered, not missed.

### 2.10 `SuiteReporter` — Renderer + Persistence Gateway ⚠️ **MEDIUM**
`to_markdown`/`to_json`/`to_sarif` are pure; `save()` does `mkdir`, `write_text`, reads `settings`, builds public URLs, and swallows exceptions. Two reasons to change, two failure modes, one class. **SARIF is a published interop contract** (GitHub code scanning ingests it), which makes the rendering half more contractual than the prior pass credited.

---

## 3. Domain Purity Report

Every dataclass, enum, state object, and value object in `services/`:

| Type | True classification | Belongs in `services/`? |
|---|---|---|
| `Notification` (frozen, slots) | **DTO / Command**. It is an instruction ("deliver this"), not a model. | Yes — it is the service's input contract. Consider naming it `DeliveryRequest`; "Notification" implies an entity that persists, which it does not. |
| `OperationProgress` (frozen, slots) | **Domain Model** with a Presentation DTO welded on. | **No, not purely.** The domain half is a genuine tool-neutral model; the presentation half belongs to a view model. See §2.1. |
| `ScanFindings` (frozen, slots) | **Value Object** — immutable, equality by value, no identity. Textbook. | **No.** This is a *security domain* concept (severity breakdown), not a notification concept. It lives in `services/notification/models/` purely because notification was the first consumer. See §6-Critical-1. |
| `LifecyclePhase` (str Enum) | **Value Object**. | **No.** It is a near-copy of `schemas/tools/owasp_zap/common.OperationStatus` (same five members, same string values), duplicated to avoid an import. The comment admits it: "defined here so the notification context does not import a tool/domain enum." The right fix is not duplication — it is moving `OperationStatus` out of the *ZAP tool schema* (where operation status has no business living) into a shared domain/contracts location both can depend on. |
| `_OperationState` (mutable dataclass) | **State Object**. | Yes — correctly private, correctly mutable, correctly owned by the coordinator. Only concern is how much it carries (§2.3). |
| `ProgressThrottle` (mutable dataclass) | **Policy** with internal state. | Yes. Correct. |
| `ZapOperation` (frozen) | **Execution Contract**. | Yes. |
| `EndpointOutcome` (mutable dataclass) | **DTO**. | Yes — internal to the suite engine. Could be frozen; mutability is unused. |
| `ScenarioContext` (plain class) | **Domain Model** (workflow state + propagation rules). | **No, architecturally.** Pure domain logic, zero ZAP dependency by explicit design. It sits in `services/` only because the constraint forbids a `domain/` layer. |
| `ExecutionStrategy`, `ZapOperationType` (str Enums) | **Value Objects**. | Yes, as tool contracts. |

**Pattern:** four types (`ScanFindings`, `LifecyclePhase`, `ScenarioContext`, the `findings.py` rule functions) are **domain concepts living in the application layer because no domain layer exists**. The refactor's no-new-top-level-layer constraint (correct at the time — it prevented premature structure) has now produced the opposite problem: domain knowledge scattered across whichever application package happened to need it first. **This is the central architectural finding of this review.**

---

## 4. Constants Report

| Constant | Classification | Current home | Recommended ownership |
|---|---|---|---|
| `EVENT_OPERATION_*` (6) | **Event contract** (cross-context) | `services/operations/operation_service.py` | **Move.** A contract consumed by another context should not live inside one context's service implementation. Belongs in `core/` (beside `ports/event_publisher.py`) or a contracts module. This is the clearest constant-level responsibility mismatch. |
| `DEFAULT_MIN_PERCENT_STEP`, `DEFAULT_MIN_INTERVAL_SECONDS` | **Configuration** (tuning values) | `policy/throttle.py` | Stay as defaults — but note they are *not* settings-driven, so throttling cannot be tuned per environment. At enterprise scale, promote to `Settings`. |
| `_PHASE_ICON`, `_PHASE_STATUS`, `_DEFAULT_TITLE`, `_DIVIDER` | **Local presentation constants** | `rendering/renderer.py` | ✅ Stay. Correctly private, correctly co-located. |
| `_STAGE_WORDING` | **Domain vocabulary**, not a local constant | `rendering/renderer.py` | **Move** — per-tool or composition root (§2.2). |
| `SLACK_CHANNEL_NAME` | **Transport identifier** | duplicated in `platform_reporter.py` **and** `bootstrap.py` | **Consolidate.** Defined twice with the same value. Belongs at the composition root only; the service should receive it. |
| `_HEADER`, `_DIVIDER`, `_SERVER` (platform) | Local presentation constants | `platform_reporter.py`, `lifecycle.py` | Stay — but `_SERVER = "mcp-server"` is defined in **both** files. Duplication of an application identity value. |
| `_SERVICE_NAME` | Application-wide identity | `public/health_service.py` | Should derive from config/`app_name`, not a literal. Third distinct spelling of the service's own name (`guardrail-mcp-server` vs `mcp-server` vs `Guardrail Hub`). |
| `RISK_ORDER`, `_RISK_RANK`, `_SEVERITY_ADVICE` | **Domain vocabulary** (security severity) | `suite/findings.py` | **Move** with the severity model (§6-Critical-1). `_SEVERITY_ADVICE` is remediation guidance — genuine security domain knowledge, currently classified as a private constant in a suite helper. |
| `_SEVERITIES` (suite, 4 members) | Domain vocabulary — **and inconsistent** | `suite/aggregator.py` | **Move + reconcile**: 4 members (no `critical`) vs `ScanFindings`'s 5 vs Slack's 5. |
| `_SARIF_LEVEL` | **Protocol constant** (SARIF spec mapping) | `suite/reporter.py` | ✅ Stay with the SARIF renderer — correctly a protocol-adjacent constant. |
| `_TERMINAL` | Local domain constant | `suite/orchestrator.py` | ✅ Stay. |
| `_DEFAULT_OPERATION_TYPE` | Migration/compat constant | `execution/registry.py` | ✅ Stay — correctly documented as legacy-row handling. |
| `_PLACEHOLDER` (regex) | Local protocol constant | `scenario/context.py` | ✅ Stay. |
| `_HEALTH_SUMMARY_INTERVAL_SECONDS` | Configuration | `execution/dispatcher.py` (class const) | Minor: every *other* dispatcher interval is injected from `Settings`; this one is hardcoded. Inconsistent configuration ownership. |
| `BatchType` (constants/) vs `ZapOperationType` (execution/) | **Two overlapping taxonomies** | `constants/batch.py`, `execution/operation_type.py` | See §6-High-2. `api_scan` appears as a value in both, meaning the same string is simultaneously a "batch type" and an "operation type". |

---

## 5. Package Semantic Report

Are packages organized by **business capability**, **responsibility**, **technical construct**, or **Python feature**?

| Package | Organized by | Verdict |
|---|---|---|
| `services/notification/` | Business capability (root) + **technical construct** (subpackages) | ⚠️ **Mixed, and this is my prior pass's doing.** `models/`, `rendering/`, `policy/`, `dispatch/`, `subscribers/` — of these, `rendering/`, `policy/`, and `dispatch/` name *responsibilities* (good); **`models/` names a Python construct** (a dataclass container), which the governance Standard's own Rule 3 warns against in spirit. `models/` is `dataclasses/` with a friendlier name. It communicates "these are data" rather than "these are the operation-progress domain." Flagged as instructed. |
| `services/operations/` | Business capability | ✅ Clear. |
| `services/platform/` | Business capability | ✅ Clear. |
| `services/public/` | **Audience/routing concern**, not capability | ⚠️ `public` means "reachable without MCP" — an HTTP exposure fact, not a domain. It bundles `HealthService` (infrastructure readiness) with `HistoryService` (operation read model) — two unrelated capabilities co-located by *who calls them*. A new engineer asking "where does operation history live?" would not look in `public/`. |
| `services/evaluations/` | Business capability — **but thin and ambiguous** | ⚠️ One class whose relationship to `operations/` is unclear (§6-Medium-1). |
| `services/tools/owasp_zap/` | Technical construct (vendor) | ✅ Correct and deliberate — matches the layering standard's `tools/<tool>/` rule; a vendor boundary is a legitimate architectural seam. |
| `execution/`, `scenario/`, `suite/` | Responsibility / capability | ✅ Best-named packages in the tree. `execution/` says what it does; `suite/` names a capability. |
| `execution/handlers/` | Responsibility | ✅ Fine. |

**Net:** the ZAP subtree communicates architectural intent better than the top-level service packages do. `public/` and `models/` are the two names that describe mechanism rather than meaning.

---

## 6. Architecture Risks

### 🔴 CRITICAL-1 — The severity model is defined five times, inconsistently
`ScanFindings` (5 buckets, notification), `suite/aggregator._SEVERITIES` (**4** buckets — no `critical`), `suite/findings.RISK_ORDER` (4, capitalized: "High"/"Medium"), `helpers/owasp_zap_helpers` (5, with `critical` hardcoded to 0 and a comment admitting it), and `SlackNotificationChannel._SEVERITIES` (5, with emoji). The Slack adapter **regex-parses** the rendered severity line to rebuild counts it could have received as data.

Severity is *the* core concept of a DevSecOps product. It has no owner, no single definition, and already disagrees with itself on cardinality and capitalization. Adding a scanner that reports `critical` findings requires correctly editing four unrelated files; missing one silently drops or miscounts findings — and a miscounted vulnerability report in a security product is a **Guardrail G3 exposure** ("never fabricate a security result"), not merely tech debt.
**Why prior passes missed it:** every definition is in a "correct" folder. Only a responsibility lens sees that five files own one concept.

### 🔴 CRITICAL-2 — Presentation flows through a text-serialization round-trip
The renderer produces a plain-text card; `SlackNotificationChannel._build_blocks` then **parses that text back into structured data** with regexes (`_field`, `_parse_findings`) — including the string-sniffing heuristic `if "get-result" in message and "Operation ID:" in message` to decide which layout to build. Structured data (`OperationProgress`) → flat text → regex → structured blocks.

Any renderer wording change silently breaks Slack formatting, with no type error and no failing test. The adapter is guessing at the domain model it was never given. **This is the most fragile coupling in the codebase**, and it is invisible to folder review because both files are exactly where they belong. The port (`NotificationChannel.send(destination, message: str)`) is the root cause: it forces a lossy `str` boundary. A capability-aware channel should receive the *model* and render natively.

### 🟠 HIGH-1 — Event contract owned by an implementation file
`EVENT_OPERATION_*` are consumed by the notification context and the composition root but defined inside `operations/operation_service.py`. Any context wanting to subscribe imports another context's service module. The payload is also an untyped `dict[str, Any]` — `_snapshot` reads `payload.get("findings")`, `"stage"`, `"worker_id"`, `"report_link"` with no schema anywhere. **The event bus is the main inter-context seam and it is entirely unvalidated.** With multiple teams, publisher/subscriber payload drift becomes a runtime-only failure.

### 🟠 HIGH-2 — Three overlapping status/type taxonomies
`OperationStatus` (in *ZAP tool schemas*, though it is a generic operation concept), `LifecyclePhase` (notification copy), and `BatchType` vs `ZapOperationType` (`api_scan` is a member of both). Four enums, two concepts. A new engineer cannot tell which to use, and the mapping between them lives in `bootstrap.py`. Concept ownership is unassigned.

### 🟠 HIGH-3 — Inconsistent dependency-injection discipline
`HistoryService.__init__` calls `get_operation_dao()` (Service Locator); `ZapApiScanService` is a `__new__` singleton with a module-level thread pool; `OperationService`/`NotificationService`/`SuiteOrchestrator` are cleanly constructor-injected. Three different lifetime/wiring models in one layer. The singletons are also **untestable in isolation** — `ZapApiScanService()` returns process-wide shared state, which is why the tests need `test_api_scanner_singleton.py` to pin the behavior.

### 🟡 MEDIUM-1 — `evaluations/` duplicates the operations lifecycle
`EvaluationService.run_api_scan` does create→start→run→complete synchronously; the queued path does the same asynchronously. Two code paths, one business meaning, no documented rule for which to use. It is wired in `bootstrap.py` but reachable from no router — effectively dead-but-maintained.

### 🟡 MEDIUM-2 — `ZapScanRunner` is Infrastructure in the application layer
Drives `ZapClient` directly; its responsibility is Gateway. My third pass moved it *into* the ZAP package (right call on tool-coupling) but did not question its *layer*.

### 🟡 MEDIUM-3 — `EventNotificationSubscriber` may be redundant
Both it and `OperationNotifier` subscribe to operation events; the subscriber's template path (`"Operation {id} created."`) is the primitive predecessor of the notifier's card path. `build_notification_flow_from_settings` wires the subscriber, `build_operation_notification_flow` wires the notifier — two flows, overlapping purpose. Which is canonical is undocumented.

### 🟡 MEDIUM-4 — `notification/models/` is a construct-named package
See §5. Rename toward intent (e.g. `progress/`) or absorb into a domain location.

### 🟢 LOW-1 — Two operation-ID formats in production (§2.4).
### 🟢 LOW-2 — Service identity spelled three ways (§4).
### 🟢 LOW-3 — `_SERVER` and `SLACK_CHANNEL_NAME` each defined twice (§4).
### 🟢 LOW-4 — `EndpointOutcome` mutable without cause; `_HEALTH_SUMMARY_INTERVAL_SECONDS` hardcoded while peers are injected.

---

## 7. Enterprise Readiness

**Would this scale to hundreds of engineers? Partially — the *structure* would; the *concept ownership* would not.**

What genuinely scales: the hexagonal ports (`NotificationChannel`, `EventPublisher`) are excellent — adding Discord is "implement the port," and that is real leverage. The generic execution registry means a new ZAP tool is one line in `bootstrap.py`. The package façades now give teams a stable import surface. The AIOS governance layer (ADR-0006, the new Standard) is genuinely unusual and will prevent structural decay.

**Predicted maintenance hotspots, in order:**

1. **`api_scanner.py`** — 442 LOC, three responsibilities, a singleton, a module-level thread pool, two near-duplicate workers. Every ZAP behavior change lands here. It will be the most-edited, most-conflicted file in the repository, and its singleton makes parallel test execution unsafe.
2. **The severity model (CRITICAL-1)** — every new scanner integration touches four files. This scales *linearly with tool count* in the worst way: a product whose entire value is accurate severity reporting has no single definition of severity.
3. **`operation_notifier.py`** — 461 LOC, threading, three responsibilities. Notification UX changes and progress-semantics changes are different teams editing the same file with a lock in it.
4. **The renderer↔Slack text contract (CRITICAL-2)** — cross-team breakage with no compile-time or test-time signal. A UX team changing a label breaks a platform team's integration silently.

**Boundaries that would confuse a new engineer:**

- **`services/public/`** — "public" describes HTTP exposure, not capability. Nobody looks there for operation history.
- **`evaluations/` vs `operations/`** — two lifecycle paths, no stated rule for which to use. A new engineer will pick by coin flip, and both will grow.
- **`OperationStatus` living in `schemas/tools/owasp_zap/`** — a *generic* operation concept inside a *vendor tool's* schema package. Everything imports it from there, including the notification layer's duplicate-avoidance comment. This is the single most misleading location in the codebase.
- **Where does a domain rule go?** There is no answer. `findings.py` (severity rules) is in `suite/`; `ScenarioContext` (workflow rules) is in `scenario/`; `ScanFindings` is in `notification/models/`. Three domain concepts, three unrelated homes, chosen by first consumer. **A new engineer adding a fourth will invent a fourth location.** That is the definition of architectural drift, and it is happening now.

**Challenging my own prior conclusions, explicitly:**

- Pass 3 rejected unifying the card renderers as "intentional divergence." **Responsibility-wise that was wrong** — three components (renderer, `PlatformReporter._render`, Slack `_build_blocks`) own presentation, and CRITICAL-2 shows the cost is not cosmetic.
- Pass 3 called `notification/models/` a clean responsibility subpackage. **It is a Python-construct name**, flagged by the very rule I later wrote into the Standard.
- Passes 1–3 accepted the no-new-top-level-layer constraint. It was right *then* — it prevented premature abstraction. **It is now the binding constraint on correctness**: four domain concepts are homeless, and the "first consumer wins" placement rule is actively producing drift. The next architectural decision this repo should make is whether `domain/` has earned its existence via ADR. My honest read: **it has** — not as a folder for tidiness, but because severity, operation status, and scan findings are concepts multiple contexts must share, and today they are copied instead.

**Recommended sequencing** (no changes made; for a future decision):
1. Fix CRITICAL-1 (single severity model) — highest value, blocks the most future work.
2. Fix CRITICAL-2 (pass the model to capability-aware channels, not text).
3. Type the event payload (HIGH-1).
4. Split `api_scanner.py`'s submit/execute responsibilities (hotspot #1).
5. Reconcile the status taxonomies (HIGH-2) — likely the ADR that also settles `domain/`.
