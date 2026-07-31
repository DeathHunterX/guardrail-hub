# JMeter Engine — Architecture Validation Report

Date: 2026-07-28 · Scope: review only (no code changed) · Reviewed against: repo HEAD (`762e1c5`) — working-tree diffs are line-ending churn only, content-identical to HEAD.

Evidence sources: `.ai/guardrails/core.md`, `.ai/router/MANIFEST.md`, `.ai/agents/backend/ROUTER.md`, Standards (backend-layering 1.1.0, service-package-design 1.0.0, backend-naming 1.0.0), ADR-0005/0007/0008/0009, `.ai/intelligence/{module-map,system-overview}.md`, and the full ZAP execution stack in `mcp-server/app/`.

---

## Architecture Summary

### What actually exists today (verified in code)

- **One built engine (ZAP).** Chain: MCP router (thin submit adapter, returns `operation_id`) → `QUEUED` row in the Operations table → `OwaspZapDispatcher` (queue-poll + heartbeat-sweep daemon threads, `services/tools/owasp_zap/execution/dispatcher.py`) → `OwaspZapPoolManager` + `OwaspZapWorkerRegistry` + `RoundRobinScheduler` (`integrations/owasp_zap/`) → self-registering, long-lived external ZAP workers → handler executes, `OperationService` persists lifecycle + result and publishes events → notification pipeline reacts.
- **The queue is the DB.** No in-memory queue; `QUEUED` rows survive restarts. Worker registry is deliberately in-memory (workers re-register/heartbeat).
- **ZAP's `runtime.py` is not an orchestrator.** It is a module of process-wide singletons (registry/scheduler/pool manager). The Generate→Validate→Execute→Parse→Persist role the plan calls "Runtime" lives, in ZAP, in handlers/services (`run_assigned_scan`, `sync_runner.py`).
- **"Analyze" precedent:** `HistoryService.get_result(operation_id)` returns the full `OperationRecord` including `result` and `batch_type` — exactly the read path `analyze_jmeter_result` needs.
- **Prior art:** a generic "Performance engine" (`services/performance/`, `integrations/jmeter/`, `schemas/performance/`) was merged and then fully reverted (`01c4d00`, `1bf9e3d`, `762e1c5`). Empty directories and stale `__pycache__` from that revert remain on disk.

### How the plan maps onto it

The plan is structurally sound and matches the codebase's own rules:

- **Tool-specific naming** (`JMeterDispatcher`, `JMeterWorker`, …) satisfies backend-naming R3/R4 (`<Tool><Role>`, tool-prefixed models) and is precisely what ADR-0009 recommends — it rejects a Performance abstraction and names JMeter as the future *second* execution substrate, to be generalized only after it exists.
- **Layout** must follow backend-layering R3 exactly: `schemas/tools/jmeter/`, `services/tools/jmeter/`, `integrations/jmeter/`, `routers/mcp/jmeter_router.py`; never `domain/tools/jmeter/`.
- **Two MCP tools, generate/validate internal** matches service-package-design (internal subpackages, deliberately small public surface) and the ZAP pattern of thin submit adapters.
- **Long-lived worker / short-lived JMeter subprocess** is compatible with the registry's heartbeat model (heartbeats are meaningful because the *worker* is a daemon; only the JMeter process is ephemeral — the concern ADR-0009 §2.5 raised applies to ephemeral *workers*, not this design).

### The ten validation points

| # | Check | Verdict |
|---|---|---|
| 1 | No conflict with AIOS | ✅ Pass, given R3 layout above |
| 2 | No conflict with ADRs | ⚠️ Pass with actions — ADR-0008 §6 explicitly fires on JMeter (see C4); ADR-0009 is still **Proposed**, unratified |
| 3 | No conflict with ZAP infrastructure | ❌ One real conflict — shared queue poll (C1) |
| 4 | Dispatcher coexistence | ⚠️ Conditional on fixing C1 |
| 5 | Worker lifecycle vs. current registry | ✅ Compatible as a *pattern*; the registry class itself is ZAP-typed, so JMeter needs its own instance + registration endpoints (C2) |
| 6 | Pool design vs. scheduler | ✅ Round-robin pattern fits; `WorkerScheduler` is typed on `ZapWorkerInfo`, so copy, don't import (C2) |
| 7 | Runtime responsibility separation | ✅ Correct separation; naming/placement guidance in A4 |
| 8 | MCP tool boundaries | ✅ Appropriate — provided `run_jmeter` is asynchronous like every ZAP tool (A6) |
| 9 | Dependency direction | ✅ Plan respects `routers → services → integrations\|dao → domain`; Analyzer reading `operation.result` via DAO (not parsing artifacts) keeps it clean |
| 10 | No premature abstraction | ✅ Pass — the plan avoids it, and the reverted generic attempt is the codebase's own proof of why; delete its remnants (A5) |

