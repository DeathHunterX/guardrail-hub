# JMeter Engine — Architecture

Status: **Phase 3 complete (2026-07-29) — load tests execute end to end.** Next milestone: Phase 4 — Result Parsing & Analysis.

| Phase | State |
|---|---|
| Design + governance | Done — ADR-0010, ADR-0011 Accepted |
| Phase 1 — Skeleton | Done — queue lane, result contract, submission, component interfaces |
| Phase 2 — Execution infrastructure | Done — dispatcher loops, worker registry/heartbeat, scheduler, pool, worker transport, router registration |
| Phase 3 — Runtime orchestration | Done — plan generation + validation, worker agent, JMeter subprocess, artifact persistence, Docker image |
| Phase 4 — Parsing & analysis | Not started — JTL parsing, metric extraction, `analyze_jmeter_result` |

A submitted load test now runs to completion and persists its artifacts. What it does **not** yet carry is `summary` and `metrics` — every field in both comes from parsing the JTL, which is Phase 4. Until then a completed result links to the report, the raw JTL, the executed plan and the engine log, and records who ran it, when, and under what load profile.

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

Input to this work: [jmeter-engine-architecture-review.md](../../jmeter-engine-architecture-review.md) (validation verdict: *READY WITH MINOR CHANGES*).

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
