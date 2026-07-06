# RFC-0002 — Activate Core Guardrails

Status: **Merged**
Date: 2026-07-06
Proposer: Loi Phan
Security sign-off: Loi Phan (security authority)
Type: Guardrail change — full RFC + security sign-off required ([guardrails/README.md](../../guardrails/README.md#lifecycle)).

---

## Proposal

**What changes.** Transition `guardrails/core` (rules G1–G5, authored in M3) from `Review` to `Active`, and bump its version `0.2.0 → 1.0.0` (first Active release).

**Why.** The five core guardrails — no exposed secrets (G1), don't weaken the product's security controls (G2), don't fabricate security results (G3), no unauthorized destructive/outward actions (G4), never present inference as fact (G5) — are the always-resident Tier G policy the whole Product Lane depends on. They were authored and Review-ready in M3; activating them makes Tier G a live, enforced policy rather than a Draft.

## Architecture Review

- **Boundaries intact?** Yes — no structural change; a status/version transition of an existing unit.
- **Tier G still bounded?** Yes — 5 concise rules in one file, well under the "small by contract" ceiling.
- Verdict: **preserved.**

## Conditional Module Reviews

None triggered — no module's category set or contract fields change.

## Acceptance Criteria Check (per [guardrails/README.md](../../guardrails/README.md#acceptance-criteria), introduced by RFC-0001)

| Criterion | Result |
|---|---|
| A1 — security sign-off recorded | ✓ (this RFC, signed off above) |
| A2 — each rule has checkpoint(s), block/escalate, concrete example | ✓ (G1–G5 all do) |
| A3 — merged through a full RFC | ✓ (this RFC) |
| A4 — `aios validate` passes | ✓ |

## Evaluation

Run against the `evaluation/benchmarks/fix-bug` baseline established earlier in this milestone: activating a Tier G guardrail does not change any Product-Lane address list (guardrails/core.md was already loaded at Tier G regardless of status), so the benchmark's Expected Context is unchanged — **no regression**.

## Decision

**Merged.** Architecture preserved, Acceptance Criteria met, security sign-off recorded, no regression. Applied: `guardrails/core.md` → `status: Active`, `version: 1.0.0`.
