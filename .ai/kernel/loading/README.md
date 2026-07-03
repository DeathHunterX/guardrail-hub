# Kernel — Loading

> Part of the [Kernel Specification](../README.md).

## Responsibilities

Executes the fetch plan the top-level Router produced, under the [Kernel's context budget](../README.md#context-budget--loading-strategy):

1. Fetch Tier 2 addresses in the order the Router prioritized (required before related).
2. When a fetched unit declares a dependency on another unit, fetch that dependency next (dependency loading), not deferred to a later pass.
3. After each fetch, hand control to the "when to stop loading" decision (see [Kernel README](../README.md#when-to-stop-loading-context)) rather than fetching everything the Router returned by default.
4. Never fetch speculatively — an address is only fetched because a specific decision asked for it.

## Inputs
The ordered address list from the top-level Router; the current budget ceiling.

## Outputs
The loaded Tier 2 context bundle handed to the dispatched Agent for planning.

## Dependencies
The top-level [Router](../../router/README.md) (source of addresses), Knowledge/Skills/Standards/Workflows/Templates (fetch targets).

## Consumers
The dispatched Agent (receives the bundle); [Validation](../validation/README.md) (may request additional context if a check fails for a fixable reason).

## Extension Points
The budget ceiling and priority ordering are tunable per deployment (e.g., a smaller-context vendor adapter may run a tighter ceiling) without changing what "priority," "dependency," and "lazy" mean structurally.
