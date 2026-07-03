# Decisions
## Decision Records

Status: **Stub** — contract fixed in [Phase 1](../foundation/architecture.md#decisions-decision-records). No dedicated phase in the current roadmap defines this module further; it follows standard ADR practice until one is added.

## Purpose
The durable record of *why* a non-obvious choice was made about the Guardrail Hub product itself — e.g., "why Postgres over Mongo," "why this scanner architecture." This is distinct from the AIOS's own governance records, which belong to **Phase 15 (Governance)**.

## Responsibility
Capture context, options considered, the decision, and its consequences, at the time the decision was made — not reconstructed later from memory.

## Inputs
A human or Agent decision moment worth recording.

## Outputs
An immutable-once-accepted record other units can cite as a source.

## Dependencies
None.

## Consumers
[Agents](../agents/README.md), [Knowledge](../knowledge/README.md) (a knowledge unit may cite a Decision as its source of truth).

## Owner
Whoever made the decision.

## Lifecycle
Append-only. A later decision that changes course adds a new record marking the old one superseded — it does not edit or delete the original. No decisions are recorded yet.
