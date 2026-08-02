---
id: standards/core/decision-policy
title: Implementation Decision Policy — Choosing Between Valid Approaches
version: 1.0.0
status: Review
owner: architecture-owner
category: core
scope: every implementation decision in any Domain, whenever more than one technically correct approach exists
severity_default: recommended
applies_to: [mcp-server/**, web/**, mobile/**, api/**]
enforced_by: []
depends_on: []
validated_against: []
---

# Implementation Decision Policy

> The first unit in `core/` — it applies to every Domain with no domain exception ([standards/README.md](../README.md#categories--hierarchy)). Status `Review`, pending a [Review](../../review/README.md) pass and the Owner's [Acceptance](../README.md#acceptance-criteria) gate.

## Purpose

Existing Standards answer *whether* an approach is correct. Several approaches usually pass that test at once — inline the logic, extract a helper, add a service, add a layer — and nothing in the AIOS states which of them is **preferred**. This standard supplies that missing ordering, so the same task produces the same shape of change regardless of which session, model, or Agent handles it.

It is decision-oriented, not prohibitive. Every level below is a legitimate engineering outcome; the policy fixes the *default* and names the *evidence* that justifies moving off it.

## Scope

Applies whenever an Agent or Planner has produced more than one implementation option that satisfies the Standards addressed for the task. It does not adjudicate correctness (that is the Standards' job), safety (Guardrails), or product intent (Decisions) — it only orders options already known to be valid.

## Rule Definitions

### D1 — The Change Ladder

Five levels, ordered by structural blast radius. The **default is the lowest level that fully satisfies the requirement**; each higher level is preferred only when the level below it cannot carry the requirement without distorting it.

| Level | Name | What it changes | Appropriate when | Authority |
|---|---|---|---|---|
| **L1** | **Preserve** | Nothing structural. Code is added or edited inside existing layers, packages, and contracts. | The requirement fits an existing seam. Most tasks land here. | Agent, unilateral |
| **L2** | **Extend** | New units following an established pattern — a new tool integration, a new service in an existing package, a new route in an existing router. | The pattern exists and the new work is another instance of it (e.g. a new scanner mirroring the ZAP layout, [backend-layering](../architecture/backend-layering.md) R3). | Agent, unilateral |
| **L3** | **Refactor locally** | Internal structure of one bounded area — splitting a module, renaming internals, moving logic behind an existing façade. Public contracts stay identical. | The existing shape blocks a correct L1/L2 change, and the fix stays inside one package's boundary ([service-package-design](../architecture/service-package-design.md)). | Agent, unilateral; the diff states the boundary it stayed inside |
| **L4** | **Evolve architecture** | A ratified contract changes — a new architectural role or layer, a new dependency direction, a widened Standard, a new runtime boundary. | Duplication or friction is **observed in present code across multiple call sites**, and no L1–L3 option removes it. | Escalates — requires a Decision (ADR) |
| **L5** | **Redesign architecture** | An established structure is replaced rather than extended. | An invariant the current design rests on has been shown false, with evidence. | Escalates — requires an ADR and, where it changes a Standard's framework, Kernel, Router, or Guardrails, an [RFC](../../governance/README.md#rfc-process) |

The ladder is climbed one rung at a time and stopped at the first rung that holds. Two levels both work → the lower one is preferred, and the reason is a one-line note, not a design document.

### D2 — Escalation Conditions

An option is escalated rather than executed when any of the following is true. Escalation means: stop, produce the ADR/RFC proposal, and return it — not implement first and document after.

- The chosen level is **L4 or L5**.
- The option introduces a business concept not present in the canonical vocabulary ([Decision 0008](../../decisions/0008-domain-ubiquitous-language.md)).
- The option requires a Mandatory Rule of any Standard to be violated or loosened.
- The option crosses an Agent's declared `decision_authority` (per that Agent's Escalation Rules).
- Two Standards conflict and neither is more specific ([standards/README.md](../README.md#conflict-resolution) hands this to [Kernel/Recovery](../../kernel/recovery/README.md)).
- The level cannot be determined because the required facts are absent and the gap is safety- or security-relevant ([guardrails/core.md](../../guardrails/core.md) G5, Kernel's stop-loading rule).

Escalation is a normal outcome, not a failure. An L4 proposal with evidence is a better result than an L1 change that quietly distorts the design to avoid raising one.

*Who* an escalation goes to, and the authority bound each level sits inside, are governed by [Change Governance](../../governance/change-authority.md) — this standard classifies the change; that capability decides who may authorize it. The two questions stay separate: whether the option is preferred, and whether the actor is authorized.

### D3 — Evidence Standard for Levels 4 and 5

L4/L5 are justified by what is true in the code **today**, never by what a change might make easier later. The evidence a proposal carries:

- the concrete call sites or files exhibiting the problem (present-tense, enumerable — [Decision 0007](../../decisions/0007-domain-layer-justification.md) is the worked precedent);
- which L1–L3 options were considered and the specific reason each fails;
- what the change costs: consumers affected, migration path, [Impact Analysis](../../governance/README.md#impact-analysis) blast radius.

Anticipated-but-unobserved need is grounds for a note, not a level.

### D4 — The Planner's Application

When producing a plan:

1. Enumerate the technically valid options — do not collapse to one before the ladder is applied.
2. Assign each option a level by D1.
3. Select the lowest level that fully satisfies the requirement, and **state the selected level and the discarded lower level in the plan** ("L2 — Extend; L1 insufficient because the ZAP router has no seam for a second tool's result contract").
4. If the selected level is L4/L5, the plan's deliverable becomes the ADR/RFC proposal rather than code (D2).
5. Where the plan spans several changes, level each change separately. A plan is not raised to L4 because one step in it is.
6. State the [confidence band](../../governance/confidence-policy.md) alongside the level, and the factor that set it. The level says how much the change moves; the band says how sure the plan is that it should. A plan at Low or Very Low delivers the question or the framing rather than code, exactly as an L4/L5 plan delivers a proposal.

The declared level is part of the plan's contract with the Coding Agent, and is what [Kernel/Validation](../../kernel/validation/README.md)'s Architecture check is read against.

### D5 — The Coding Agent's Interpretation

- Implement at the declared level. The level is a ceiling as well as a floor: an L1 task is not delivered as an opportunistic L3 refactor because the surrounding code was untidy.
- **A level discovered mid-implementation to be insufficient returns to the Planner** with what was found, rather than being silently upgraded in the diff. A silent upgrade is the failure this policy exists to prevent — it is how an unreviewed architecture change ships inside a routine commit.
- Incidental improvements observed but not required are recorded (a note, a follow-up), not bundled.
- Where no plan named a level, the Coding Agent defaults to L1/L2 and escalates before exceeding it.

## Mandatory Rules

**D2 alone is blocking**: an L4/L5 change, or any of D2's other conditions, may not ship without its escalation. Everything else in this standard is a strong default — a departure is legitimate when it is stated and reasoned, and is reviewable precisely because it was stated.

## Optional Recommendations

- Record the level in the commit or PR description; it makes the Architecture validation check a lookup rather than a re-derivation.
- When an L1 option is chosen over a cleaner L3, leave the trade-off as a one-line comment at the site rather than in a separate document.
- Repeated L1 workarounds at the same seam are the natural trigger to gather D3 evidence — three is a signal, one is not.

## Exceptions

- **Security and correctness outrank the ladder.** Where the lowest level would leave a Guardrail, a security control, or input validation weaker, the level that preserves them is the correct choice, and the ladder does not argue against it.
- **Greenfield territory.** In a subsystem with no established architecture yet (`mobile/`, `api/` — near-empty scaffolds per [intelligence/system-overview.md](../../intelligence/system-overview.md)), there is nothing to preserve; the first structural choice there is an L4-style Decision by nature and is treated as one.
- **Reverting to a previously ratified design** is not L5; it is the execution of the Decision that superseded it.

## Related Skills
None yet (`skills/` holds no units).

## Related Knowledge
Grounded in `intelligence/` — [system-overview](../../intelligence/system-overview.md), [module-map](../../intelligence/module-map.md), [conventions](../../intelligence/conventions.md) — until `knowledge/` units exist.

## Related Templates
None yet.

## Related Workflows
None yet; when Workflow units are authored, the level declaration (D4.3) is the natural Review Point.

## Examples

- **L1 — Preserve.** Adding a field to an existing ZAP finding response: the schema, service, and router all exist; the change lands inside them.
- **L2 — Extend.** Adding a JMeter integration by mirroring the ZAP layout exactly ([backend-layering](../architecture/backend-layering.md) R3) — new files, established pattern, no contract change.
- **L3 — Refactor locally.** Splitting an overgrown service module into responsibility subpackages behind its existing façade ([service-package-design](../architecture/service-package-design.md)) — callers unchanged.
- **L4 — Evolve.** The `domain/` layer: duplication of business concepts was observed across present call sites, no local refactor removed it, and the change shipped as [Decision 0007](../../decisions/0007-domain-layer-justification.md) plus a Minor bump to `backend-layering`. This is the reference shape of a correct L4.
- **L5 — Redesign.** The 2026-07-10 architecture hardening ([Decision 0005](../../decisions/0005-architecture-hardening-refactor.md)), which replaced rather than extended the prior service structure.

## Anti-patterns

- **Silent level upgrade.** A plan says "add a field"; the diff also introduces a new top-level package under `app/`. The architecture changed without an ADR, inside a routine review.
- **Speculative L4.** Introducing a layer, interface, or abstraction for a second implementation that does not exist yet — no present-tense call sites, so D3's evidence bar is unmet.
- **L1 as avoidance.** The fifth conditional branch added to the same function to sidestep raising an L3/L4, when the duplication is already enumerable — the ladder prefers the lowest level that *holds*, not the lowest level that compiles.
- **Opportunistic refactor.** A one-line bugfix delivered as a 400-line reorganisation of the surrounding module; the fix is now unreviewable independently of the restructuring.
- **Level asserted without an alternative.** "L4 was necessary" with no statement of which L1–L3 options were tried and why they failed — an unfalsifiable justification, and the same failure mode [guardrails/core.md](../../guardrails/core.md) G5 names for unlabelled inference.
