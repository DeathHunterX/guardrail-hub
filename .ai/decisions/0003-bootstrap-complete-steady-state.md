# 0003 — Bootstrap Complete; Steady-State Operating Model

Status: **Accepted**
Owner: Loi Phan
Date: 2026-07-06

---

## Context

The AIOS bootstrap roadmap ([Decision 0001](0001-aios-bootstrap-roadmap.md)) is complete: M0 (Constitution Reconciliation), M1 (Schema & Skeleton), M2 (Deterministic Tooling), M3 (Backend Vertical Slice), M4 (Governance Loop Activation), the Architecture Hardening pass (H1–H3), and the first M5 expansion (Frontend) have all closed. The [Domain Expansion Report](../evaluation/reports/domain-expansion-backend-vs-frontend.md) provides the decisive evidence: two structurally different domains (Backend/FastAPI, Frontend/Next.js) run through one pipeline with **zero** change to Constitution, schema, routing model, lifecycle, governance, or tooling, and no RFC.

AIOS v1.0 is therefore no longer a design being built; it is a proven architecture being operated. This decision records that transition and the rules that govern it.

## Decision

**AIOS v1.0 is architecture-frozen and enters Steady State.** The project is now in "operate and expand," not "design."

### Default operating procedure (per new domain / new unit)

1. Choose the domain.
2. Author artifacts against the *existing* contracts (Standard/Agent/Guardrail/… schemas).
3. `python .ai/tools/aios.py validate`.
4. Review (per [review/README.md](../review/README.md)).
5. Acceptance (per-type criteria, [governance §Acceptance](../governance/README.md#acceptance)).
6. Activate (status → `Active`).
7. Regenerate indexes (`aios index`).
8. Update changelog.

No step in this loop may alter the Constitution.

### The frozen set (changeable only by RFC, under the conditions below)

`foundation/`, `kernel/`, the routing *model* (`router/README.md`), `schema/`, the unit *lifecycle*, `governance/` framework, and the `aios` tooling *contract*. (Additive *content* — a new MANIFEST row, a new domain registry entry, new units, generated indexes, changelog lines — is not a Constitution change and needs no RFC.)

### RFC is opened only when

- **(a)** a genuinely new invariant arises that **cannot be expressed** with the current architecture; **or**
- **(b)** **two or more independent domains** hit the **same** limitation of the Constitution.

Absent (a) or (b), every proposed improvement goes to **backlog first** (the standing list in the [Architecture Hardening Report §6](../evaluation/reports/architecture-hardening-m0-m4.md)). A single domain's inconvenience is not evidence; it is a backlog item until a second, independent domain corroborates it.

## Rationale

- **One domain can rationalize almost any change; two independent domains hitting the same wall is signal, not noise.** Condition (b) is a deliberate guard against overfitting the Constitution to whichever domain is being worked on this week — the exact failure the whole AIOS was built to prevent, applied now to its own evolution.
- **The bootstrap earned the freeze.** The architecture wasn't frozen on faith; it was frozen after being exercised end-to-end and reproduced across two domains with the tooling enforcing the invariants (H1–H3). Freezing before that evidence would have been premature; freezing after it is disciplined.
- **Backlog-first keeps velocity honest.** It separates "this would be nicer" from "the architecture cannot do this," and only the latter is allowed to destabilize a proven core.

## Consequences

- Future domains (Mobile, Security, Infrastructure, …) are pure applications of the operating procedure above; each is recorded by a Domain Expansion Report, not a milestone-completion review (M5 is steady-state, not bounded).
- The deferred backlog remains deferred until condition (a) or (b) fires. Items there today: typed frontmatter, data-driven impact rules, domain-scoped guardrail-impact fan-out, real owner registry, block-list YAML, converting remaining module-README manual tables to pointers, the bare-`**` authority edge case.
- This decision extends [Decision 0001](0001-aios-bootstrap-roadmap.md)'s "additive by default / frozen-architecture" principle into a concrete, standing operating contract. It does not supersede 0001; it operationalizes its endgame.
- Changing *this* operating model is itself subject to its own bar: evidence from ≥2 domains, via RFC.

## Related Documents
[Decision 0001](0001-aios-bootstrap-roadmap.md) · [Domain Expansion Report](../evaluation/reports/domain-expansion-backend-vs-frontend.md) · [Architecture Hardening Report](../evaluation/reports/architecture-hardening-m0-m4.md) · [governance/README.md](../governance/README.md) · [tools/README.md](../tools/README.md)
