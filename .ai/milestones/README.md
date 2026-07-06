# Milestones

Historical records of AIOS **implementation** — one entry per milestone in the [Decision 0001 roadmap](../decisions/0001-aios-bootstrap-roadmap.md). A Milestone Review captures *how the execution actually went*: what was planned, what actually changed, what was learned, what debt surfaced.

## This Is Not an AIOS Module

Deliberately outside the twelve+ modules governed by [foundation/architecture.md](../foundation/architecture.md). It has no contract an Agent consumes, is never resolved by the [Router](../router/README.md), is never loaded at runtime (not Tier G/0/1/2/3, not Constitution), and is absent from the [Module Index](../README.md#module-index) by design. It therefore does **not** trigger governance's "new top-level module → RFC" rule ([governance/README.md](../governance/README.md#rfc-process)) — appending a Milestone Review is a bookkeeping act, not a structural change. It exists per direct human direction, discoverable via Decision 0001 rather than via Tier 0.

## What It Is Not (relationship to adjacent records)

| Record | Answers | Where |
|---|---|---|
| **Decision** | *Why* a non-obvious choice was made | [decisions/](../decisions/README.md) |
| **RFC** | *Approval* of a structural/Constitution-tier change | [governance/](../governance/README.md#rfc-process) |
| **Changelog** | *What* version changed, per unit/module | alongside each module |
| **Milestone Review** *(this)* | *How the implementation of a roadmap milestone went* | here |

A Milestone Review never authorizes anything and never supersedes a Decision — if it surfaces a needed course change, that change goes through a Decision or RFC, and the Review only records that it happened.

> **Milestone Review records observations, not architectural decisions.**

If implementation surfaces a needed architecture or governance change, the Review *observes* it and cites the Decision or RFC that must ratify it — it never becomes the place where that change is enacted. A Review that reads as if it decided something is itself a defect: the decision belongs in [decisions/](../decisions/README.md) or an [RFC](../governance/README.md#rfc-process), and the Review should only point to it.

## Record Contract

Every Milestone Review contains these eight sections:

1. **Objective** — the milestone's goal, per Decision 0001.
2. **Planned scope vs. Actual scope** — what was intended vs. what was done.
3. **Files changed** — the concrete change set.
4. **Verification performed** — how Definition of Done was confirmed.
5. **Lessons learned** — what to carry into later milestones.
6. **Deviations** — where actual diverged from planned, and why.
7. **Technical debt / backlog** — issues found but deliberately not fixed in this milestone.
8. **Prerequisites met for next milestone** — the gate check that permits proceeding.

## Lifecycle

Append-only, like [Decisions](../decisions/README.md#lifecycle) — a Milestone Review is written once, when the milestone closes, and is not edited afterward (it is history; correcting history is done by a later record noting the correction, not by rewriting). No numbered-versioning, no Review/RFC gate — it is a log, not a governed unit.

## Index

| Milestone | Review | Closed |
|---|---|---|
| M0 — Constitution Reconciliation | [M0-constitution-reconciliation.md](M0-constitution-reconciliation.md) | 2026-07-06 |
| M1 — Schema & Skeleton | [M1-schema-and-skeleton.md](M1-schema-and-skeleton.md) | 2026-07-06 |
| M2 — Deterministic Tooling | [M2-deterministic-tooling.md](M2-deterministic-tooling.md) | 2026-07-06 |
| M3 — First Vertical Slice (Backend) | [M3-first-vertical-slice.md](M3-first-vertical-slice.md) | 2026-07-06 |
| M4 — Governance Loop Activation | [M4-governance-loop-activation.md](M4-governance-loop-activation.md) | 2026-07-06 |
| M5 — Horizontal Expansion (steady state) — first domain: Frontend | [Domain Expansion Report](../evaluation/reports/domain-expansion-backend-vs-frontend.md) | 2026-07-06 |

M5 is steady-state, not a bounded milestone (per [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)); each domain expansion is recorded by a Domain Expansion Report rather than a milestone-completion review.
