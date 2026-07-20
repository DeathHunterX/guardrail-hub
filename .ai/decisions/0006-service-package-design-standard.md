# 0006 — Service Package Design Standard (Governance Capture of the Services Refactor)

Status: **Accepted**
Owner: Loi Phan
Date: 2026-07-20

---

## Context

A three-pass architecture review of `mcp-server/app/services/` (audit → package-design plan → public-API minimization; artifacts: [services-architecture-audit.md](../architecture/evidence/services-architecture-audit.md), [services-architecture-plan.md](../architecture/evidence/services-architecture-plan.md)) found the service layer largely well-placed but structurally decaying in one specific way: service packages accumulating implementation files at their roots. `services/notification/` was the clearest case — a DTO, a domain model, a renderer, a throttle policy, an event subscriber, and a delivery strategy sitting flat beside the application service, with every consumer importing deep file paths because no package had a public API (`__init__.py`) at all.

The refactor that followed (executed 2026-07-20, behavior-preserving, 194 tests green throughout) established a package-design discipline the existing Standards did not capture: [backend-layering](../standards/architecture/backend-layering.md) governs the top-level roles and dependency direction, but nothing governed the *inside* of a service package — so nothing would stop the same decay from recurring as contributors (human or AI) add files along the path of least resistance.

Two design questions settled during the refactor carry non-obvious reasoning worth recording:

1. **Public APIs are contracts, not conveniences.** The first façade draft exported everything `bootstrap.py` imported (`OperationNotifier`, `EventNotificationSubscriber`, `LifecyclePhase`, the execution dispatcher and handler factories). This was rejected: the composition root's job is to know implementations, so its imports must not define the public surface. The final notification façade exports three symbols; bootstrap deep-imports the rest by design.
2. **One package earned an exception.** `services/tools/owasp_zap/` has no eager façade because re-exporting its services would import the zaproxy-dependent chain at package-import time, defeating deliberate lazy-import discipline. The exception is documented rather than silently divergent.

## Decision

Adopt [standards/architecture/service-package-design@1.0.0](../standards/architecture/service-package-design.md) as an Active architecture Standard, enforced by the Backend Agent, capturing eight rules: (R1) service package roots hold only application services; (R2) every package has an intentionally minimal public API; (R3) implementation subpackages are responsibility-named, never generic buckets; (R4) only the composition root may import internals; (R5) internal subpackages are protected — repeated outside need is a signal, not a precedent; (R6) façade promotion is an explicit contract decision, never a wiring convenience; (R7) ~5–7 mixed-responsibility root files trigger an architecture review; (R8) new responsibilities/renderers/strategies/adapters/policies trigger a boundary review before the file lands.

Enforcement wiring (all additive):

- New unit `standards/architecture/service-package-design.md` (Active; `applies_to: mcp-server/app/**`; `depends_on: backend-layering`).
- Backend Agent `standards_enforced` gains the new standard (agent bumped 1.0.0 → 1.1.0, Minor/additive per [Governance versioning](../governance/README.md#versioning)).
- Backend Domain Router task table gains a "service package structure / new service file" subtype row.
- `standards/architecture/INDEX.md` regenerated via `aios index`.

No RFC is required: this is a new unit within an already-approved module, not a Kernel/Router/Guardrails or structural change ([Governance — RFC Process](../governance/README.md#rfc-process)). `backend-layering` itself is intentionally left untouched at 1.0.0 to keep the blast radius additive.

## Consequences

- Future additions to `services/` are checked against R1–R8 at the Validation gate; the pre-refactor flat-package state is now a named, citable Anti-pattern rather than a matter of taste.
- The Composition Root Exception is codified once, in a Standard, instead of living only in refactor-plan prose — deep imports in `bootstrap.py` are sanctioned; deep imports anywhere else are violations with a defined remediation path (R5 → R6 promotion evaluation).
- The `owasp_zap` no-façade exception (E3) is a documented, bounded carve-out; a future package wanting the same treatment must document its own load-cost reason.
- Rejected alternative: folding these rules into `backend-layering` as a 1.1.0 bump. Rejected because the two standards answer different questions (where roles live vs. how a package is shaped internally), and because backend-layering is pinned by `validated_against` references whose churn an additive new unit avoids.
