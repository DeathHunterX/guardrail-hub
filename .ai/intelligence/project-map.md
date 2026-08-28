# Project Map

## Purpose

Map repository locations to their current responsibilities and maturity.

## Scope

Top-level and important second-level directories. Use [module-map.md](module-map.md) for internal ownership.

## AI Usage Guidance

Use this map to find the correct work area. A directory's presence is not evidence that its advertised feature is complete.

## Main Content

| Path | Responsibility | Status |
|---|---|---|
| `.ai/` | AI Operating System: guardrails, routing, agents, standards, decisions, intelligence and tooling | Active; maturity varies by module |
| `.github/workflows/` | Repository automation | AIOS validation workflow present |
| `mcp-server/app/` | FastAPI/MCP product backend | Substantially implemented |
| `mcp-server/tests/` | Unit, integration, flow and architecture tests | Substantial suite |
| `mcp-server/config/` | LLM provider/model registry | Implemented configuration |
| `mcp-server/migrations/` | SQL schema migrations | Implemented |
| `mcp-server/docs/` | Backend-specific design and operational notes | Populated |
| `web/app/` | Next.js routes and layouts | Multi-page marketing site |
| `web/components/`, `web/features/`, `web/hooks/`, `web/lib/` | Web UI, feature composition and client utilities | Implemented for site experience |
| `mobile/` | Mobile application target | Near-empty scaffold |
| `api/` | Separate API target | Near-empty scaffold; backend lives in `mcp-server/` |
| `docs/` | Documentation-site project | Scaffold/content shell |
| `architecture/` | Product architecture notes for ZAP, JMeter and ChatOps | Populated evidence/design material |
| `docker-compose.yml`, `Dockerfile*` | Local/container runtime definitions | Implemented for server and workers |

Important backend subtrees:

| Path | Responsibility |
|---|---|
| `app/core/` | Settings, startup, events, ports and shared infrastructure |
| `app/domain/` | Framework-free findings and operation lifecycle vocabulary |
| `app/routers/` | HTTP and MCP transport adapters |
| `app/services/` | Application use cases: operations, tools, notifications, conversations and health/history |
| `app/integrations/` | ZAP, JMeter and Slack adapters |
| `app/dao/` | Operation persistence abstractions and concrete stores |
| `app/intelligence/` | LLM catalog, providers, credentials, inference and conversation infrastructure |
| `app/runtime/` | Isolated runtime entry points, currently the JMeter worker |

## Related Documents

[system-overview.md](system-overview.md) · [module-map.md](module-map.md) · [deployment-map.md](deployment-map.md)

## Last Updated

2026-08-28 — full repository tree re-review.
