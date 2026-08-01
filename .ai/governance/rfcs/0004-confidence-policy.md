# RFC-0004 — Confidence-Based Decision Making

Status: **Proposed**
Date: 2026-08-01
Proposer: Loi Phan
Type: Governance framework extension — additive capability, no Kernel/Router/Guardrails change.
Prerequisite: [RFC-0003](0003-change-governance.md) (this extends the Authority Check gate that RFC proposes).

---

## Proposal

**What changes.** Add [governance/confidence-policy](../confidence-policy.md) as a new unit in the Governance module: four confidence bands (High → proceed; Medium → proceed with declared assumptions; Low → ask, once and batched; Very Low → recommend planning before implementation), five factors that move the band, and the rule that the **weakest factor sets it rather than an average**. Integrates at three points — Planning (the band is declared with the plan), the Authority Check (a second, independent pass), and Review (input to existing dimensions). One subsection is added to [governance/README.md](../README.md); one cross-reference to `standards/core/decision-policy` D4.

**Why.** The Kernel already decides clarification-vs-assumption in binary — safety-relevant gaps escalate, everything else may proceed if labelled ([Kernel](../../kernel/README.md#when-to-stop-loading-context), [Recovery](../../kernel/recovery/README.md), [G5](../../guardrails/core.md)). That binary is correct and stays authoritative, but it says nothing about *payload*: what a labelled assumption should contain, or what an escalation should carry so a human can decide in one pass. The gap shows up as both failure modes at once — Agents asking what the repository already answers, and Agents shipping fluent implementations of the wrong thing. Naming the bands and their payloads is the smallest addition that addresses both.

**Blast radius.**

| Surface | Effect |
|---|---|
| Kernel, Recovery, Guardrails, Router, Foundation | **None.** No file touched. The bands sit *inside* the existing binary; Recovery's four outcomes stay exhaustive — Very Low is an escalation with a different payload, not a fifth branch. |
| [Review framework](../../review/README.md) | **None to the checklist.** Confidence is consumed by the existing 12 dimensions; no thirteenth is added, so the RFC gate that governs Review's own bar is not engaged. Only an *undeclared* assumption reaches Blocking, and it does so through G5, which was already Blocking. |
| [change-authority](../change-authority.md) | Extended by reference: confidence is a second pass over the same Authority Check. No new gate, no new state, no change to the classification→authority table. |
| `standards/core/decision-policy` | Patch-level cross-reference at D4 only; D1–D5 rule text unchanged. |
| Product-Lane context budget | **Unchanged.** Meta/Constitution-tier, reached when an Agent classifies at L3+ or declares a band — not added to any always-loaded set. |

**Why an RFC at all.** Not strictly required (an additive unit in an approved module needs only [Impact Analysis](../README.md#impact-analysis)). Filed because it modifies the inputs to the Authority Check gate proposed in RFC-0003, and because a policy governing when an Agent may act without asking is, like authority itself, poorly suited to self-ratification.

## Architecture Review

- **Boundaries intact?** Yes. Governance gains one unit; dependencies (`confidence-policy → change-authority`, `→ decision-policy`) follow the existing direction — Governance consumes Standards, never the reverse.
- **Duplication check?** The Kernel's binary is referenced and left authoritative rather than restated; G5 supplies the labelling obligation and this unit supplies only the content; architectural impact is read from `decision-policy` D1, not redefined.
- **Does it add a gate?** No. One input to an existing gate, one input to existing Review dimensions.
- **Rigid thresholds?** None. Bands are recognised by description; the document states explicitly that a numeric scale would launder judgment into false precision and would be gamed once a band became a gate.
- Verdict: **preserved.**

## Conditional Module Reviews

| Review | Triggered? | Reason |
|---|---|---|
| Knowledge Review | No | No category structure or granularity rule changes. |
| Template Review | No | No Customization Point contract changes. |
| Workflow Review | No | No state, order, or Review Point changes. |

## Evaluation

Against the [`fix-bug` benchmark](../../evaluation/benchmarks/fix-bug.md): an ordinary bugfix classifies L1 and reads High or Medium, whose response is *proceed* — the declaration is one sentence in the plan and adds no address to the Expected Context. **No regression expected**; requires a re-run before merge to confirm rather than assert.

The behavioural claim this RFC makes — fewer unnecessary clarifications *and* fewer over-confident changes — is not measurable at the current benchmark's granularity. The honest position is that it is unmeasured, and the [calibration path](../confidence-policy.md#review) through [Memory](../../memory/README.md) is the mechanism intended to produce evidence for or against it over real sessions. Stated here so a later reviewer does not read the claim as demonstrated.

## Acceptance Criteria Check

| Criterion | Result |
|---|---|
| `aios validate` passes | ✓ |
| `aios links` resolves every cross-reference | ✓ |
| `depends_on` targets resolve and are at least `Approved` | ⏳ **Open** — `governance/change-authority` and `standards/core/decision-policy` are both at `Review`; this unit cannot reach `Active` before they do. |
| Owner recorded | ⏳ **Open** — same `architecture-owner` role question carried by RFC-0003; one decision resolves it for all three units. |

## Decision

**Pending**, and dependent on RFC-0003 — the Authority Check this extends does not exist until that merges. Returning 0003 returns this with it.

## Applied Changes

Recorded on merge. Authored under this proposal, all at `status: Review` pending it:

- `governance/confidence-policy.md` — new unit, v1.0.0.
- `governance/README.md` — Confidence-Based Decision Making subsection.
- `governance/rfcs/README.md` — index row for this RFC.
- `standards/core/decision-policy.md` — D4 cross-reference to the band declaration.
