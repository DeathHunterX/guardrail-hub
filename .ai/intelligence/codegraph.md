# Code Graph

## Purpose
Give an AI assistant the architectural shape of the code — entry points, major classes, how they call each other, and the execution path of the one fully-working feature — without documenting every function.

## Scope
Architectural relationships only. Does not enumerate every function or file (see [module-map.md](module-map.md) for directory-level ownership). Not a substitute for reading the actual source when implementing a change.

## AI Usage Guidance
Use this to understand how a request travels through the system before modifying any layer in that path. Only one execution path (ZAP API scan) is fully built end-to-end — treat it as the reference pattern for how a new tool integration should be structured.

## Main Content

### Entry Points

| Entry point | File | Starts |
|---|---|---|
| Backend process | `mcp-server/app/main.py` | `uvicorn app.main:app` (per `docker/fastapi/Dockerfile` CMD) — builds the FastAPI app, mounts routers, mounts `/mcp` |
| Frontend process | `web/app/(marketing)/page.tsx` via `web/app/layout.tsx` | `next dev` / `next start` (per `web/package.json` scripts) |
| MCP protocol entry | `/mcp` mount in `app/main.py` (`FastApiMCP`) | Exposes the whitelist in `MCP_OPERATIONS` (`app/routers/endpoints.py`) as MCP tools |

### Major Classes / Modules

| Class | File | Role |
|---|---|---|
| `Settings` | `app/core/config/__init__.py` | Composes `AppMixin, AuthMixin, DatabaseMixin, SecurityMixin, ServerMixin, ZapMixin, BaseSettings` — single source of runtime config, read from `.env` |
| `MCPLogger` | `app/core/mcp_logger.py` | The app's only logging mechanism; every layer below logs through it |
| `PostgresDAO` / DynamoDB equivalent | `app/dao/postgres/postgres_dao.py`, `app/dao/dynamodb/dynamodb_dao.py` | Low-level connection wrappers |
| Operation DAO (Postgres & DynamoDB variants) | `app/dao/postgres/operation_dao.py`, `app/dao/dynamodb/operation_dao.py`, common surface in `app/dao/base.py` | Persistence for scan `OperationRecord`s; provider selected at runtime by `DATABASE_PROVIDER` |
| `ZapClient` | `app/integrations/owasp_zap/client.py` | Wraps the `zaproxy` SDK's `ZAPv2` client |
| `OwaspZapPool` | `app/integrations/owasp_zap/pool.py` | Thread-safe pool managing one ZAP client per Docker container (`acquire_node`, `book_zap_slot`, `release_zap_slot`) |
| `ZapApiScanService` | `app/services/tools/owasp_zap/api_scanner.py` | Orchestrates an API scan: acquires a ZAP slot, drives the scan, normalizes results, persists via DAO |
| `HistoryService` | `app/services/public/history_service.py` | Reads persisted `OperationRecord`s for the history endpoints |

### Package Relationships

```mermaid
graph TD
    routers --> services
    routers --> schemas
    services --> integrations
    services --> dao
    services --> helpers
    services --> constants
    integrations --> core
    dao --> core
    routers --> core
    core --> external[External SDKs: fastapi, fastapi-mcp,<br/>zaproxy, psycopg2, boto3]
```

Dependency direction is one-way: `routers → services → integrations/dao → core`. Nothing in `core/` imports from `services/` or `routers/` (see [dependency-graph.md](dependency-graph.md) for the full internal/external breakdown).

### Service Interactions & Data Flow — ZAP API Scan (the one complete path)

```mermaid
sequenceDiagram
    participant Client as Client (MCP or HTTP)
    participant Router as owasp_zap_router
    participant Service as ZapApiScanService
    participant Pool as OwaspZapPool
    participant ZapClient as ZapClient
    participant Zap as ZAP Docker container
    participant DAO as Operation DAO
    participant DB as Postgres / DynamoDB
    participant Static as public/report/ (static files)

    Client->>Router: POST /tools/zap/scan_api
    Router->>Service: ZapApiScanService.run(request)
    Service->>Pool: acquire_node() / book_zap_slot()
    Pool-->>Service: ZapClient bound to a container slot
    Service->>ZapClient: drive scan (spider, active scan, alerts)
    ZapClient->>Zap: ZAP REST API calls
    Zap-->>ZapClient: scan progress / alerts
    Service->>Service: normalize into ZapScanResult
    Service->>DAO: persist OperationRecord
    DAO->>DB: write
    Service->>Static: write HTML/JSON report
    Service-->>Router: ZapScanResult
    Router-->>Client: response
    Service->>Pool: release_zap_slot()
```

### Important Execution Paths

1. **ZAP API scan** (above) — the only path with a working integration client, container orchestration, persistence, and report generation. Use this as the template for any new scanner integration (Semgrep, Gitleaks, etc. are all unimplemented — see [system-overview.md](system-overview.md)).
2. **History retrieval** — `GET /tools/history/*` → `history_router.py` → `HistoryService` → Operation DAO → Postgres/DynamoDB. Read-only, no external integration.
3. **Health check** — `GET /health`, `/health/live`, `/health/ready` → `health_router.py`, no dependencies beyond process liveness. Used by the Docker Compose healthcheck.
4. **MCP tool invocation** — an MCP client calls through the `/mcp` mount; `FastApiMCP` maps it to one of the four whitelisted operations in `MCP_OPERATIONS` (`app/routers/endpoints.py`), which resolve to the same router functions as the direct HTTP paths above. There is no separate code path for MCP vs. HTTP — both hit the same router handlers.

### What Has No Execution Path Yet

`app/client/`, `app/policies/`, `app/prompts/`, `app/runner/`, `app/security/` are empty — there is no code graph to draw for "Tool Gateway," "Policy Enforcement," or "Runner" concepts named in the root README. Token issuance/verification (`app/routers/internal/token_router.py`) is schema-only, with no handler logic. See [security-map.md](security-map.md) for the implications.

## Related Documents
[module-map.md](module-map.md) · [dependency-graph.md](dependency-graph.md) · [api-map.md](api-map.md) · [database-map.md](database-map.md)

## Last Updated
2026-07-03 — verified against commit `10bd79b`.
