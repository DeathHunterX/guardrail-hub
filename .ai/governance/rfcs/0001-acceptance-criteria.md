# RFC-0001 — Introduce Acceptance Criteria

Status: **Merged**
Date: 2026-07-06
Proposer: Loi Phan
Type: Constitution-tier (lifecycle + governance) — full RFC required.

> The first RFC run through the [Governance RFC process](../README.md#rfc-process). It both delivers a requested governance layer *and* is M4's dogfood of the RFC flow on a real, substantive change.

---

## Proposal

**What changes.** Introduce **Acceptance** as a distinct governance gate between `Approved` and `Active`, separating three concerns that were previously conflated at the Review→Active transition:

| Layer | Question | Owner |
|---|---|---|
| **Validation** | Is it *correct*? (schema, id=path, links) | Automation (`aios`) |
| **Review** | Is it *good*? (12-dimension quality checklist) | Review + module Owner |
| **Acceptance** | Is it *ready to be runtime*? (per-type readiness criteria) | module Owner |

An artifact that has passed Review (`Approved`) must additionally meet its unit-type's **Acceptance Criteria** before transitioning to `Active`.

**Concrete edits (blast radius):**
1. `foundation/architecture.md` — the per-unit lifecycle diagram's `Approved → Active` transition becomes guarded: `Approved → Active: Acceptance Criteria met`. (Modeled as a transition guard, not a new state — parallel to the existing `Deprecated → Archived: N Releases elapsed` guard — to avoid state-machine bloat.)
2. `governance/README.md` — a new **Acceptance** section defining the gate and the Validation/Review/Acceptance separation.
3. `standards/README.md`, `agents/README.md`, `guardrails/README.md` — each gains an **Acceptance Criteria** subsection listing that type's readiness checks. Other module types add theirs when they author their first real unit (additive, no RFC each).

**Why.** "Passed quality review" and "ready to be depended on at runtime" are different guarantees. A Standard can be well-written (Review-approved) yet not ready to enforce (its `applies_to` globs match nothing real, or a dependency isn't Active). Conflating them let not-ready artifacts reach `Active`. Acceptance makes readiness an explicit, per-type, checkable gate.

## Architecture Review

Checked against [foundation/architecture.md](../../foundation/architecture.md) module contracts and dependency graph:
- **Module boundaries intact?** Yes — Acceptance is additive; it introduces no new module, changes no module's ownership or dependency direction.
- **Tier 0 budget unaffected?** Yes — Acceptance Criteria live in module contracts (Meta-lane docs), never loaded on the Product Lane.
- **Consistent with existing gates?** Yes — it composes with, and does not weaken, Validation or Review (governance's "no third quality gate that bypasses the two" is respected: Acceptance is a *readiness* gate, orthogonal to quality, and cannot waive a Review Blocking finding).
- Verdict: **boundaries preserved.**

## Conditional Module Reviews

Touches the *lifecycle* (all modules) and three module *contracts* (adding an Acceptance section), but does **not** change any module's category set or existing contract fields. Knowledge/Template/Workflow structural reviews are therefore **not triggered**. The three touched contracts (Standards/Agents/Guardrails) gain an additive section only.

## Evaluation

The RFC process calls for a regression-benchmark run before merge. **No benchmark baseline exists at this RFC's time** — the first benchmark (`evaluation/benchmarks/fix-bug`) is established later in this same milestone (M4). The regression check is therefore vacuously satisfied and recorded as a known first-RFC condition; every subsequent RFC runs against the `fix-bug` baseline. This gap is inherent to bootstrapping the governance loop and is not a defect.

## Decision

**Merged.** Boundaries preserved, no regressions possible (no baseline yet), the change is additive and human-authorized. Applied below.

## Applied Changes

- `foundation/architecture.md`: lifecycle `Approved → Active` guarded by "Acceptance Criteria met."
- `governance/README.md`: Acceptance section added.
- `standards/README.md`, `agents/README.md`, `guardrails/README.md`: per-type Acceptance Criteria added.

Verified post-merge by `aios check` (see [milestones/M4](../../milestones/M4-governance-loop-activation.md)).
