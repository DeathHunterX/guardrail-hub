# Kernel — Guardrails

> Part of the [Kernel Specification](../README.md). See also the top-level [Policy layer](../../guardrails/README.md), which this module consults.

## Responsibilities

The Kernel's own invocation points for the cross-cutting Policy layer — Guardrails is not where policy is authored, it's where the Kernel *checks* it:

1. At Boot — activate Policy before any dispatch can happen.
2. At Kernel/Routing — block dispatch into a capability Policy forbids for this task.
3. At Validation — run the Security check against Policy before output ships.
4. At Recovery — determine whether a gap is "safety/security relevant" (and therefore must escalate) by asking Policy, not by the AI's own judgment.

## Inputs
The dispatch decision (from Routing), the draft output (from Validation), the failure type (from Recovery).

## Outputs
An allow/deny/escalate decision at each of the four checkpoints above.

## Dependencies
The top-level [Policy layer](../../guardrails/README.md) (authoritative rule source), Standards (security-category rules).

## Consumers
Boot, Routing, Validation, Recovery — every other Kernel module that has a checkpoint above consumes this module's decision.

## Extension Points
New policy rules are authored in the top-level Policy layer, not here. This module's four checkpoints are fixed by the Kernel's near-immutability; what each checkpoint checks *against* can grow.
