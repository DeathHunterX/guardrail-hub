# Module Map

> **2026-07-10 — Architecture Hardening Sync ([ADR-0005](../decisions/0005-architecture-hardening-refactor.md)).** Baseline `10bd79b` predates both the ChatOps subsystem and this refactor. Corrections: (1) the roles `app/prompts/` and `app/utils/` were **removed** — `LoggerUtils` now lives at `app/core/logger_utils.py` (fixing a `core → utils` inversion). (2) Empty scaffold dirs (`app/client`, `app/policies`, `app/runner`, `app/security`, `app/integrations/jmeter`, `app/services/internal`, `app/services/tools/jmeter`, `app/schemas/public`, `app/schemas/tools/{playwright,selenium}`) and 0-byte stubs (`routers/internal/token_router.py`, `routers/mcp/{playwrights,selenium}_router.py`, `schemas/internal/audit_request.py`) were **deleted**. (3) New units: `services/tools/owasp_zap/worker_service.py` (`ZapWorkerService`) and `services/public/health_service.py` (`HealthService`); the worker + health routers are now thin HTTP adapters. (4) The ChatOps subsystem (`core/events`, `core/ports`, `integrations/chat/slack`, `services/{notification,platform,operations,evaluations}`) is live; `MCPLogger` is now the **sole** logger (stdlib `logging` removed from the ZAP client and both scanners).

## Purpose
Describe the internal modules of `mcp-server/app/` and `web/`, what each owns, and whether it's implemented or an empty placeholder.

## Scope
Code-level module boundaries within the two implemented applications. Directory-level structure (including empty top-level folders) is covered in [project-map.md](project-map.md); class-level relationships and execution paths are covered in [codegraph.md](codegraph.md).

## AI Usage Guidance
Before adding code to any module below marked **Empty**, check whether the surrounding modules imply a convention (see [conventions.md](conventions.md)) rather than inventing a new pattern. Modules marked **Implemented** should be extended following their existing pattern, not restructured.

## Main Content

### `mcp-server/app/` Module Boundaries

```mermaid
graph TD
    main[main.py — entry point] --> routers
    routers --> services
    services --> integrations
    services --> dao
    routers --> schemas
    services --> schemas
    integrations --> core_config[core/config]
    dao --> core_config
    routers --> core_config
    services --> helpers
    services --> constants
```

| Module | Status | Owns |
|---|---|---|
| `app/main.py` | Implemented | FastAPI app construction, CORS wiring, router mounting, MCP mount (`FastApiMCP`) |
| `app/routers/public/` | Implemented | `health_router.py`, `history_router.py`, `zap_worker_router.py` — endpoints with no MCP exposure. `zap_worker_router.py` backs `POST /workers/register`, `POST /workers/heartbeat`, `POST /workers/{id}/drain`, `DELETE /workers/{id}`, `GET /workers` — mounted directly on the app, same as `health_router` |
| `app/routers/mcp/` | Partial | `owasp_zap_router.py` implemented and wired; `playwrights_router.py`, `selenium_router.py` exist as files but are **not wired into `endpoints.py`** |
| `app/routers/internal/` | Empty (stub) | `token_router.py` is a 0-byte file — internal token issuance/verification is unimplemented |
| `app/routers/endpoints.py` | Implemented | Central router registry; defines `tools_router` and the MCP-exposed operation whitelist (`MCP_OPERATIONS`) |
| `app/core/config/` | Implemented | Settings composed via mixins (`_app`, `_auth`, `_database`, `_security`, `_server`, `tools/_zap`) into one `Settings` class, backed by `pydantic_settings.BaseSettings` reading `.env`. `tools/_zap.py` no longer has a worker-name/prefix/count field — only deployment-wide timeouts and worker-registry heartbeat/poll intervals |
| `app/core/exception.py`, `app/core/mcp_logger.py` | Implemented | Custom exception handling; `MCPLogger` — the app's only logging mechanism |
| `app/core/startup.py` | Implemented | `run_startup_sequence()` — Database Ready → Run Migrations → Verify required tables → Initialize services (start the ZAP dispatcher), called from `main.py`'s lifespan *before* the defensive reporting try/except so a schema failure aborts boot with a non-zero exit |
| `app/dao/` | Implemented | Data-access layer: `base.py` (interface, now with `get_queued_operations()` and `initialize_schema()`), `postgres/` and `dynamodb/` implementations, selected at runtime by `DATABASE_PROVIDER`. `app/dao/postgres/migrations/` holds versioned `.sql` files applied by `app/dao/postgres/migration_runner.py` |
| `app/integrations/owasp_zap/` | Implemented | `client.py` (`ZapClient`, always bound to an explicit worker `endpoint`), `registry.py` (`OwaspZapWorkerRegistry` — the Worker Registry), `scheduler.py` (`WorkerScheduler` protocol + `RoundRobinScheduler`), `pool.py` (`OwaspZapPoolManager` — assignment + client cache), `runtime.py` (process-wide registry/scheduler/pool-manager singletons), `configurator.py` |
| `app/integrations/jmeter/` | Empty | No files — planned integration, unimplemented |
| `app/schemas/internal/` | Implemented | `token_request.py`, `operation.py` — Pydantic models, some for the unimplemented token router |
| `app/schemas/tools/owasp_zap/` | Implemented | 6 files: request/response models for website scan, API batch scan, interactive scan, common types, scan results |
| `app/schemas/tools/playwright/`, `app/schemas/tools/selenium/` | Empty | Reserved, no schemas defined |
| `app/services/tools/owasp_zap/` | Implemented | `api_scanner.py` (`ZapApiScanService` — `init_api_scan` only queues; `run_assigned_scan`/`zap_scan_worker`/`zap_full_scan_worker` execute once assigned), `dispatcher.py` (`OwaspZapDispatcher` — background queue-poll + heartbeat-sweep loops), `interactive_scanner.py`, `web_scanner.py` |
| `app/services/tools/jmeter/`, `app/services/internal/` | Empty | Unimplemented |
| `app/services/public/history_service.py` | Implemented | `HistoryService` — backs the history endpoints |
| `app/helpers/tools/owasp_zap_helpers.py` | Implemented | ZAP-specific helper functions |
| `app/constants/` | Implemented | `batch.py` (`BatchType` enum), `paths.py` (`ReportPaths`) |
| `app/client/`, `app/policies/`, `app/prompts/`, `app/runner/`, `app/security/` | **Empty** | All exist as directories with zero files — these correspond to concepts named in the root README ("Tool Gateway", "Policy Enforcement", "Runner") that have not been built |

### `web/` Module Boundaries

```mermaid
graph TD
    app[app/ — Next.js App Router] --> components
    components --> lib
    app --> config
    app --> content
```

| Module | Status | Owns |
|---|---|---|
| `web/app/(marketing)/` | Implemented | The only route group — landing page (`page.tsx`) and its `layout.tsx` |
| `web/components/layout/` | Implemented | Site-wide chrome: header, footer, announcement bar, logo, skip-link |
| `web/components/sections/` | Implemented | Marketing page sections (hero, features, pricing, FAQ, te