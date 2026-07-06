# Kernel — Routing

> Part of the [Kernel Specification](../README.md).

## Responsibilities

Kernel/Routing answers "which capability handles this," not "which knowledge is needed" (that's the top-level [Router](../../router/README.md)). Per [Decision 0001](../../decisions/0001-aios-bootstrap-roadmap.md), Agents are registered per-Domain, not in one flat global registry — this keeps dispatch lookup bounded as Agent count grows into the hundreds (Domain count grows far slower than Agent count):

1. Take the scope statement from [Behavior](../behavior/README.md).
2. Detect which Domain it maps to (Backend, Frontend, Security, Infrastructure, …) using `router/MANIFEST.md` — the same Global-tier lookup the top-level Router uses.
3. Within that Domain, select the primary Agent to dispatch to from the Domain's own registry (`<domain>/ROUTER.md`). If the task is genuinely cross-cutting, determine the lead Agent and which others — possibly in other Domains — must be consulted (collaboration, not duplication — see the Capability Framework, Phase 3). Domain grouping is a routing namespace only; it does not create authority between Agents — the flat Consult/Delegate/Escalate model in [agents/README.md](../../agents/README.md) is unchanged.
4. Check the selection against Guardrails/Policy before dispatch — an Agent is never dispatched into a capability Policy forbids for this task.

## Inputs
The scope statement from Behavior; `router/MANIFEST.md` (Domain classification); the matched Domain's own Agent registry (`<domain>/ROUTER.md`, populated as Agents are added, Phase 3).

## Outputs
A dispatch decision: primary Agent, any consulted Agents (same-Domain or cross-Domain), and the capability label handed to the top-level Router for knowledge-address resolution.

## Dependencies
`router/MANIFEST.md`, the matched Domain's Agent registry (Phase 3), Guardrails/Policy.

## Consumers
The top-level [Router](../../router/README.md) (uses the capability label to scope its own resolution), [Loading](../loading/README.md) (fetches for the dispatched Agent).

## Extension Points
New Agents register additively into their Domain's own registry — Kernel/Routing's dispatch logic does not change when a new Agent is added, only the Domain registry it reads grows. A genuinely new Domain registers one line in `router/MANIFEST.md` and gets its own `<domain>/ROUTER.md` — rare, unlike ordinary Agent addition.
