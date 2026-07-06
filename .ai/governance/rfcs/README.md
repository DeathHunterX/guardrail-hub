# RFCs

Records of changes that went through the [Governance RFC process](../README.md#rfc-process) — Kernel, Router, Guardrails, Foundation, or any module's structural/contract change, or a new top-level module. Established in Roadmap M4 ([Decision 0001](../../decisions/0001-aios-bootstrap-roadmap.md)), when the RFC process ran for the first time.

## Relationship to Decisions and Changelog
- A [Decision](../../decisions/README.md) records *why* a choice was made (narrative). An **RFC** records that a Constitution-tier or structural change went through the *approval gate* (Architecture Review → conditional module reviews → Evaluation → merge) — and IS the changelog entry for that governance change.
- A Decision may precede an RFC (the reasoning) and the RFC ratifies/executes it, or an RFC may stand alone. RFC-0001 stands alone (its rationale is inline).

## Record Contract
Each RFC record contains: **Proposal** (what changes, why, blast radius); **Architecture Review**; **Conditional Module Reviews** (only if it touches a module's structure); **Evaluation** (regression benchmark result, or why N/A); **Decision** (Merged / Returned); **Applied Changes** (the concrete edits, once merged).

## Lifecycle
Append-only, like Decisions. An RFC is `Proposed → Merged` or `Proposed → Returned`; a later change adds a new RFC, never edits a merged one.

## Index

| RFC | Title | Status | Date |
|---|---|---|---|
| [0001](0001-acceptance-criteria.md) | Introduce Acceptance Criteria | Merged | 2026-07-06 |
| [0002](0002-activate-core-guardrails.md) | Activate Core Guardrails | Merged | 2026-07-06 |
