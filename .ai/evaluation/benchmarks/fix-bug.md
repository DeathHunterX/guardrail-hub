---
id: evaluation/benchmarks/fix-bug
title: Benchmark — Fix Bug
version: 1.0.0
status: Active
owner: evaluation-owner
category: benchmark
depends_on: [agents/backend/backend-agent]
validated_against: [agents/backend/backend-agent@1.0.0]
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
