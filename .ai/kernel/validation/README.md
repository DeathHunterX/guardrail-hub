# Kernel — Validation

> Part of the [Kernel Specification](../README.md).

## Responsibilities

The pre-output gate. Nothing returns to the requester without passing through this module. Runs the six checks defined in the [Kernel README's Validation Gate](../README.md#validation-gate): Architecture, Naming, Standards, Workflow, Security, Completeness.

1. Compare the proposed action's scope against `foundation/architecture.md` module boundaries (did the Agent stay in its lane?).
2. Check Naming and Standards against the Standards units that were addressed for this task.
3. Check Workflow compliance if the task was executed under a Workflow (were required checkpoints honored?).
4. Check Security via [Guardrails](../guardrails/README.md).
5. Check Completeness against the original task as scoped in Behavior — not against what was easiest to produce.

## Inputs
The proposed action/output from the dispatched Agent; the Standards/Workflow units that were loaded for this task; the original task scope.

## Outputs
Pass → output returned to requester. Fail-fixable → sent back to Plan. Fail-not-fixable → sent to [Recovery](../recovery/README.md).

## Dependencies
Standards, Workflows (as applicable), [Guardrails](../guardrails/README.md).

## Consumers
[Lifecycle](../lifecycle/README.md) (only validated output is eligible for session termination / return); [Recovery](../recovery/README.md) (receives not-fixable failures).

## Extension Points
Additional checks may be added to the gate as new Standards categories are introduced (Phase 6); the six-check structure itself does not need to change to accommodate them — a new Standards category is just more input to the existing "Standards" check.
