# Kernel — Recovery

> Part of the [Kernel Specification](../README.md).

## Responsibilities

Handles the three failure types shown in the [Kernel README's recovery state diagram](../README.md#failure-recovery--fallback): knowledge missing, sources conflict, or validation failed.

1. **Knowledge missing** — ask [Guardrails](../guardrails/README.md) whether the gap is safety/security relevant. If yes, escalate. If no, permit [Behavior](../behavior/README.md) to proceed with a labeled inference.
2. **Conflict** — two loaded sources disagree. Always escalate; the Kernel does not arbitrate between contradictory declared facts (that would violate Phase 0's single-source-of-truth principle — a conflict means the *source* has a defect, not that the AI should guess which one wins).
3. **Validation failed, fixable** — route back to Plan with the specific failed check attached, so the Agent doesn't repeat the same mistake blind.
4. **Validation failed, not fixable** — escalate.

"Escalate" means: return control to the human with a clear statement of what's missing/conflicting and why the AI stopped, rather than a best-effort guess presented as a normal result.

## Inputs
The failure type and context from [Loading](../loading/README.md) (missing address) or [Validation](../validation/README.md) (failed check).

## Outputs
Either a resumed Execute/Plan step (with the fix applied or the inference labeled) or an escalation to the human, ending the session's ability to complete this task autonomously.

## Dependencies
[Guardrails](../guardrails/README.md) (safety-relevance determination).

## Consumers
[Lifecycle](../lifecycle/README.md) (an escalation is itself a session outcome worth writing to Memory — "the AI didn't know X" is exactly the kind of thing the feedback loop exists to capture).

## Extension Points
None structurally — Recovery's four outcomes (escalate, infer-and-label, replan, escalate) are meant to be exhaustive. If a future failure mode doesn't fit one of the three failure types, that's a signal the Kernel README's failure taxonomy needs revisiting, not that Recovery needs a fifth ad hoc branch.
