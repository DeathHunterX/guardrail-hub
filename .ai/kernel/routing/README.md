# Kernel — Routing

> Part of the [Kernel Specification](../README.md).

## Responsibilities

Kernel/Routing answers "which capability handles this," not "which knowledge is needed" (that's the top-level [Router](../../router/README.md)):

1. Take the scope statement from [Behavior](../behavior/README.md).
2. Detect which capability domain(s) it maps to (Backend, Frontend, Security, Infrastructure, …).
3. Select the primary Agent to dispatch to. If the task is genuinely cross-cutting, determine the lead Agent and which others must be consulted (collaboration, not duplication — see the Capability Framework, Phase 3).
4. Check the selection against Guardrails/Policy before dispatch — an Agent is never dispatched into a capability Policy forbids for this task.

## Inputs
The scope statement from Behavior; the capability/Agent registry (populated as Agents are added, Phase 3).

## Outputs
A dispatch decision: primary Agent, any consulted Agents, and the capability label handed to the top-level Router for knowledge-address resolution.

## Dependencies
The Agent registry (Phase 3), Guardrails/Policy.

## Consumers
The top-level [Router](../../router/README.md) (uses the capability label to scope its own resolution), [Loading](../loading/README.md) (fetches for the dispatched Agent).

## Extension Points
New capability domains register into the Agent registry additively — Kernel/Routing's dispatch logic does not change when a new Agent is added, only the registry it reads grows.
