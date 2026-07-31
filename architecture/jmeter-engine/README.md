# JMeter Engine — Architecture

Status: **Phase 4 complete (2026-07-29) — the JMeter engine is functionally complete.** Both MCP tools are implemented end to end.

| Phase | State |
|---|---|
| Design + governance | Done — ADR-0010, ADR-0011 Accepted |
| Phase 1 — Skeleton | Done — queue lane, result contract, submission, component interfaces |
| Phase 2 — Execution infrastructure | Done — dispatcher loops, worker registry/heartbeat, scheduler, pool, worker transport, router registration |
| Phase 3 — Runtime execution pipeline | Done — plan generation + validation, worker agent, JMeter subprocess, artifact collection, JTL parsing, result persistence, Docker image |
| Phase 4 — Result analysis | Done — `analyze_jmeter_result`, reading only the persisted result |

A submitted load test runs to completion, and its result carries `summary` and `metrics` parsed from the JTL — sample counts, error rate, latency distribution, throughput and the per-label breakdown — alongside links to the HTML dashboard, the raw JTL, the executed plan and the engine log. `analyze_jmeter_result` then reads that stored record and describes it in plain language.

Both derived sections remain **optional in the contract**, for one reachable case: a run whose results file cannot be read back. That is a degraded result, not a failed test — the target really was loaded — so the run is completed with the sections absent rather than zero-filled, and the analyzer reports that state as its own distinct outcome. See [result-contract.md](result-contract.md) §1.

**Where the engine stops, deliberately.** It reports measurements and the arithmetic relationships between them. It states no verdict: no pass/fail, no SLA, no thresholds, no recommendations, no comparison against previous runs. That is `Policy` and trend analysis, both deferred with their reasoning on the record ([ADR-0008](../../.ai/decisions/0008-domain-ubiquitous-language.md) §6, [result-contract.md](result-contract.md) §4) — neither trigger has fired.

**Deployment note.** The worker writes its artifacts into the same `./public` tree the server serves from (a shared volume in `docker-compose.yml`), so there is no upload step — and, today, workers must run on the same host as the server. Replacing that with an artifact upload is a deployment change, not a contract change.

JMeter is an **independent execution engine** in Guardrail Hub: JMeter-specific components throughout, reusing ZAP's *patterns* but none of its classes. There is no "Performance" abstraction and no engine-agnostic layer — the earlier generic Performance branch was reverted in full (`01c4d00`, `1bf9e3d`, `762e1c5`) and is not a reference for anything here.

This folder holds the architectural decisions that had to be settled **before** implementation. It follows [`architecture/README.md`](../README.md)'s convention (one subfolder per subsystem, linking out to `.ai/` rather than restating it).

---

## 1. Documents

| Document | Settles |
|---|---|
| [queue-isolation.md](queue-isolation.md) | How JMeter and ZAP operations coexist in the shared Operations table |
| [result-contract.md](result-contract.md) | The canonical payload persisted to `operation.result`, consumed by `analyze_jmeter_result` |
| [runtime-responsibility.md](runtime-responsibility.md) | Runtime vs. Worker vs. Parser vs. Analyzer ownership; package layout; naming |
| [cleanup.md](cleanup.md) | Revert remnants removed, and what is recommended but not executed |
| [governance-report.md](governance-report.md) | ADR review, ratification, cross-reference validation, readiness checklist |
| [architecture-review.md](architecture-review.md) | The pre-implementation validation of the plan against the repo as it stood — the conflicts (**C1–C4**) and adjustments (**A1–A8**) every document above resolves |

`architecture-review.md` is the **input** to this work rather than an output of it: verdict *READY WITH MINOR CHANGES*, dated 2026-07-28, written against `762e1c5`. It is a point-in-time record and is not updated as the engine evolves — read it for *why the design was changed before it was built*, not for the current state.

## 2. The decisions in one page

**Queue.** Each dispatcher declares the `batch_type` lane it owns; `get_queued_operations(batch_types)` takes a required lane argument. ZAP passes the pre-existing `ALL_SCAN_TYPES`, JMeter passes a new `ALL_JMETER_TYPES` (`jmeter_test`). Additive, no migration, ZAP behavior unchanged. Without it, the ZAP dispatcher marks every JMeter row `FAILED` within one poll tick — so this lands **before** anything can create a JMeter operation. → [ADR-0011](../../.ai/decisions/0011-tool-scoped-queue-consumption.md)

**Result.** `JMeterTestResult` — a tool-specific wire format in `schemas/tools/jmeter/`, with four sections: `summary`, `metrics`, `artifacts`, `metadata`. No lifecycle status inside it (the `Operation` owns that), no SLA verdict (that is `Policy`, whose trigger has not fired), no `Finding`s, and **no cross-tool `Result` root** — ADR-0008 §6 named JMeter as the trigger to decide that, and the decision is *defer, with new triggers stated*. → [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md)

**Boundaries.** Dispatcher schedules; `JMeterRuntime` orchestrates Generate → Validate → Execute → Parse → Persist and is the sole caller of `OperationService`; Worker owns the JMeter subprocess and nothing else; Parser turns a JTL into numbers and makes no judgment; Analyzer reads only `operation.result` and never re-parses artifacts. The `runtime.py` ambiguity is resolved by layer: `integrations/jmeter/runtime.py` = process singletons (mirrors ZAP), `services/tools/jmeter/execution/runtime.py` = the per-operation orchestrator.

**Also settled here:** `run_jmeter` is asynchronous (`{operation_id, status, message}`), like every ZAP MCP tool. Target authorization (Guardrail G4) is enforced in Runtime's Validate step, before generation output is executed. Artifacts follow the existing `ReportPaths` / `/public/**` mechanism — no artifact-store component is introduced.

## 3. Phase 1 preconditions

1. ~~Ratify ADR-0010 and ADR-0011.~~ **Done — both Accepted 2026-07-29** ([governance-report.md](governance-report.md)).
2. ~~Land the queue lane change (queue-isolation §2) first, with its lane test.~~ **Done 2026-07-29** — `get_queued_operations(batch_types)` is lane-filtered and required; `tests/dao/test_queue_lanes.py` guards both properties.
3. ~~Build the skeleton per runtime-responsibility §2.~~ **Done 2026-07-29** — Phase 1 complete. Submission and the result contract are implemented; runtime, worker, dispatcher, parser and analyzer are interfaces with their boundaries fixed. The MCP router exists but is **not registered** in `endpoints.py`: registration belongs with the phase that lands the dispatcher, so the tools are never callable before something polls the lane.

## 4. Open item — for the backend owner, not for implementation

[ADR-0009](../../.ai/decisions/0009-execution-capability.md) is still **Proposed** and its H1–H4 contract hygiene is unimplemented. It is **not a JMeter blocker** — JMeter reuses no part of the ZAP execution contract, which is precisely why. But JMeter landing *is* ADR-0009's own stated revisit trigger, so two things are owed:

- Ratify (or reject) ADR-0009 as it stands. Ratification is a human decision and is deliberately not performed by this work.
- After JMeter is implemented and observed, open the follow-up Decision on whether any cross-tool execution extraction has earned its existence — with two real substrates to compare instead of one. Do not pre-empt it.
