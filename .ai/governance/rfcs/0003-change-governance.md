# RFC-0003 — Change Governance: Authority to Modify Architecture

Status: **Proposed**
Date: 2026-08-01
Proposer: Loi Phan
Type: Governance framework extension — additive capability, no Kernel/Router/Guardrails change.

---

## Proposal

**What changes.** Add [governance/change-authority](../change-authority.md) as a new addressable unit in the Governance module, introducing seven concepts: Repository Owner Authority, Architecture Change Classification (binding, not redefining, [decision-policy](../../standards/core/decision-policy.md) D1), Architecture Impact Analysis, Branch Contract, Scope Budget, Scope Drift Detection, and Escalation Policy — plus the Authority Check gate that consumes them. One section link is added to [governance/README.md](../README.md); one cross-reference is added to `standards/core/decision-policy`.

**Why.** The AIOS could already answer *is this change correct* (Standards) and, since `decision-policy`, *which correct option is preferred*. It could not answer *is this Agent authorized to make it*. An Agent's capability was therefore the effective limit on its authority — which is how a competent, standards-compliant architecture change ships without anyone having ratified it. The gap is not one of prompt constraints; it is a missing governance object. Encoding it as governance rather than as instruction means it survives a model change, a tool change, and a session boundary.

**Blast radius.**

| Surface | Effect |
|---|---|
| Kernel, Router, Guardrails, Foundation | **None.** No file touched, no Tier G/Tier 0 cost added. |
| Workflow framework | **None to the state machine.** The `Design` state is *specialised* into Impact Analysis → Authority Check. Order and state set are unchanged, so this is additive per [workflows/README.md](../../workflows/README.md#collaboration-reuse-evolution), not the breaking reorder that would require its own RFC. |
| Governance framework | Additive (Minor): a new unit + a section link. No existing contract field, category set, or gate changes. |
| `standards/core/decision-policy` | Patch-level cross-reference only; D1–D5 rule text unchanged. Classification is referenced, never restated. |
| Existing Impact Analysis | Untouched and explicitly disambiguated from Architecture Impact Analysis in the new unit. |
| Agents | No frontmatter change. Their existing `decision_authority` globs become the authority bound this capability reads; `aios validate` H2 (no overlapping authority) already enforces the partition it depends on. |

**Why an RFC at all.** Strictly, an additive unit in an approved module needs only [Impact Analysis](../README.md#impact-analysis), not a full RFC. This one is filed because the capability defines who may authorize repository-wide change — a claim about authority ought not be self-ratifying. It is also the smallest available demonstration of the rule it introduces: the change classifies as L4 (a new ratified governance contract), so it asks rather than assumes.

## Architecture Review

- **Boundaries intact?** Yes. Governance gains one unit; no module's contract, category set, or dependency direction changes. The dependency it adds (`governance/change-authority → standards/core/decision-policy`) follows the existing direction — governance consumes Standards, never the reverse.
- **Tier 0 budget still small?** Yes. This is Constitution/meta-tier, loaded on the Meta Lane and when an Agent classifies a change at L3+. `router/MANIFEST.md` and `guardrails/core.md` are unchanged, so no Product-Lane session pays for it.
- **Duplication check?** Classification (L1–L5) is referenced from `decision-policy`, not copied; unit-level Impact Analysis is disambiguated from Architecture Impact Analysis in a side-by-side table rather than merged or shadowed.
- Verdict: **preserved.**

## Conditional Module Reviews

| Review | Triggered? | Reason |
|---|---|---|
| Knowledge Review | No | No Knowledge category structure or granularity rule changes. |
| Template Review | No | No Customization Point contract changes. |
| Workflow Review | **Recommended, non-blocking** | The state machine is unchanged, so the structural trigger is not met. A Workflow Owner confirmation that "specialising `Design` into two named gates" is read as additive — the reading this RFC asserts — would close the only interpretive question in the proposal. |

## Evaluation

Against the [`fix-bug` benchmark](../../evaluation/benchmarks/fix-bug.md) baseline: an ordinary bugfix classifies L1, whose Branch Contract is two lines and whose Authority Check is satisfied by the Agent's existing `decision_authority`. The benchmark's Expected Context is unchanged — `change-authority` is not loaded for an L1/L2 Product-Lane task. **No regression expected.** Requires a benchmark re-run before merge to confirm rather than assert.

## Acceptance Criteria Check

| Criterion | Result |
|---|---|
| `aios validate` passes | ✓ |
| `aios links` resolves every cross-reference | ✓ |
| `depends_on` target (`standards/core/decision-policy`) resolves and is at least `Approved` | ⏳ **Open** — that unit is at `Review`; this one cannot reach `Active` before it does. |
| Owner recorded | ⏳ **Open** — `architecture-owner` is not yet a role held by a named person in this repository. |

## Decision

**Pending.** Two open items above are the Repository Owner's to resolve; both are role/status decisions, not authoring work.

## Applied Changes

Recorded on merge. Authored under this proposal, all at `status: Review` pending it:

- `governance/change-authority.md` — new unit, v1.0.0.
- `governance/README.md` — Change Governance section + link.
- `governance/rfcs/README.md` — index row for this RFC.
- `standards/core/decision-policy.md` — D2 cross-reference to the Authority Check.
