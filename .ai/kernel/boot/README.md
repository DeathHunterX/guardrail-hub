# Kernel — Boot

> Part of the [Kernel Specification](../README.md).

## Responsibilities

The cold-start sequence every session begins with, before any task-specific reasoning happens:

1. Confirm the session is operating inside the Guardrail Hub repository.
2. Load Tier 0 (`foundation/vision.md`, `foundation/architecture.md`, `kernel/`) — the only unconditional load in the whole system.
3. Load the top-level `.ai/README.md` index so Kernel/Routing and the Router have a map to work from.
4. Initialize the Guardrails/Policy layer so no action can be dispatched before policy is active.
5. Hand off to [Behavior](../behavior/README.md) for task reasoning.

## Inputs
The raw incoming task or request; the repository root; the identity of the calling vendor adapter (Claude Code, Cursor, etc.), if known.

## Outputs
An initialized Kernel context: Tier 0 loaded, index loaded, Policy active, ready to reason about the task.

## Dependencies
`foundation/`, the top-level `.ai/README.md` index, Guardrails/Policy.

## Consumers
Every subsequent Kernel module (Behavior, Routing, Loading, …) depends on Boot having run first; nothing in the sequence is valid before Boot completes.

## Extension Points
A vendor adapter may append an adapter-specific boot step (e.g., loading that tool's native config format) *after* core Boot completes, never in place of it. Adapters must not skip loading Tier 0.
