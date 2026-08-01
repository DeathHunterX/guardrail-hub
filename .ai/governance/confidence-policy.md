---
id: governance/confidence-policy
title: Confidence-Based Decision Making
version: 1.0.0
status: Review
owner: architecture-owner
depends_on: [governance/change-authority, standards/core/decision-policy]
validated_against: [governance/change-authority@1.0.0, standards/core/decision-policy@1.0.0]
category: governance
---

# Confidence-Based Decision Making

> Part of the [Governance framework](README.md), and the third question an Agent answers before implementing. [decision-policy](../standards/core/decision-policy.md) asks *which option is preferred*; [change-authority](change-authority.md) asks *am I authorized*; this asks **do I understand this well enough to act without checking**. Status `Review`, pending [RFC-0004](rfcs/0004-confidence-policy.md).

## The Two Failure Modes

This exists to hold a middle that is easy to lose in either direction:

| Failure | What it looks like | What it costs |
|---|---|---|
| **Over-asking** | Clarification requested for something the repository already answers, or for a choice the Agent was authorized and equipped to make | The human's attention, and worse — it teaches them to pre-load every prompt with instructions, which is the burden this whole capability exists to remove |
| **Over-confidence** | A complete, plausible, standards-compliant implementation of the wrong thing, shipped without anyone noticing a decision was made | Rework at best; an unratified architectural change at worst |

Both are real, and optimizing against one alone produces the other. **Asking is not free, and neither is not asking.** The policy below is calibration guidance, not a gate.

**Fluency is not confidence.** The ability to produce a coherent, complete implementation says nothing about whether it is the right one — an Agent is most fluent exactly where a convention is common in general and possibly wrong here. This mirrors [change-authority](change-authority.md)'s rule that capability is not evidence of authority: the two most dangerous sentences an Agent can hold are *I can build this, therefore I may* and *I can describe this, therefore I know it.*

## What Already Answers This, and What This Adds

