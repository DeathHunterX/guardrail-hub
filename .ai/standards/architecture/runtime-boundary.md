---
id: standards/architecture/runtime-boundary
title: Runtime Boundaries — Independently Deployed Execution Processes
version: 1.0.0
status: Active
owner: backend-owner
category: architecture
scope: mcp-server processes that deploy and run separately from the MCP server
severity_default: blocking
applies_to: [mcp-server/app/runtime/**]
enforced_by: []
depends_on: [standards/architecture/backend-layering]
validated_against: []
---

# Runtime Boundaries — Independently Deployed Execution Processes

> Justification: [Decision 0012](../../decisions/0012-runtime-boundary.md). Implemented and verified 2026-07-29 by the JMeter worker agent.
>
> Where [backend-layering](backend-layering.md) says *which roles exist inside the MCP server and which way its dependencies point*, this standard says *what may live outside that application while still shipping from the same source tree*. It exists because a thing that already exists had no legal home: the JMeter worker is a separately built image, with its own process lifecycle and HTTP surface, that is none of `routers/`, `services/`, `integrations/`, `dao/` or `domain/`.

## Scope

A **Runtime Boundary** is an independently deployed execution process that ships from this repository but is **not** part of the MCP server application.

A component qualifies only if all four hold:

1. It is built and deployed as its **own container image**, separate from the MCP server's.
2. It owns its **own process lifecycle** — it starts, stops and is scaled independently.
3. It has its **own external interface** (an HTTP surface, a queue consumer, a scheduled entry point).
4. It performs **local execution** on its own host that the server cannot perform in-process.

Something that fails any of these is not a runtime boundary; it is application code and belongs in one of [backend-layering](backend-layering.md) R1's roles.

`app/runtime/` is **not a backend layer**. It sits outside R1's role set by explicit carve-out (backend-layering 1.2.0 R1), and this standard governs it instead. R1's whitelist is unchanged and remains blocking for everything else under `app/`.

## Rule Definitions

- **RB1** A runtime boundary lives at `app/runtime/<name>/`, and its process entry point is `app/runtime/<name>/main.py`. `<name>` identifies the deployed process, not a tool family and not a layer.
- **RB2** A runtime component owns **process lifecycle and local execution only**. It composes whatever `integrations/` it needs to do its local work. It owns no business rules, no orchestration of other operations, and no persistence.
- **RB3** A runtime component **MUST NOT** import `app.dao`, `app.services`, `app.routers` or `app.bootstrap` — directly or transitively. Persistence, orchestration, dispatching and the server's HTTP surface are the MCP server's, and a process that can reach them can make decisions that belong to exactly one owner.
- **RB4** A runtime component communicates with the MCP server **only through explicit contracts** — schema types under `app/schemas/`, exchanged over its declared interface. Never a shared database, never shared mutable in-process state.
- **RB5** Every runtime boundary ships with four things: its own **Dockerfile**; an **isolation boundary** in that Dockerfile that copies only the trees its entry point imports (never the whole `app/`); **responsibility documentation** naming what it owns and what it must not; and a **validation test** asserting RB3 against its real import closure.
- **RB6** No module inside `app/runtime/` may be named `runtime.py`. The word already carries two meanings in this codebase — process singletons (`integrations/<tool>/runtime.py`) and per-operation orchestration (`services/tools/<tool>/execution/runtime.py`) — and a third inside the boundary folder itself would be indefensible.

## Mandatory Rules

RB1–RB6 are all Mandatory (blocking). RB3 is additionally **mechanically enforced** by `python .ai/tools/aios.py arch`, which scans `app/runtime/**` and fails on a forbidden import. RB5's test requirement is what keeps the Dockerfile's copy list from silently drifting back to `COPY app ./app`.

## Optional Recommendations

Give the runtime's own schema types a home under `app/schemas/tools/<tool>/` when the boundary serves one tool, rather than inventing a schema location per process.

## Exceptions

None. A component that wants runtime-boundary placement without meeting all four Scope conditions is application code trying to escape [backend-layering](backend-layering.md) R1, which is the failure this standard is shaped to prevent — see [Decision 0012](../../decisions/0012-runtime-boundary.md) §4.

## Anti-patterns

- Adding `app/runtime/<name>/` for a module that is imported by the MCP server. If the server imports it, it is not independently deployed, and it belongs in a backend role.
- A `COPY app ./app` in a runtime's Dockerfile — it makes RB3 true only by convention, since the forbidden modules are still present in the image.
- Reaching the database "just to read" from a runtime component. RB3 admits no read-only exception: the constraint is about who may know the persistence model, not about who may write.
- Using `app/runtime/` as a home for code that "doesn't fit anywhere" — the generic-dumping-ground failure [Decision 0006](../../decisions/0006-service-package-design-standard.md) was written to prevent, reappearing one directory over.
- A runtime component importing another runtime component. Two independently deployed processes do not share code paths; they share contracts.

## Examples

The JMeter worker agent is the reference implementation: `app/runtime/jmeter/main.py` (entry point and its assignment endpoints), composing `app/integrations/jmeter/` for local execution, built by `mcp-server/docker/jmeter/Dockerfile` with a four-tree selective `COPY`, documented in [architecture/jmeter-engine/runtime-responsibility.md](../../../architecture/jmeter-engine/runtime-responsibility.md) §4a, and asserted by `mcp-server/tests/integrations/jmeter/test_jmeter_worker_isolation.py`.

The counter-example is OWASP ZAP: its worker runs the vendor's own daemon image and this repository contains no ZAP worker code at all. A tool only needs a runtime boundary when it ships a command rather than a server.
