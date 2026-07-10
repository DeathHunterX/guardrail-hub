# Conventions

> **2026-07-10 — Hardening Sync ([ADR-0005](../decisions/0005-architecture-hardening-refactor.md)).** The MCPLogger-only rule is now enforced everywhere (stdlib `logging` removed from `integrations/owasp_zap/client.py`, `web_scanner.py`, `interactive_scanner.py`; logger instance names standardized to `<ClassName>`). Routers stay HTTP-only: worker-lifecycle and health-probe logic live in `ZapWorkerService` / `HealthService`. Tests now mirror the source tree (grouped by architectural domain, not flat filenames).

## Purpose
Capture the coding and structural conventions actually observed in this codebase, so new code matches existing patterns instead of introducing a competing style.

## Scope
Observed conventions in `mcp-server/` and `web/` only. Where no convention has been established yet (e.g., testing), this document says so explicitly rather than inventing one.

## AI Usage Guidance
Follow these patterns when adding code. Where this document says "no convention established," treat that as license to propose one — but flag it as a new convention rather than presenting it as pre-existing. This document is about observed patterns, not the [Standards Framework](../standards/README.md), which will hold mandatory, enforced rules once any are authored.

## Main Content

### Backend (`mcp-server/`)

**Directory-by-responsibility layering.** Code is organized by architectural role, not by feature: `routers/`, `services/`, `integrations/`, `dao/`, `schemas/`, `helpers/`, `constants/`, each with `core/` as the shared base. See [module-map.md](module-map.md) and [dependency-graph.md](dependency-graph.md) for the enforced one-directional dependency order.

**Sub-partitioning by audience/tool.** Within `routers/`, `schemas/`, and `services/`, further split by audience (`public/`, `mcp/`, `internal/`) or by tool (`tools/owasp_zap/`, `tools/jmeter/`). A new tool integration should follow the ZAP layout: `schemas/tools/<tool>/`, `services/tools/<tool>/`, `integrations/<tool>/`, `routers/mcp/<tool>_router.py`.

**Config via composed mixins.** `Settings` (`app/core/config/__init__.py`) is built from multiple `*Mixin` classes (`AppMixin`, `AuthMixin`, `DatabaseMixin`, `SecurityMixin`, `ServerMixin`, `ZapMixin`), each in its own file, combined via multiple inheritance into one `BaseSettings` subclass. A new settings category (e.g., for a new tool) should follow this pattern: `app/core/config/tools/_<tool>.py` defining a `<Tool>Mixin`, added to the `Settings` class's base list.

**No ORM — hand-written DAO pattern.** Persistence goes through `app/dao/`, not SQLAlchemy models. A common interface (`app/dao/base.py`) is implemented per backend (`postgres/`, `dynamodb/`), selected at runtime by config. See [database-map.md](database-map.md).

**Custom logger, not stdlib `logging` directly.** All logging goes through `MCPLogger` (`app/core/mcp_logger.py`).

**Pydantic for all request/response/config models**, split by role: request/response schemas live in `app/schemas/`, config in `app/core/config/`. Class names for tool-specific schemas are prefixed with the tool name (e.g., `ZapApiTarget`, `ZapScanResult`, `ZapInteractiveScanRequest`) — a new tool's schemas should follow the same `<Tool><Purpose>` naming.

**File naming**: snake_case throughout (`owasp_zap_router.py`, `api_scanner.py`). **Class naming**: PascalCase, often `<Tool><Role>` (`ZapApiScanService`, `ZapClient`, `OwaspZapPoolManager`, `OwaspZapWorkerRegistry`, `OwaspZapDispatcher`) or `<Role>` for generic infrastructure (`PostgresDAO`, `Settings`, `MCPLogger`).

**Worker discovery via self-registration, never generation.** A pool of external processes (ZAP workers today) is never derived from a configurable prefix + count (`prefix-{index}`). Each worker announces itself at runtime (`POST /workers/register`) and heartbeats periodically; a Worker Registry is the single source of truth, and a Scheduler strategy (Round Robin by default, isolated behind a small interface) picks who runs the next queued operation. See [module-map.md](module-map.md) and `architecture/zap-worker-pool/README.md` at the repo root.

**No testing convention established.** `mcp-server/tests/` exists but is empty — there is no existing test file to pattern-match against. Do not assume a test framework (pytest, etc.) is configured; check `pyproject.toml`'s dev-dependencies (currently none declared) before writing tests.

### Frontend (`web/`)

**App Router with route groups.** `web/app/(marketing)/` — parenthesized route groups organize pages without affecting the URL path. A new product area (e.g., a dashboard) would likely follow the same pattern (`app/(dashboard)/`).

**Component layering by reusability scope**: `components/ui/` (shadcn/ui primitives, vendored/generated — don't hand-edit heavily, use `npx shadcn@latest add <component>` per `web/README.md`), `components/shared/` (hand-built reusable pieces), `components/sections/` (page-specific composition, one file per marketing section), `components/layout/` (site-wide chrome).

**Hooks live in `lib/hooks/`, not the root `hooks/` folder** — the root `web/hooks/` contains only a `.gitkeep` and appears to be an unused leftover. Follow `lib/hooks/` for new hooks.

**Path/config conventions**: `components.json` configures shadcn/ui's CLI (aliases, style). `config/site.ts` and `content/site.ts` hold site metadata and marketing copy separately from components.

**No API integration convention established yet** — since `web/` has no code that calls `mcp-server`, there is no existing pattern for HTTP client setup, error handling, or data fetching to follow. This will need to be decided when the two are first integrated (see [system-overview.md](system-overview.md)).

### Cross-Cutting

**Environment-driven config everywhere** — both apps re