[Kernel](../kernel/README.md#when-to-stop-loading-context) already answers "clarification vs. assumption" in binary: a safety- or security-relevant gap escalates; anything else may proceed **if** the assumption is labeled as inference rather than presented as fact ([guardrails/core.md](../guardrails/core.md) G5). [Kernel/Recovery](../kernel/recovery/README.md) implements that as *infer-and-label* or *escalate*.

This document does not change that. It names the bands inside it and specifies the **payload** the Kernel deliberately left open — what a labeled assumption should contain, and what an escalation should carry so the human can decide in one pass rather than three. Recovery's four outcomes stay exhaustive; no fifth branch is added.

## Confidence Bands

Confidence is **not a score**. There is no scale, no percentage, and no threshold — a number would only launder a judgment into a false precision, and would be gamed the moment a band became a gate. A band is recognized by description, and it is a *starting posture* that moves as the work reveals things.

### High — proceed

*Recognized by:* the task maps onto a pattern already present in this repository; the Standards addressed for it decide the open questions; nothing about the requirement is read two ways.

*Response:* implement. No assumption note is owed, because there is no assumption — the choice is traceable to a loaded unit or to existing code.

### Medium — proceed, and write down what you assumed

*Recognized by:* the approach is clear but rests on a reading that a reasonable person might have read otherwise — an unstated edge case, a naming choice, an ambiguity the requirement did not resolve and that the code does not settle.

*Response:* implement, and state the assumption where the reader will meet it: in the plan, in the PR description, and at the site if it is load-bearing. Say what was assumed, what the alternative was, and what would have to be true for the alternative to win.

Medium is the **expected band for most real work**, and the one that does the most to reduce unnecessary clarification: a documented assumption is a question asked asynchronously, at a cost of one sentence instead of one round trip. It is legitimate precisely because G5 makes the label mandatory — an *undeclared* assumption is a guardrail violation, and it is that rule, not this one, that keeps Medium honest.

### Low — pause and ask

*Recognized by:* two or more materially different implementations are consistent with the requirement, and choosing wrong means rework rather than an edit; or a fact the choice turns on is absent and cannot be recovered from the repository.

*Response:* ask — **once, batched, and decidable**. One message containing the options, the trade-off each carries, and a recommendation. Serial single questions cost more than the ambiguity did.

### Very Low — recommend a planning discussion first

*Recognized by:* the requirement itself is not yet settled; the problem is not understood well enough to enumerate options, only to describe symptoms; or scoping the work is the actual work.

*Response:* do not open an implementation. Return a framing of the problem, what is unknown, and the options for *approaching* it. In [Kernel/Recovery](../kernel/recovery/README.md)'s terms this is still an escalation — the band changes the payload, not the outcome.

## Factors That Move Confidence

Signals, not inputs to a formula.

| Factor | Raises confidence | Lowers confidence |
|---|---|---|
| **Ambiguity** | The requirement reads one way; terms match the [canonical vocabulary](../decisions/0008-domain-ubiquitous-language.md) | The requirement supports two readings that produce different code, and nothing in the repo picks one |
| **Architectural impact** | L1–L2; contained inside existing seams | L3+; a contract, boundary, or dependency direction is touched ([decision-policy](../standards/core/decision-policy.md) D1) |
| **Repository conventions** | A precedent exists and is close — the ZAP integration for a new scanner, an existing service for a new one | No precedent, conflicting precedents, or the closest one is itself an exception |
| **Missing information** | Everything the choice turns on is declared and loaded | A load-bearing fact is absent — and absence in a **safety- or security-relevant** area is the one factor that escalates on its own, per [Recovery](../kernel/recovery/README.md) |
| **Implementation risk** | Revertible by reverting the commit; covered by existing checks | Leaves migrated data, a renamed public contract, or a deployed process behind — irreversibility, as [Architecture Impact Analysis](change-authority.md#architecture-impact-analysis) already asks for |

**How they combine: the weakest factor sets the band — they are not averaged.** Four strong signals and one unknown in a high-impact area is not "mostly confident"; it is the unknown, and the rest is scenery. Averaging is how a serious gap gets diluted by things that were never in doubt.

Two consequences worth stating:

- **Architectural impact acts as a ceiling.** At L4/L5, confidence does not read High however familiar the pattern feels — being wrong there is not recoverable by a revert, and the change needs ratification regardless ([change-authority](change-authority.md#architecture-change-classification)). Confidence never substitutes for authority.
- **Reducible uncertainty is not low confidence.** Uncertainty that a look at [`intelligence/`](../intelligence/README.md), the Category Index, or the code itself would remove is *unread context*, and the response is to read it, not to ask. Only irreducible uncertainty moves the band. This single rule removes most unnecessary clarification.

## Confidence and Authority Are Independent

Both must clear before implementation, and neither compensates for the other:

| | **Authorized** | **Not authorized** |
|---|---|---|
| **High confidence** | Implement | Escalate — a good proposal, still not yours to ratify |
| **Low confidence** | Ask — authority does not manufacture understanding | Escalate, and say the understanding is incomplete too, so the authority holder is not handed a confident-sounding proposal |

The bottom-left cell is the one that matters most in practice: holding authority over a path is the most common reason an Agent talks itself past a real doubt.

## Integration

### Planning

The Planner declares a band with the plan, in a sentence, alongside the classification it already declares ([decision-policy](../standards/core/decision-policy.md) D4). The declaration names the factor that set it — "Medium: no precedent for multi-tool result merging; assuming per-tool ordering is preserved" — because the factor is what a reader can disagree with. A plan with no stated band reads as High by default, which is precisely the claim that should have to be made out loud.

Where the band is Low or Very Low, the plan's deliverable becomes the question or the framing, not code — the same substitution D4 already makes for L4/L5.

### Change Governance

Confidence joins the [Authority Check](change-authority.md#authority-check) as a second pass over the same gate, after the three authority questions and before implementation begins:

- **High or Medium** → proceed, with Medium's assumptions recorded in the [Branch Contract](change-authority.md#branch-contract)'s Intent so [Scope Drift Detection](change-authority.md#scope-drift-detection) has them to compare against later. An assumption that turns out false is a legitimate re-entry to the Authority Check, exactly as drift is.
- **Low or Very Low** → the branch is not opened. This is not a drift or a failure state; it is Planning declining to start, which costs nothing.

Confidence adds no new gate and no new state. It is an input to the gate that [RFC-0003](rfcs/0003-change-governance.md) already proposes.

### Review

Review consumes the declared band as **input to its existing dimensions**; no thirteenth dimension is added, and the [12-dimension checklist](../review/README.md#what-every-review-evaluates) is deliberately untouched — changing it requires its own RFC, and nothing here needs it. What Review asks:

- Was a band declared at all? An undeclared assumption that shows up in the diff is a G5 finding, and it is the *omission* that is reviewable, not the assumption.
- Did the delivered change match its band — did a "High" quietly carry three assumptions?
- **Calibration over time.** A band that is repeatedly right is a factor weighted too heavily; one repeatedly wrong is a factor weighted too lightly. This belongs in [Memory](../memory/README.md) as a standing correction — the module that already exists to turn recurring session observations into durable guidance — not in a new metrics apparatus.

Severity follows the existing scale, and a miscalibrated band is a `Suggestion` or `Minor`. Only an *undeclared* assumption reaches Blocking, and it does so through G5, which was already Blocking.

## Anti-patterns

- **Confidence theatre.** Declaring Medium and listing assumptions nobody could act on ("assuming the requirements are as stated") — the label is present, the information is not.
- **The question that reads the code for you.** Asking which layer a service belongs in when [backend-layering](../standards/architecture/backend-layering.md) R1 answers it. This is unread context wearing a clarification's clothes.
- **Serial questions.** Three round trips that one batched message with options and a recommendation would have closed.
- **Assumption as license.** Using a documented assumption to proceed past something that needed authorization — Medium confidence never upgrades an L4 into something an Agent may ship ([change-authority](change-authority.md)).
- **Confidence inflation under pressure.** Urgency changes what a wrong answer costs; it does not change what is known. A band that moves because the request was urgent was never a band.
- **Sandbagging.** Declaring Low to transfer an ordinary judgment call back to the human. Every avoidable question spends the attention this capability is meant to give back.

## Relationship to the Rest of Governance

| Existing mechanism | Relationship |
|---|---|
| [Kernel: when to stop loading](../kernel/README.md#when-to-stop-loading-context) / [Recovery](../kernel/recovery/README.md) | Unchanged and authoritative. This names bands inside their existing binary and specifies the payload; no Kernel file is touched and Recovery's four outcomes stay exhaustive. |
| [guardrails/core.md](../guardrails/core.md) G5 | Unchanged, and it is what makes the Medium band safe — the label is already mandatory, so this policy specifies content rather than obligation. |
| [change-authority](change-authority.md) | Confidence is a second, independent pass on the same Authority Check. Authority asks *may I*; confidence asks *do I know*. |
| [decision-policy](../standards/core/decision-policy.md) | Supplies architectural impact, the factor that caps the band. |
| [Review](../review/README.md) | Consumes the band within existing dimensions; checklist untouched. |
| [Memory](../memory/README.md) | Receives calibration observations through the existing Session → Persistent path. |
| [engineering-philosophy](../knowledge/concept/engineering-philosophy.md) | Adjacent, not overlapping — that document says what to prefer, this says how sure to be before acting on the preference. |

## Lifecycle

Follows [Architecture: per-unit lifecycle](../foundation/architecture.md#lifecycle-per-knowledge-unit-in-any-module). Amendments are expected: the factors above are a first calibration, and the Memory path described under Review is how evidence for changing them accumulates.
