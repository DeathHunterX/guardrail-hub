# Code Graph

## Purpose

Show entry points, composition, and the main runtime flows.

## Scope

Architectural relationships, not every function or class.

## AI Usage Guidance

Trace a requested change through the appropriate flow before editing. Keep transport, application, domain and adapter responsibilities separate.

## Main Content

### Entry points

| Entry point | Location | Role |
|---|---|---|
| Backend API/MCP | `mcp-server/app/main.py` | FastAPI app, routers, static reports and `/mcp` mount |
| Backend lifecycle | `app/core/startup.py` | Registry, credentials, providers, database, workers and notifications |
| Composition root | `app/bootstrap.py` | Constructs concrete services and adapters |
| JMeter worker | `app/runtime/jmeter/main.py` | Isolated ASGI assignment runtime |
| Web | `web/app/layout.tsx` and route pages | Next.js site |

### Startup flow

```text
FastAPI lifespan
  -> load settings and LLM registry
  -> select credential backend and build provider manager
  -> configure operation persistence and run PostgreSQL migrations when selected
  -> build shared OperationService + event/notification pipeline
  -> build ZAP and JMeter dispatchers/worker services
  -> build ConversationService (PostgreSQL store when available, otherwise memory)
  -> start registered providers and background lifecycle work
```

### Tool execution

```text
MCP or HTTP tool route
  -> tool application service validates/submits
  -> OperationService persists QUEUED and publishes lifecycle event
  -> engine dispatcher claims an operation and selects a live worker
  -> ZAP/JMeter adapter executes remotely
  -> progress/results persist through operation services
  -> event bus -> OperationNotifier -> NotificationService -> Slack (when enabled)
```

ZAP API, scenario and suite paths are wired. The web-application and interactive-session ZAP routes are HTTP-visible development placeholders and are deliberately excluded from MCP.

### Conversation/inference

```text
Conversation HTTP route
  -> ConversationService loads and transitions conversation state
  -> LLMService resolves model/provider through registry + ProviderManager
  -> provider adapter performs chat or streaming request
  -> turns/state history persist; stream is relayed to the client
```

`LLMService` also exposes embeddings, rerank and vision paths. Provider health and generic inference-policy abstractions remain incomplete.

### Architectural absences

No inbound authentication/authorization middleware protects these routes. Configured policy, rate-limit and audit concepts do not currently form an enforced request pipeline. Conversation audit events are in-process and no durable audit subscriber was found.

## Related Documents

[module-map.md](module-map.md) · [dependency-graph.md](dependency-graph.md) · [api-map.md](api-map.md)

## Last Updated

2026-08-28 — startup and execution paths re-traced from source.
