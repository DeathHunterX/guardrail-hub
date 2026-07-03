# Kernel — Lifecycle

> Part of the [Kernel Specification](../README.md).

## Responsibilities

Manages the AI session itself as a process (Phase 0's "Assistant sessions are processes" analogy), distinct from the lifecycle of any individual knowledge unit (that's the [Architecture's per-unit lifecycle](../../foundation/architecture.md#lifecycle-per-knowledge-unit-in-any-module)):

1. **Spin up** — triggered by Boot completing.
2. **Run** — the session executes the startup sequence (reason, route, load, plan, validate) for as many tasks as the session covers.
3. **Terminate** — on completion, write session outcomes to [Memory](../../memory/README.md): corrections, confirmations, anything worth surviving past this session.
4. **Leave no undeclared state** — nothing persists across sessions except what was deliberately written to Memory. A session does not silently mutate `.ai/` content as a side effect of reasoning.

## Inputs
Boot completion (start signal); the sequence of tasks handled in this session; Validation/Recovery outcomes to capture as feedback.

## Outputs
A closed session and a set of Memory entries (possibly empty, if nothing in the session was novel enough to persist).

## Dependencies
[Memory](../../memory/README.md) (write target at termination).

## Consumers
None downstream within the same session — Lifecycle's output is consumed by the *next* session's Boot (via Memory).

## Extension Points
Vendor adapters may define their own session boundaries (e.g., one chat = one session, or one task = one session); Lifecycle's contract (spin up → run → terminate → feed back) holds regardless of how a given tool draws that boundary.
