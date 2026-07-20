---
id: standards/architecture/service-package-design
title: Service Package Design & Public API Boundaries
version: 1.0.0
status: Active
owner: backend-owner
category: architecture
scope: mcp-server service package structure, public API surfaces, and internal-package protection
severity_default: blocking
applies_to: [mcp-server/app/**]
enforced_by: []
depends_on: [standards/architecture/backend-layering]
validated_against: []
---

# Service Package Design & Public API Boundaries

> Distilled from the 2026-07-20 Services Architecture Refactor ([Decision 0006](../../decisions/0006-service-package-design-standard.md); executed per [services-architecture-plan.md](../../architecture/evidence/services-architecture-plan.md)). Where [backend-layering](backend-layering.md) governs *which* top-level roles exist and the dependency direction between them, this standard governs the *inside* of a `services/` package: what sits at a package root, what hides in subpackages, and who may import what. Its purpose is to prevent service packages from gradually becoming dumping grounds.

## Scope
Applies to all code under `mcp-server/app/`, with rules R1–R3 and R7–R8 scoped to packages under `mcp-server/app/services/` and rules R4–R6 binding every application module that imports them. Does not govern `web/`, `mobile/`, or the `.ai/` tree.

## Rule Definitions

- **R1 — Services are application boundaries.** A service package exists to expose application use cases. Its package root contains only true application services (plus the `__init__.py` façade). Implementation details — DTOs, dataclasses, enums, renderers, throttles/policies, adapters, subscribers, execution registries, execution handlers, protocol definitions — live in dedicated responsibility-oriented subpackages, never loose at the root.
- **R2 — Intentional public API.** Every service package has a deliberately designed public surface: the package root (`__init__.py`) defines the public contract; everything else is internal implementation. Every exported symbol is a long-term compatibility commitment — export as little as possible; when in doubt, keep it internal. *Documented exception:* a package with a load-cost constraint may declare **module-granularity** as its public API instead of an eager façade (see Exceptions E3).
- **R3 — Responsibility-oriented subpackages.** Implementation subpackages are named for one clear responsibility — the sanctioned vocabulary includes `models/`, `rendering/`, `policy/`, `dispatch/`, `subscribers/`, `execution/`, `handlers/`. Generic buckets — `utils/`, `helpers/`, `misc/`, `common/` — are forbidden inside service packages. (The top-level `app/helpers/` role sanctioned by backend-layering R1 is outside service packages and unaffected.)
- **R4 — Composition Root Exception.** The composition root — `app/bootstrap.py`, plus `app/main.py`'s startup/shutdown wiring — may import internal implementation modules directly; its responsibility *is* knowing concrete implementations and wiring them together. This is not an architecture violation and must not be "fixed" by widening a façade. The exception applies to **nothing else**: routers, services, platform modules, and every other application module depend only on package public APIs or explicit abstractions (ports, injected callables). Tests are likewise exempt (white-box unit tests import the units they test).
- **R5 — Internal package protection.** Implementation subpackages (`dispatch/`, `rendering/`, `policy/`, `models/`, `subscribers/`, `execution/`, `handlers/`, …) are internal. No application module outside the composition root imports them. When a second non-root module needs the same internal symbol, that is an architectural signal, not a precedent: stop, and evaluate under R6 whether the symbol has become part of the package's public contract. Deep imports are never normalized by repetition.
- **R6 — Promotion rule.** A symbol enters a package façade only when it is part of the package's stable application contract. "Bootstrap imports it," "dependency injection constructs it," and "it is convenient" are each explicitly insufficient. Promotion is an explicit architectural decision, recorded (commit message or Decision record) with the contract-based reason.
- **R7 — Service package size trigger.** When a service package accumulates more than roughly five to seven root-level files spanning different responsibilities, an architectural review of the package is required before further growth. The review decides whether responsibilities move into subpackages. Subpackages are *not* created preemptively — a package of two or three closely related files stays flat — but flat packages do not grow indefinitely.
- **R8 — Architecture review trigger.** Before adding a file that (a) introduces a new responsibility to an existing package, (b) adds a second renderer, another execution strategy, another adapter, or another policy implementation, or (c) begins accumulating multiple implementation helpers, review whether the package boundary is still appropriate — and only then add the file. The outcome may be "boundary is fine, proceed"; the requirement is that the question is asked before the file lands, not after the package has decayed.

## Mandatory Rules
R1–R6 are Mandatory (blocking): a diff that violates them is rejected, not merged with a caveat. R7 and R8 are Mandatory *process* rules — the violation is adding files when their trigger conditions are met without performing the review; the review's outcome itself is a judgment call.

## Optional Recommendations
- Subpackages may carry a façade `__init__.py` re-exporting their own contents for intra-package convenience; keep its docstring explicit that the subpackage is internal.
- A façade docstring should state what is public, what is internal, and name the Composition Root Exception, so a future reader learns the boundary from the file itself.

## Exceptions
- **E1 — Composition root** (`app/bootstrap.py`, `app/main.py` startup/shutdown wiring): may deep-import internals, per R4. It accepts the corresponding cost: its imports are updated when internals move.
- **E2 — Tests**: import the units they test directly; forcing tests through façades would bloat façades or weaken tests.
- **E3 — Load-cost-constrained packages**: `services/tools/owasp_zap/` deliberately has **no** eager root façade because an eager re-export would import the zaproxy-dependent scanner chain at package-import time, defeating the lazy-import discipline in `bootstrap.py` and `scan_api_suite.py`. Its public API is module-granularity: root modules are importable by routers/bootstrap; subpackages are internal. Any package claiming this exception must document the load-cost reason where the façade would be.

## Anti-patterns
- `services/notification/` containing `renderer.py`, `throttle.py`, `operation_progress.py`, `event_subscriber.py`, `operation_notifier.py` flat at the package root beside the service — the pre-refactor dumping-ground state this standard exists to prevent (R1/R3).
- Exporting `OperationNotifier` or `EventNotificationSubscriber` from `app/services/notification/__init__.py` "because bootstrap constructs them" — wiring internals advertised as stable contract (R6).
- `app/routers/public/some_router.py` importing `app.services.notification.dispatch.operation_notifier` — a non-root application module reaching past a façade (R4/R5).
- Creating `services/notification/utils/` (or `helpers/`, `common/`, `misc/`) and moving three unrelated functions into it (R3).
- Adding a fourth and fifth scan service file plus two helper modules to the `services/tools/owasp_zap/` root without an architecture review (R7/R8).

## Examples
- `services/notification/` is the reference layout: root = `__init__.py` (exports exactly `NotificationService`, `Notification`, `UnknownChannelError`) + `notification_service.py`; internals in `models/`, `rendering/`, `policy/`, `subscribers/`, `dispatch/`. `platform_reporter.py` consumes the façade; `bootstrap.py` deep-imports `dispatch/` and `subscribers/` under E1.
- `services/tools/owasp_zap/execution/` is the reference for engine consolidation: contract (`handler.py`, `operation_type.py`, `execution_strategy.py`, `registry.py`), loop (`dispatcher.py`), and implementations (`handlers/`) in one internal subtree; the tool package root holds only application services + `sync_runner.py` under E3.
