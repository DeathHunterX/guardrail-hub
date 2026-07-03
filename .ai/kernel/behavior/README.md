# Kernel — Behavior

> Part of the [Kernel Specification](../README.md).

## Responsibilities

Defines the reasoning discipline every session must follow (Phase 0, §5–10, made operational):

1. **Layered reasoning, not one pass.** Establish scope (which module/domain does this task touch) before retrieving anything; retrieve the minimum relevant knowledge for that scope; apply the governing policy for that scope; then act.
2. **Declared vs. inferred.** Every claim the AI makes is either traceable to a loaded Knowledge/Standard/Decision unit ("declared") or explicitly labeled as the AI's own inference. The two are never presented identically.
3. **Escalate rather than improvise.** When knowledge conflicts or is absent and the gap is safety- or security-relevant, Behavior routes to [Recovery](../recovery/README.md) instead of generating a plausible-sounding fill-in.

## Inputs
The task as scoped by Boot; whatever context has been loaded so far this session.

## Outputs
A scope statement (which domain/module this task belongs to) and a reasoning trace that downstream steps (Routing, Validation) can inspect for the declared/inferred distinction.

## Dependencies
Guardrails/Policy (to know what "safety-relevant" means for escalation purposes).

## Consumers
[Routing](../routing/README.md) (uses the scope statement to pick a capability), [Validation](../validation/README.md) (checks the declared/inferred distinction was honored in the final output).

## Extension Points
None at the reasoning-discipline level — this is the one Kernel module Phase 0 explicitly marks as near-immutable. Vendor adapters may render the declared/inferred distinction differently in their own UI (e.g., inline citations vs. a footnote), but may not remove it.
