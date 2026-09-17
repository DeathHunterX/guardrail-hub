# Conventions

## Purpose

Capture conventions demonstrated and enforced by the current codebase.

## Scope

Backend and web implementation patterns. Normative instructions remain in AIOS Standards and Agent contracts.

## AI Usage Guidance

Follow nearby code and the applicable routed Standards. This document reports current practice, including known exceptions; it does not legalize a violation.

## Main Content

### Backend structure

- Keep HTTP/MCP routers thin: validate/translate transport data, call an application service, map domain errors at the boundary.
- Put use cases under `app/services/`; expose package-level façades where the package owns a stable public API.
- Keep tool-specific wire formats and adapters in their tool/integration packages; map shared findings and lifecycle meaning into `app/domain/`.
- Domain code must remain framework-free and must not import outer `app` layers.
- Construct concrete graphs in `app/bootstrap.py` and `app/core/startup.py`; their deep imports are an intentional composition-root exception.
- Put external systems behind ports/services and inject them for tests. Scanner code must not directly depend on Slack or another presentation channel.
- Isolated executors belong under `app/runtime/` and must not import server routers, services, DAOs or composition code.
- Use explicit Pydantic request/response schemas at transport boundaries and async functions for network/database work.

### Operations and events

- Create and transition asynchronous work through `OperationService` so persistence and lifecycle events stay aligned.
- Treat direct DAO writes as narrow bookkeeping, not an alternative lifecycle path.
- Keep notification payloads channel-neutral; render and transport them in the notification/adapter layer.
- MCP exposure is an explicit allowlist in `app/routers/endpoints.py`, not automatic for every FastAPI operation.

### Logging and errors

- Normal application logging uses `MCPLogger`; avoid leaking secrets, raw credentials or sensitive prompts/results.
- `conversation_router.py` currently has two local stdlib-logging fallbacks during stream cleanup. Treat these as known exceptions, not a pattern to copy.
- Raise transport-neutral application/domain errors below routers; convert them to HTTP responses at the router boundary.

### Tests

- Backend tests mirror architectural concerns under `mcp-server/tests/` and include unit, integration, flow and boundary checks. Intelligence tests are grouped by capability (`credentials`, `providers`, `registry`, `routing`, `services`, `setup`) with cross-capability behavior under `integration`.
- Add tests at the owning layer and verify observable behavior, including failure paths and dependency boundaries.
- Run AIOS mechanical checks only through `python .ai/tools/aios.py check` when `.ai/` is changed.

### Web

- Use Next.js App Router conventions in `web/app/`.
- Keep feature composition in `web/features/`, reusable visual pieces in `web/components/`, reusable hooks in `web/hooks/`, and general utilities in `web/lib/`.
- Type-check and lint with the declared package scripts; preserve the existing TypeScript and Tailwind conventions.

## Related Documents

[module-map.md](module-map.md) · [dependency-graph.md](dependency-graph.md) · [technology-stack.md](technology-stack.md)

## Last Updated

2026-09-17 — conventions re-derived from current code and reorganized tests at `3632394`.