---

## Risks

1. **Queue contention is silent data loss** (detail in C1). Without a fix, every JMeter operation submitted would be marked FAILED by the ZAP dispatcher within one poll tick — before the JMeter dispatcher ever sees it.
2. **Result vocabulary decision is contractually pending.** ADR-0008 §6 recorded, by name, that JMeter's arrival is the trigger to decide the `Result` root / `Metrics` kind. Implementing without recording that decision violates the AIOS's own governance trail (C4).
3. **"Runtime" means two different things.** In ZAP convention `runtime.py` = process singletons; in the plan, Runtime = the Generate→Validate→Execute→Parse→Persist orchestrator. A contributor following "same philosophy as ZAP" will be misled (A4).
4. **Stale revert remnants.** Empty `app/services/performance/{engine,redaction,runtime,worker}/`, `app/schemas/performance/`, and `app/integrations/jmeter/` dirs with orphaned `__pycache__` violate ADR-0005's no-empty-scaffold rule and can shadow/confuse imports of the new packages (A5).
5. **Guardrail G4 exposure is higher for a load engine than a scanner.** JMeter generates real traffic volume; an unauthorized or wrong target is a denial-of-service, not just an unwanted scan. Target authorization must be an explicit, validated input of `run_jmeter` (A8).
6. **`run_jmeter` return contract is ambiguous.** "Return operation summary and artifact links" reads synchronous; load tests are long-running and the whole dispatcher/pool design assumes async submit-and-poll (A6).
7. **ADR-0009 is unratified and its H1–H4 hygiene is unimplemented.** Not a JMeter blocker (JMeter does not reuse the ZAP execution contract), but JMeter landing *is* ADR-0009's stated revisit trigger — plan the post-implementation observation Decision now (A9).

---

## Conflicts

**C1 — Shared `QUEUED` poll: the ZAP dispatcher will destroy JMeter operations.** `get_queued_operations()` (both DAO backends) returns *every* `QUEUED` row with no tool filter. `OwaspZapDispatcher._dispatch_one` resolves each row's `metadata["operation_type"]` against the *ZAP* registry and, on an unresolvable type, calls `operation_service.fail(...)`. A JMeter row therefore gets FAILED immediately. Worse: a row *missing* `operation_type` is legacy-defaulted to `API_SCAN` and would be executed on a ZAP worker. Symmetrically, a naïve `JMeterDispatcher` polling the same unfiltered query would fight over ZAP rows. This is the only hard conflict, and it is fixable with a small additive change (A1).

**C2 — "May reuse: Worker Registry, Scheduler" is not literally possible.** `OwaspZapWorkerRegistry`, `WorkerScheduler`, `RoundRobinScheduler`, and `OwaspZapPoolManager` live in `integrations/owasp_zap/` and are typed on `ZapWorkerInfo`. Importing them from JMeter code would create a cross-tool dependency on the ZAP package — contrary to the plan's own "Must NOT reuse" spirit, backend-layering R3, and ADR-0009 (which counts them as ZAP infrastructure, "none of it currently shared"). Reuse is *pattern* reuse: JMeter-specific copies in `integrations/jmeter/`. That duplication is deliberate — it is the "Implement" step of Implement→Observe→Extract, and ADR-0009's revisit trigger is exactly where extraction gets decided later.

**C3 — "Artifact Store" does not exist.** There is only `constants/paths.py` (`ReportPaths`, ZAP-scoped directories) plus static serving under `/public/**`. JMeter can follow the same mechanism (`./public/report/jmeter/...`), but the plan should not name a component that isn't there.

