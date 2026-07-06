# Kernel — Boot

> Part of the [Kernel Specification](../README.md).

## Responsibilities

The cold-start sequence every session begins with, before any task-specific reasoning happens. Redefined by [Decision 0001](../../decisions/0001-aios-bootstrap-roadmap.md) — the original Tier 0 (`foundation/` + `kernel/`, unconditional every session) made every session pay Constitution-sized cost; the sequence below pays that cost only when the task actually needs it:

1. Confirm the session is operating inside the Guardrail Hub repository.
2. Load Tier G (`guardrails/core.md`) — the one truly unconditional load in the whole system.
3. Load Tier 0 (`router/MANIFEST.md`) — the static task-classification lookup, replacing the old `.ai/README.md`-index load in this role.
4. Initialize the Guardrails/Policy layer so no action can be dispatched before policy is active (this consumes the Tier G content just loaded).
5. Hand off to [Behavior](../behavior/README.md), which classifies the task into the Product Lane, Meta Lane, or First-Contact Lane per [kernel/README.md's Startup Sequence](../README.md#startup-sequence) — only the Meta Lane or First-Contact Lane goes on to load `foundation/` and this document's parent in full.

## Inputs
The raw incoming task or request; the repository root; the identity of the calling vendor adapter (Claude Code, Cursor, etc.), if known.

## Outputs
An initialized Kernel context: Tier G loaded, Tier 0 loaded, Policy active, ready to classify and reason about the task.

## Dependencies
`guardrails/core.md`, `router/MANIFEST.md`, Guardrails/Policy.

## Consumers
Every subsequent Kernel module (Behavior, Routing, Loading, …) depends on Boot having run first; nothing in the sequence is valid before Boot completes.

## Extension Points
A vendor adapter may append an adapter-specific boot step (e.g., loading that tool's native config format) *after* core Boot completes, never in place of it. Adapters must not skip loading Tier 0.
