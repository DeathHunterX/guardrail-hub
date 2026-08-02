# RFC-0005 — Improvement Discovery

Status: **Proposed**
Date: 2026-08-01
Proposer: Loi Phan
Type: Governance framework extension — additive capability, no Kernel/Router/Guardrails change.
Prerequisites: [RFC-0003](0003-change-governance.md) (Branch Contract, Scope Budget, the drift path this reuses), [RFC-0004](0004-confidence-policy.md) (the bands that shape a record).

---

## Proposal

**What changes.** Add [governance/improvement-discovery](../improvement-discovery.md) as a new unit, plus [`governance/discoveries/`](../discoveries/README.md) as an append-only record series following the `rfcs/` precedent. Introduces **Execution Commitment** (an approved plan is a commitment; a better solution discovered mid-flight does not retroactively change what was authorized), a lightweight **Scope Check** at the moment of discovery, five **stopping criteria**, and a record contract. Adds **P9** to [engineering-philosophy](../../knowledge/concept/engineering-philosophy.md) — *prefer disciplined execution over continuous optimization* — which supplies the value the capability then references rather than argues.

**Why.** [Scope Budget](../change-authority.md#scope-budget) already sets bundled incidental refactors to zero and [decision-policy](../../standards/core/decision-policy.md) already names the opportunistic refactor as an anti-pattern. Both told an Agent not to act on a discovery; neither said where the discovery should go. The result is three lossy exits — implemented anyway, forgotten, or written in a chat that ends — for observations made at the moment the codebase is understood best. This adds the fourth exit and closes the gap the two existing rules left open.

**Blast radius.**

| Surface | Effect |
|---|---|
| Kernel, Router, Guardrails, Foundation | **None.** No file touched. |
| [change-authority](../change-authority.md) | Reuses the existing `Implementation → Authority Check` drift path for stopping-criterion discoveries — **no new gate, no new state**. One Scope Budget cell gains a pointer to the release valve; the budget value (0) is unchanged. |
| [Review](../../review/README.md) | **Checklist untouched.** Discovery quality is read through the existing Knowledge Reuse and Maintainability dimensions; no thirteenth dimension, so Review's RFC gate is not engaged. Adds one *reading* instruction — an implementation is not incomplete for having declined a discovered improvement. |
| [engineering-philosophy](../../knowledge/concept/engineering-philosophy.md) | One value added (P9). Additive; would be a Minor bump if the unit were released — it is at `Review`, so the version is unchanged and the [changelog](../../knowledge/CHANGELOG.md) records it. It is always-loaded on the Product Lane, so the addition is 6 lines by design. |
| [Memory](../../memory/README.md) | Referenced for its lifecycle shape only. **No new Memory category** — that would be a Major change to Memory's contract and would require its own RFC. Discoveries are authored records with a full field contract; Memory entries are Kernel-captured and unschema'd. Adjacent, not the same thing. |
| Product-Lane context budget | Unchanged except P9's 6 lines. The capability itself is Meta/Constitution-tier, reached at Planning and at discovery. |

**Backlog risk, addressed structurally.** The brief's hardest constraint is that this must not become a task system. The defence is the absence of fields, not a statement of intent: a record carries no assignee, no priority, no effort estimate, no due date, and no `Open`/`Done` state. Its lifecycle is `Recorded → Promoted | Superseded | Declined`, mirroring Memory. A record left at `Recorded` is a fact that remains true, not a ticket going stale — which is what makes leaving it there free, and what stops the series growing a grooming ritual.

## Architecture Review

- **Boundaries intact?** Yes. Governance gains one unit and one record series; dependencies (`improvement-discovery → change-authority, confidence-policy, decision-policy`) follow the existing direction.
- **Duplication check?** Classification is read from `decision-policy` D1, authorization from `change-authority`, the record's claim strength from `confidence-policy`'s bands, the lifecycle shape from `Memory`, and the value from `engineering-philosophy` P9. This unit connects those five and defines only what none of them holds: Execution Commitment, the Scope Check, the stopping criteria, and the record contract.
- **Parallel planning system?** No. The Scope Check is one decision inside Implementation, not a workflow; no state is added to the [Workflow framework](../../workflows/README.md#workflow-state-machine); `discoveries/` has no queue semantics.
- **Two near-identical fields in the brief** — *suggested implementation level* and *related Decision Policy level* — are kept as **Classification** (how much the change moves, per D1) and **Suggested route** (how it would have to be authorized: task, ADR, RFC, or *leave it*), so both survive with non-overlapping meaning rather than one restating the other.
- Verdict: **preserved.**

## Conditional Module Reviews

| Review | Triggered? | Reason |
|---|---|---|
| Knowledge Review | **Yes, narrow** | P9 is added to a Knowledge unit. No category set, granularity rule, or contract field changes — the unit gains one value in its existing structure. |
| Template Review | No | No Customization Point contract changes. |
| Workflow Review | No | No state, order, or Review Point changes. |

## Evaluation

Against the [`fix-bug` benchmark](../../evaluation/benchmarks/fix-bug.md): a bugfix that discovers nothing is unaffected — the Scope Check does not run and no address is added. One that discovers something writes one file and continues, leaving the Expected Context unchanged. **No regression expected**; re-run required before merge to confirm rather than assert.

The mechanism's value depends on records being *read* at Planning, not merely written. That is unmeasured and will stay unmeasured until entries exist; if the series accumulates records that no plan ever consults, the honest conclusion is that this failed and should be deprecated, not that it needs a grooming process. Stated here so a later reviewer has the falsification condition in hand.

## Acceptance Criteria Check

| Criterion | Result |
|---|---|
| `aios validate` passes | ✓ |
| `aios links` resolves every cross-reference | ✓ |
| `depends_on` targets resolve and are at least `Approved` | ⏳ **Open** — all three are at `Review`. |
| Owner recorded | ⏳ **Open** — the same `architecture-owner` question carried by RFC-0003 and RFC-0004; one decision resolves it for all five units. |

## Decision

**Pending**, and dependent on RFC-0003 and RFC-0004 — the Branch Contract this records against and the bands that shape a record do not exist until those merge.

## Applied Changes

Recorded on merge. Authored under this proposal, all at `status: Review` pending it:

- `governance/improvement-discovery.md` — new unit, v1.0.0.
- `governance/discoveries/README.md` — record series home and index.
- `governance/README.md` — Improvement Discovery subsection.
- `governance/rfcs/README.md` — index row for this RFC.
- `knowledge/concept/engineering-philosophy.md` — P9.
- `governance/change-authority.md` — Scope Budget pointer to the release valve.