**C4 — No canonical result schema exists for performance results.** The domain vocabulary (ADR-0008, `domain/findings/`) models security findings (`Finding`, `FindingSummary`, `Severity`); ADR-0008 §2/§6 explicitly determined JMeter *cannot* produce `Finding`s and reserved `Result` (root) + `Metrics` (latency, throughput, SLA verdict) as future concepts triggered by "First non-security tool (**JMeter**)". "Persist canonical result" is therefore currently unsatisfiable as written — the canonical shape must first be decided (A3).

---

## Suggested Adjustments

**A1 (required — fixes C1).** Add a tool-scoped queue read — e.g. `get_queued_operations(batch_types: Collection[str])` or a `batch_type` filter parameter — as an additive DAO change; each dispatcher polls only its own `batch_type`s. Add JMeter members to `BatchType` (e.g. `JMETER_TEST`). `analyze_jmeter_result`'s "verify operation belongs to JMeter" check falls out of the same field (`record.batch_type`).

**A2.** Reword the plan's Shared Infrastructure list. Actually shared and reusable as-is: DAO / Operations table, `OperationService` + lifecycle events, notification pipeline, `domain.lifecycle.OperationPhase`, `MCPLogger`, config pattern, history endpoints, `/public` static serving. Pattern-only (build JMeter-specific copies): worker registry, scheduler, pool manager, dispatcher, worker registration/heartbeat router.

**A3 (required — fixes C4).** Record a short ADR before implementation choosing one of: (a) keep the JMeter result a tool-specific wire format in `schemas/tools/jmeter/` (`JMeterResult…`, per backend-naming R4) persisted into `operation.result`, deferring the `Result`/`Metrics` domain root — most consistent with the plan's no-premature-abstraction stance; or (b) introduce the `Result` root now. Either is defensible; ADR-0008 reserved this exact decision for this exact moment, so it must be written down, not defaulted.

**A4.** Resolve the "Runtime" naming: either (a) mirror ZAP — `integrations/jmeter/runtime.py` holds process singletons, and the orchestration pipeline (Generate→Validate→Execute→Parse→Persist) lives in the handler/service layer under `services/tools/jmeter/` like ZAP's `run_assigned_scan`; or (b) keep the name `JMeterRuntime` for the orchestrator but place it in `services/tools/jmeter/` and document the divergence. Orchestration is application logic and belongs in `services/`; only the subprocess/client adapter belongs in `integrations/jmeter/`.

**A5.** Delete the reverted-PR remnants (empty `services/performance/**`, `schemas/performance/`, contentless `integrations/jmeter/` + all stale `__pycache__`) before implementation — ADR-0005 no-empty-scaffold rule.

**A6.** Make `run_jmeter` asynchronous like every ZAP tool: return `{operation_id, status, message}`; the summary and artifact links come from `GET /api/history/get-result` (and from `analyze_jmeter_result`). If a synchronous mode is truly intended, the dispatcher/pool tier is unnecessary for it and the plan contradicts itself — pick one.

**A7.** JMeter worker registration/heartbeat endpoints must be JMeter-scoped (own router, own registry instance) so the two pools cannot cross-register; heartbeat/sweep intervals configurable independently (a load-generating worker under full load may heartbeat less promptly than an idle ZAP daemon).

**A8.** Enforce Guardrail G4 in `run_jmeter` validation: the target must be explicitly named by the caller, and JMX generation must never widen the target set beyond what was requested.

**A9.** Ratify ADR-0009 (still Proposed), and schedule its revisit trigger: once JMeter is implemented and observed, open the new Decision on whether any cross-tool execution extraction has earned its existence.

---

## Validation Result

**READY WITH MINOR CHANGES**

The plan is internally consistent with the AIOS, the standards, and ADR-0009's explicit direction — JMeter-specific everything, no Performance abstraction, extraction deferred until a second substrate is observable. Two items must be resolved as part of (not after) implementation: the tool-scoped queue read (A1 — without it the ZAP dispatcher destroys JMeter operations) and the result-schema ADR (A3 — ADR-0008 names JMeter as the trigger for that decision). The remaining adjustments are wording, placement, and cleanup. Nothing requires revising the architecture itself.
