---
id: standards/architecture/domain-layer
title: Domain Layer — Canonical Ownership, Purity and Vocabulary
version: 1.0.0
status: Active
owner: backend-owner
category: architecture
scope: mcp-server domain layer, canonical business concepts, and boundary translation
severity_default: blocking
applies_to: [mcp-server/app/**]
enforced_by: []
depends_on: [standards/architecture/backend-layering]
validated_against: []
---

# Domain Layer — Canonical Ownership, Purity and Vocabulary

> Ratified architecture, translated into enforceable rules. Justification: [Decision 0007](../../decisions/0007-domain-layer-justification.md). Vocabulary: [Decision 0008](../../decisions/0008-domain-ubiquitous-language.md). Implemented and verified 2026-07-20.
>
> Where [backend-layering](backend-layering.md) says *which roles exist and which way dependencies point*, and [service-package-design](service-package-design.md) says *how a package is shaped inside*, this standard says **who owns a business concept and what may touch it**. It exists because the failure it prevents already happened: severity was defined six times, two of those definitions disagreed about what `total` meant, and one could not represent a CRITICAL finding at all.
>
> **D2 and D3 are mechanically enforced.** `python .ai/tools/aios.py arch` scans the Domain tree and fails the build on violation; it runs inside `aios check`. Prose an AI can rationalize past becomes a gate it cannot.

## Scope
Applies to all code under `mcp-server/app/`. D2/D3 govern `mcp-server/app/domain/**` specifically; D1, D4 and D5 govern every layer's relationship to the canonical concepts. Does not govern `web/`, `mobile/`, or `.ai/`.

## Rule Definitions

- **D1 — Canonical Ownership.** Every business concept has exactly **one** canonical definition, owned by one Domain capability. Duplicating a business concept is forbidden, *including* a copy made to avoid an import — that is the precise anti-pattern that produced the six severity definitions, and the code comment justifying it ("defined here so the notification context does not import a tool/domain enum") is not a defence. A concept needed by two contexts is promoted to Domain, never copied. Two names for one concept (`OperationStatus`/`LifecyclePhase`) and one name for two concepts (`total` meaning both "all findings" and "vulnerabilities only") are both D1 violations.

- **D2 — Domain Purity.** `domain/` may contain business meaning, business rules, value objects, entities, and canonical vocabularies. It may **never** contain, or import: FastAPI/Starlette, Pydantic, ORM or SQLAlchemy, Postgres or Redis or any driver, HTTP clients, Slack or any transport SDK, tool SDKs, rendering or Markdown/SARIF/JSON formatting, persistence, infrastructure, logging, or framework types. Domain does not log — its callers do. *(Enforced: `aios arch`.)*

- **D3 — Dependency Direction.** `domain/` depends on nothing outside `domain/`. Application (`services/`, `routers/`) and Infrastructure (`integrations/`, `dao/`) may depend on Domain. Domain must never depend on services, routers, core, schemas, dao, or integrations. Infrastructure depending on Domain is *deliberate and encouraged* — it is what lets an adapter receive a canonical model instead of re-deriving one. *(Enforced: `aios arch`.)*

- **D4 — Canonical Vocabulary.** Business concepts reuse the existing Domain vocabulary defined in [Decision 0008](../../decisions/0008-domain-ubiquitous-language.md). Do not redefine `Severity`, `Finding`, `FindingIdentity`, `FindingSummary`, `Confidence`, or `OperationPhase` — import them. Do not introduce a synonym for a concept that already has a name (`Assessment` for `Operation`) or a qualified variant of a canonical concept (`NormalizedSeverity` alongside `Severity`). Counts use the canonical names `finding_count` and `vulnerability_count`; **no domain term named `total` may exist**. A genuinely new business concept requires an ADR passing the qualification test in Decision 0007 §3 — never an ad-hoc type.

- **D5 — Boundary Translation.** A tool's native model is a **wire format** and belongs to that tool's adapter, never to Domain. Normalization from a native scale to canonical vocabulary happens at the boundary, on the way in. Domain owns canonical concepts only and never learns a vendor's spelling. Concretely: `ZapAlert`/`ZapScanSummary` stay in `schemas/tools/owasp_zap/`; the mapping into `Finding`/`FindingSummary` lives in the ZAP helper/adapter; a future scanner adds its own wire format and its own mapping, and changes **zero** lines of Domain.

## Mandatory Rules
D1–D5 are all Mandatory (blocking). D2 and D3 additionally fail automatically via `aios arch`; D1, D4 and D5 are Review-gate checks (a human or AI reviewer compares the diff against the vocabulary) because "is this the same concept?" is a judgment a regex cannot make.

## Optional Recommendations
- Domain capability `__init__.py` docstrings should state both what is allowed and what is explicitly not allowed, so the boundary is legible at the point of use.
- Domain invariants (Decision 0008 I1–I18) should be asserted by tests; they are the checkable form of the vocabulary.

## Exceptions
- **Tool wire formats retained for persistence.** `ZapScanSummary` remains as a persisted ZAP wire format rather than being deleted; it maps into `FindingSummary` at the adapter. This is D5 operating as designed, not a D1 violation — it is a *format*, not a second definition of severity.
- **Persisted payload keys.** Report payloads may retain historical string keys (e.g. `"total"` in stored suite reports) because renaming them breaks stored data. The D4 ban on `total` applies to Domain signatures and vocabulary, not to frozen wire formats.
- No exception exists for D2 or D3. A Domain module needing infrastructure is a design error, not a special case.

## Anti-patterns
- Defining `class Severity` (or any severity tuple/list) anywhere outside `app/domain/findings/` — including a "display-only" copy in a transport adapter. *(The Slack adapter may own emoji and labels; it may not own the severity set.)*
- Copying an enum into another package to avoid an import, with a comment explaining why the copy is acceptable.
- `from app.services...` inside any `app/domain/**` module.
- `import logging`, `from pydantic import BaseModel`, or `import httpx` inside `app/domain/**`.
- A domain type named `total`, or a summary exposing one ambiguous count instead of `finding_count` and `vulnerability_count`.
- Adding `critical` to one severity list and not the others — the D1 failure mode that silently dropped critical findings from suite aggregation.
- A domain module importing `ZapAlert`, or any type whose name contains a vendor's.
- Introducing `Result`, `Metrics`, `Policy`, or `Compliance` without the ADR trigger in Decision 0008 §6 having fired.

## Examples
- `app/domain/findings/severity.py` is the sole definition of `Severity`; `app/domain/lifecycle/phase.py` is the sole definition of `OperationPhase`.
- `ZapApiScanHelpers.findings_from_summary` is the reference D5 boundary translation: ZAP's native summary in, canonical `FindingSummary` out.
- `SlackNotificationChannel` iterates `SEVERITY_ORDER` from Domain and owns only its emoji map — infrastructure depending on Domain (D3, allowed) without redefining it (D1, satisfied).
