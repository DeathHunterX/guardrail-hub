---
id: evaluation/benchmarks/fix-bug
title: Benchmark — Fix Bug
version: 1.0.3
status: Active
owner: evaluation-owner
category: benchmark
depends_on: [agents/backend/backend-agent]
validated_against: [agents/backend/backend-agent@1.3.0]
---

# Benchmark — Fix Bug

> The minimal-context benchmark: fixing a localized backend bug should resolve to the *fewest* addresses of any task type. Established and first run in Roadmap M4 ([Decision 0001](../../decisions/0001-aios-bootstrap-roadmap.md)); it is the regression baseline every subsequent RFC's Evaluation step runs against.

## Benchmark Contract

| Field | Value |
|---|---|
| **Objective** | Fix a localized bug in `mcp-server/` backend code by routing through the Product Lane and touching only the minimum necessary addresses. |
| **Expected Inputs** | Task: "Fix the report-path construction bug in `ZapApiScanService`." Starting repo state: current `main`. |
| **Expected Context** (answer key) | `guardrails/core.md` (Tier G) · `router/MANIFEST.md` (Tier 0) · `agents/backend/ROUTER.md` · `agents/backend/backend-agent.md` · the one relevant Standard (`standards/architecture/backend-layering` or `standards/operational/logging` if logging is touched) · the target source file. **Must NOT load** `foundation/`, full `kernel/`, `router/README.md`, `agents/README.md`. |
| **Expected Output** | A minimal code change within `mcp-server/**`, conforming to the enforced Standards, no scope creep. |
| **Success Criteria** | Correct routing to Backend Agent; fix stays within `mcp-server/**`; enforced Standards respected; context fetched ⊆ Expected Context. |
| **Failure Criteria** | Fetched more than Expected Context without justification (esp. any Constitution-tier doc); dispatched to the wrong Domain; violated a Standard or Guardrail. |
| **Scoring** | Accuracy + Completeness = pass/fail; Token Usage (fetched vs. Expected Context) and Reasoning Quality = efficiency/quality score. |

## Run Record — 2026-07-06 (v1.0.0)

**Result: PASS.** Routing resolved as: `mcp-server/CLAUDE.md → AGENTS.md (Product Lane) → guardrails/core.md → router/MANIFEST.md (Backend) → agents/backend/ROUTER.md → backend-agent → standards/operational/logging (+ backend-layering)`. Constitution-tier docs were **not** loaded — matching Expected Context exactly.

- **Accuracy / Completeness:** Pass — the lane reaches a Backend-scoped fix with the enforced Standards applied.
- **Token Usage:** at Expected Context (no over-fetch); this is the minimal-context path, as intended.
- **Reasoning Quality:** declared/inferred distinction and escalation rules honored (Guardrail G5).

This run is the baseline; future RFCs compare their Evaluation step against it (see [evaluation/README.md](../README.md#regression-testing)).

## Revalidation — 2026-07-20 (v1.0.1)

Backend Agent bumped 1.0.0 → 1.1.0 (additive: `standards/architecture/service-package-design` added to `standards_enforced`, per [Decision 0006](../../decisions/0006-service-package-design-standard.md)). Checked against this benchmark's contract: the routing path, Expected Context answer key, and success criteria are unchanged — a localized bug fix creates no new service files or packages, so the added Standard is not part of the minimal context and does not alter the baseline. Re-pinned `validated_against` to 1.1.0; no re-run required.

## Revalidation — 2026-07-20 (v1.0.2)

Backend Agent bumped 1.1.0 → 1.2.0 (additive: `standards/architecture/domain-layer` added to `standards_enforced`, per [Decision 0007](../../decisions/0007-domain-layer-justification.md) / [0008](../../decisions/0008-domain-ubiquitous-language.md)). Checked against the contract: the routing path and success criteria are unchanged, and the Expected Context answer key still resolves to "the one relevant Standard" — fixing a localized bug in `ZapApiScanService` neither defines a business concept nor touches `domain/`, so `domain-layer` stays out of the minimal context. The benchmark's *purpose* (proving minimal-context routing) is unaffected by a Domain task-subtype existing in the Router, because this scenario does not match that row. Re-pinned to 1.2.0; no re-run required.

> Coverage gap noted (not a regression): no benchmark exercises the Domain task subtype — a task that *should* load `domain-layer`. Worth adding a `add-business-concept` benchmark when the Evaluation module next gains units; recorded here so the gap is declared rather than silent.

## Revalidation — 2026-07-29 (v1.0.3)

Backend Agent bumped 1.2.0 → 1.3.0 (additive: `standards/architecture/runtime-boundary` added to `standards_enforced`, and `backend-layering` re-pinned to 1.2.0, per [Decision 0012](../../decisions/0012-runtime-boundary.md)). Checked against the contract: routing path, Expected Context answer key and success criteria are all unchanged. `ZapApiScanService` is a service in the MCP server, not an independently deployed process, so the new Router row (`app/runtime/`) does not match this scenario and `runtime-boundary` stays out of the minimal context. The `backend-layering` re-pin is likewise inert here: its carve-out removes `app/runtime/` from scope, and this task touches `services/`. Re-pinned to 1.3.0; no re-run required.

> The same coverage gap now applies one more time: no benchmark exercises the runtime-boundary task subtype either. The two gaps share a cause — Evaluation has one backend benchmark, and it is deliberately the *minimal-context* one — so the fix is one new benchmark per task subtype, not a change here. Declared, not silent.
