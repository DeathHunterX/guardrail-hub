---
id: knowledge/concept/engineering-philosophy
title: Engineering Philosophy — Default Decision Tendencies
version: 1.0.0
status: Review
owner: architecture-owner
category: concept
depends_on: [standards/core/decision-policy]
validated_against: [standards/core/decision-policy@1.0.0]
---

# Engineering Philosophy

> The values this repository builds by. They exist so that preferences a human would otherwise repeat in every prompt are **declared once, versioned, and discoverable** — a team convention in the sense [foundation/vision.md](../../foundation/vision.md#4-principles-that-must-never-be-violated) means it, not a rule and not an inference.

## Why This Is Knowledge and Not a Standard

A Standard states what an engineer **must** do and is checked pass/fail. This document states what this repository **prefers** when nothing mandates an answer — and most engineering choices are of that kind. Filing it as a Standard would convert taste into a gate and produce exactly the constraint list it is meant to replace.

Placement also settles precedence for free. [AGENTS.md](../../../AGENTS.md)'s conflict order is `Guardrails → Standards → Decisions → Intelligence/Knowledge → …`, so this document already ranks **below** every rule in the system. A value can inform a judgment call; it can never license a Standard violation or overrule a Guardrail. No change to that ordering was needed to make that true.

## Scope

Applies to product code in every Domain, on every task, as the default lean when two or more options remain after the Standards have been satisfied. It covers *what to prefer*, never *what is permitted* ([guardrails/core.md](../../guardrails/core.md)), *what is required* ([standards/](../../standards/README.md)), or *who may authorize* ([governance/change-authority.md](../../governance/change-authority.md)).

---

## The Values

Each states the tendency, why it is held, and where the exception lives. Where a mechanism already enforces it, that mechanism is **linked, not restated** — the value is the *why* beneath the rule, and the rule stays the single source of truth for the *what*.

### P1 — Prefer minimal change

*Why.* Diff size is the most reliable proxy available for risk: every line changed is a line that can regress, and a small diff is one a reviewer can actually hold in their head. Minimal change also keeps a revert cheap, which is what makes moving fast survivable.

*Exception.* When the minimal change works only by adding a special case to a shape that is already carrying several — the small diff is then buying time at compounding interest. Preferring the *smallest* change over the *right* change is a misreading of this value, not an application of it.

*Mechanism.* [decision-policy](../../standards/core/decision-policy.md) D1 — the ladder's default is the lowest level that **holds**, not the lowest level that compiles.

### P2 — Preserve existing architecture

*Why.* An existing structure carries information that no reading of it fully recovers: the constraints that shaped it, the failures it already absorbed. Consistency with a merely-adequate structure usually beats local improvement, because a codebase with one adequate pattern is more navigable than one with three good ones.

*Exception.* When the structure has been shown false rather than merely inconvenient — an invariant it rests on no longer holds. Inconvenience is not evidence; [Decision 0012](../../decisions/0012-runtime-boundary.md) is the worked example of the distinction, where territory was placed *outside* a rule rather than the rule being bent to admit it.

*Mechanism.* [decision-policy](../../standards/core/decision-policy.md) L1, and [backend-layering](../../standards/architecture/backend-layering.md) R1's rule that a genuinely new role is a Decision, never an ad-hoc folder.

### P3 — Prefer extension over replacement

*Why.* Extension keeps existing consumers working and keeps the change reviewable against a known baseline. Replacement discards proven behavior along with the flaw and moves the risk from the part being fixed to every part that depended on it.

*Exception.* When extension would require the existing abstraction to mean two different things — a shape extended past its concept produces a component nobody can describe in a sentence, which is worse than the replacement it avoided.

*Mechanism.* [decision-policy](../../standards/core/decision-policy.md) L2 before L5; [governance/change-authority](../../governance/change-authority.md) makes replacement the level that requires ratification.

### P4 — Avoid unnecessary abstraction

*Why.* Abstraction trades a concrete cost now — indirection, a layer to step through, a concept to learn — for flexibility that may never be exercised. Duplication is visible and cheap to remove later; the wrong abstraction is invisible and expensive, because every subsequent change is shaped to fit it.

*The working test.* Does a **second real** caller exist today? Not a plausible one, not a planned one. Two concrete call sites justify the extraction; one justifies waiting.

*Exception.* Where the abstraction is the boundary itself rather than a convenience — a port at a trust or transport edge earns its place on the first implementation, because its purpose is isolation, not reuse ([domain-layer](../../standards/architecture/domain-layer.md) D5).

*Mechanism.* [decision-policy](../../standards/core/decision-policy.md)'s *Speculative L4* anti-pattern and D3's present-tense evidence bar.

### P5 — Prefer local optimization before global optimization

*Why.* A local fix is verifiable by the person making it and revertible by itself. A global refactor asserts that a pattern observed in one place generalizes to all of them — an assertion that is usually made before the evidence exists, and that is unfalsifiable once merged. Solve it where it hurts; let the third occurrence, not the first, argue for generalizing.

*Exception.* When the same defect is genuinely one root cause behind several symptoms. Patching each call site is not local optimization — it is the same global change, made worse by being scattered. Fix it once where the callers route through.

*Mechanism.* None mechanical. This is judgment, and is flagged at [Review](../../review/README.md) rather than gated.

### P6 — Optimize readability before cleverness

*Why.* Code is read far more often than written, and most of those readings happen under pressure — during an incident, by someone who did not write it, possibly by a model with only the surrounding file in context. Cleverness optimizes the moment of authorship at the expense of every reading afterward. Boring code is a feature.

*Exception.* A measured hot path, where the clever form is justified by a number and annotated with it. The comment explaining *why* the obvious form was rejected is part of the change, not an optional extra.

*Mechanism.* [Review](../../review/README.md)'s Maintainability dimension.

### P7 — Prefer stability over elegance

*Why.* This is a DevSecOps platform whose value proposition is trustworthy security posture ([foundation/vision.md](../../foundation/vision.md#1-2-what-problems-does-aios-solve-and-why-must-it-exist)). A dependable system that is slightly inelegant serves that purpose; an elegant one that surprises its operators does not. Elegance is worth having when it is free, and worth deferring when it is not.

*Exception.* When the inelegance is itself the instability — a structure so awkward that every change to it introduces a defect. At that point the tidiness argument and the reliability argument point the same way, and the change is justified on reliability.

*Mechanism.* None mechanical. Reversibility is the practical proxy, and it is what [Architecture Impact Analysis](../../governance/change-authority.md#architecture-impact-analysis) asks for.

### P8 — Architecture evolution requires explicit justification

*Why.* Architecture is the set of decisions that are expensive to reverse. Any of them may be right; none of them should be arrived at implicitly, as a side effect of a change that was described as something else. The requirement is not that evolution be rare — it is that it be *visible*, so it can be argued with while it is still cheap.

*Exception.* None to the requirement of justification. The *weight* of the justification scales with the level: a sentence at L3, evidence and an ADR at L4, an RFC at L5.

*Mechanism.* [decision-policy](../../standards/core/decision-policy.md) D3 (evidence) and [governance/change-authority](../../governance/change-authority.md) (who ratifies it).

### P9 — Prefer disciplined execution over continuous optimization

*Why.* Implementation is when the code is understood best, so it is when improvements are most visible — and acting on each one means a plan that never closes and a change no reviewer can evaluate, because what was delivered is no longer what was described. A discovered improvement is evidence of engineering insight; implementing it is a separate engineering decision, made with the same deliberation as the first one.

*Exception.* When the discovery is required for correctness, for safety, or for architecture integrity. Those three were never inside the scope trade-off — a plan does not authorize shipping something known to be wrong.

*Mechanism.* [governance/improvement-discovery](../../governance/improvement-discovery.md) — the discovery is recorded, and implementation continues.

---

## Where the Philosophy Yields

These values order options that are *already* acceptable. They never argue against:

- a [Guardrail](../../guardrails/core.md) or a security control — P1's small diff is not a reason to leave validation weaker;
- a Mandatory Rule of any Standard — precedence is settled above;
- correctness, or error handling that prevents data loss;
- an explicit human instruction for this task, which outranks a standing default by construction ([human authority is final](../../foundation/vision.md#4-principles-that-must-never-be-violated)).

Two values can also point opposite ways — P3 says extend, P4 says do not abstract; P2 says preserve, P6 says make it readable. That is expected of values and is not a defect to be resolved by adding a tiebreak rule. The tie is broken by the mechanism that governs the specific case ([decision-policy](../../standards/core/decision-policy.md) for which option, [change-authority](../../governance/change-authority.md) for who may choose it) and, failing that, by asking.

## How Each Role Reads This

- **Planner** — uses the values to *order* the options it enumerates, and states the one it followed when the choice was close ("kept the duplication, P4 — one caller"). It does not cite a value as a reason a Standard does not apply.
- **Coding Agent** — applies them as the default lean inside its authorized [Branch Contract](../../governance/change-authority.md#branch-contract). A value never widens scope: "P6, so I tidied the module" is the [opportunistic refactor](../../standards/core/decision-policy.md#anti-patterns) wearing a philosophy label.
- **Reviewer** — reads a departure as a discussion to have, not a violation to log. A stated departure with a reason is healthy; the reviewable failure is an **unstated** one, which is the same shape as an unlabelled inference ([guardrails/core.md](../../guardrails/core.md) G5). Severity for a philosophy departure is `Suggestion` or `Minor`, never `Blocking` — this document holds no Mandatory Rules to violate.
- **Governance** — treats a value that keeps being overridden as evidence about the value, not about the engineers. Recurring, well-reasoned departures are the intended trigger to amend this unit, via the ordinary [Impact Analysis](../../governance/README.md#impact-analysis) path. Governance also holds the line that a value never becomes a gate: converting one into a Mandatory Rule is a Standards change, deliberate and reviewed, not a drift in how this document is read.

---

## Contract

| Field | Value |
|---|---|
| **Purpose** | State the repository's default engineering tendencies once, so they stop being re-supplied per prompt and start being discoverable, versioned context. |
| **Scope** | Product code in every Domain, as the lean between options that already satisfy the Standards. Not permission (Guardrails), not requirement (Standards), not authority (Change Governance), not procedure (Skills). |
| **Dependencies** | [standards/core/decision-policy](../../standards/core/decision-policy.md) — supplies the mechanism P1–P3 and P8 refer to. |
| **Consumers** | Every Capability Agent (via both Domain Routers' always-loaded set), Planner, [Review](../../review/README.md), [Governance](../../governance/README.md). |
| **Update Frequency** | `static` — values change on deliberate amendment, not on a schedule. Staleness is signalled by recurring justified departures, not by elapsed time. |
| **Owner** | `architecture-owner`. |
| **Related Standards** | [core/decision-policy](../../standards/core/decision-policy.md); [architecture/backend-layering](../../standards/architecture/backend-layering.md) (P2); [architecture/domain-layer](../../standards/architecture/domain-layer.md) (P4). |
| **Related Skills** | None yet (`skills/` holds no units). |
| **Related Workflows** | None yet; when authored, Planning and Review are where these values are consulted. |
