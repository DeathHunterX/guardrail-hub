# Module Map

## Purpose

Describe the ownership and maturity of product modules without requiring a full source-tree scan.

## Scope

`mcp-server/app/` and the meaningful modules under `web/`.

## AI Usage Guidance

Choose the owner by responsibility, then confirm its public API and tests before changing it. `bootstrap.py` is the intentional composition-root exception to normal import boundaries.

## Main Content

### Backend

| Module | Owns | Current state |
|---|---|---|
| `main.py` | FastAPI application and router mounting | Implemented |
| `bootstrap.py`, `core/startup.py` | Dependency construction, migrations, provider and worker startup | Implemented |
| `core/config/` | Typed environment settings split by concern | Implemented; several policy settings are not yet enforced at request boundaries |
| `core/events/`, `core/ports/` | In-process event contracts and infrastructure ports | Implemented |
| `domain/findings/`, `domain/lifecycle/` | Canonical domain concepts | Implemented and dependency-inward |
| `dao/` | Operation records, queue claims, PostgreSQL/DynamoDB persistence | Implemented |
| `integrations/owasp_zap/` | ZAP client and report parsing | Implemented |
| `integrations/jmeter/` | JMeter worker client/result integration | Implemented |
| `integrations/chat/slack/` | Slack notification transport | Implemented |
| `services/tools/owasp_zap/` | ZAP scan submission, dispatch and execution | API scan paths implemented; web/interactive scan endpoints remain placeholders |
| `services/tools/jmeter/` | JMeter submission, dispatch and analysis | Implemented |
| `services/operations/` | Operation lifecycle and event publication | Implemented |
| `services/notification/` | Channel-neutral notification rendering and dispatch | Implemented |
| `services/platform/`, `services/evaluations/` | Platform reporting and scan evaluation abstractions | Implemented supporting capabilities |
| `services/public/` | Health and history use cases | Implemented |
| `services/conversation/` | Conversation use cases and state transitions | Implemented |
| `intelligence/registry/`, `intelligence/catalog/` | Provider/model definitions and catalog validation | Implemented from `config/llm.yaml` |
| `intelligence/providers/` | Ollama, OpenAI-compatible and Bedrock adapters plus manager | Implemented outbound calls |
| `intelligence/credentials/` | Windows Credential Manager, mounted-file and environment backends | Implemented with platform-aware selection |
| `intelligence/inference/` | LLM service for chat, stream, embeddings, rerank and vision | Implemented; generic policy classes are incomplete |
| `intelligence/conversation/` | Conversation stores and orchestration support | PostgreSQL and in-memory implementations |
| `intelligence/health/` | Provider-health capability | Stub/incomplete |
| `runtime/jmeter/` | Isolated ASGI JMeter worker runtime | Implemented |
| `routers/mcp/` | MCP tool surface | Implemented, explicit operation whitelist |
| `routers/public/` | Health, history, workers and conversations HTTP API | Implemented; no inbound auth middleware |

### Web

| Module | Owns | Current state |
|---|---|---|
| `web/app/` | Next.js App Router pages and metadata | Implemented multi-page site |
| `web/features/` | Page/feature-level composition | Implemented |
| `web/components/` | Shared visual components | Implemented |
| `web/hooks/`, `web/lib/` | Reusable browser behavior and utilities | Implemented |
| Backend/API integration | Operational dashboard behavior | Not implemented; only limited external/site services exist |

## Related Documents

[project-map.md](project-map.md) · [codegraph.md](codegraph.md) · [dependency-graph.md](dependency-graph.md)

## Last Updated

2026-08-28 — full source-module re-review.
