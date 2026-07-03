# Guardrails
## Cross-Cutting Policy Layer

Status: **Stub.** Not one of the twelve modules enumerated in [Phase 1](../foundation/architecture.md#module-hierarchy) by name, but required by it: the Architecture Philosophy inherited from [Phase 0](../foundation/vision.md#architecture-philosophy) states "Policy is a distinct, cross-cutting layer consulted before action, not folded into knowledge." This directory is where that layer lives. It pre-existed as an empty placeholder before this phase; this README makes its role explicit rather than leaving it undocumented. **Flagged for your confirmation** — see the implementation report for this phase.

## Purpose
The authoritative source of safety and security policy — what the AI is never allowed to do, regardless of task, Agent, or how confidently a plan is reasoned. Distinct from [Standards](../standards/README.md) (mandatory *quality/consistency* rules) and from [Kernel/Guardrails](../kernel/guardrails/README.md) (the Kernel's *checkpoints* that consult this layer).

## Responsibility
Author and version policy rules; answer allow/deny/escalate queries from [Kernel/Guardrails](../kernel/guardrails/README.md) at each of its four checkpoints (Boot activation, Routing dispatch, Validation security check, Recovery safety-relevance determination).

## Inputs
Governance decisions, human-set security posture requirements (this is a DevSecOps platform — its own tooling cannot have a weaker policy layer than the product it ships).

## Outputs
Allow/deny/escalate decisions.

## Dependencies
None — foundational, alongside Standards.

## Consumers
[Kernel/Guardrails](../kernel/guardrails/README.md) exclusively. No other module queries Policy directly; everything routes through the Kernel's checkpoints so policy enforcement can't be bypassed by a module that forgets to check.

## Owner
Architecture/governance owners, with security sign-off.

## Lifecycle
Near-immutable, like the Kernel itself — changes here have the same blast radius as a Kernel change and should go through the same governance review (Phase 15). No policy rules are authored yet.
