# Decisions
## Decision Records

Status: **Stub** — contract fixed in [Phase 1](../foundation/architecture.md#decisions-decision-records). No dedicated phase in the current roadmap defines this module further; it follows standard ADR practice until one is added.

## Purpose
The durable record of *why* a non-obvious choice was made — about the Guardrail Hub product itself (e.g., "why Postgres over Mongo," "why this scanner architecture"), or about the AIOS's own foundational strategy when no other mechanism captures the narrative reasoning. [Governance](../governance/README.md) (Phase 15) owns the *mechanics* of how AIOS changes are versioned, RFC'd, and gated — it does not itself hold a "why we chose this sequence, what we rejected" record. Decisions owns that narrative, whether the subject is product or AIOS-process.

## Responsibility
Capture context, options considered, the decision, and its consequences, at the time the decision was made — not reconstructed later from memory.

> **Frontmatter:** Decision records are append-only narrative records, not Router-addressable units, so they use a light ADR header (`Status`, `Owner`, `Date`) rather than the full [unit schema](../schema/README.md). This is a deliberate exception noted here so the "every module references the schema" expectation resolves to an explicit "does not apply, and why," not silence.

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
Append-only. A later decision that changes course adds a new record marking the old one superseded — it does not edit or delete the original.

## Index

| Decision | Status | Date |
|---|---|---|
| [0001 — AIOS Implementation Roadmap & Bootstrap Strategy](0001-aios-bootstrap-roadmap.md) | Accepted | 2026-07-06 |
| [0002 — Guardrail Rule Granularity](0002-guardrail-rule-granularity.md) | Accepted | 2026-07-06 |
| [0003 — Bootstrap Complete; Steady-State Operating Model](0003-bootstrap-complete-steady-state.md) | Accepted | 2026-07-06 |
| [0004 — ChatOps Platform Architecture](0004-chatops-platform-architecture.md) | Proposed | 2026-07-07 |
| [0005 — Architecture Hardening Refactor & Corruption Recovery](0005-architecture-hardening-refactor.md) | Accepted | 2026-07-10 |
| [0006 — Service Package Design Standard](0006-service-package-design-standard.md) | Accepted | 2026-07-20 |
| [0007 — Domain Layer Justification](0007-domain-layer-justification.md) | Accepted | 2026-07-20 |
| [0008 — The Canonical Domain Language](0008-domain-ubiquitous-language.md) | Accepted | 2026-07-20 |
| [0009 — Execution Capability](0009-execution-capability.md) | Accepted | 2026-07-20 |
| [0010 — Performance Engine Capability (Apache JMeter)](0010-performance-engine-capability.md) | Accepted | 2026-07-22 |
