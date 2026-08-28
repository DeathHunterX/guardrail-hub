# Glossary

## Purpose

Define project-specific terms consistently for people and AI assistants.

## Scope

Current product and AIOS vocabulary.

## AI Usage Guidance

Prefer these terms in code and documentation. When a transport/tool uses a different wire term, translate it at the adapter boundary.

## Main Content

| Term | Meaning in Guardrail Hub |
|---|---|
| AIOS | The repository's AI Operating System under `.ai/`: rules, routing, contracts, current-state intelligence and deterministic checks. |
| Product Lane | Ordinary work in product directories; loads Tier G plus a routed domain-specific context. |
| Meta Lane | Work that changes the AIOS itself. |
| Intelligence | Current-state repository facts under `.ai/intelligence/`; not the same as the backend LLM runtime. |
| Intelligence runtime | Backend capabilities under `app/intelligence/` for models, providers, credentials, inference and conversations. |
| Operation | Durable asynchronous unit of ZAP/JMeter work, identified by an operation ID and lifecycle phase. |
| Operation phase | Canonical lifecycle vocabulary owned by `app/domain/lifecycle/`. |
| Finding | Canonical tool-neutral security finding owned by `app/domain/findings/`. |
| Worker | A registered executable instance capable of receiving engine-specific work. |
| Worker registry | In-process directory of live workers and their heartbeat/scheduling state. |
| Dispatcher | Application component that claims queued work, selects a worker and coordinates execution. |
| ZAP worker | OWASP ZAP instance registered with the control plane for DAST work. |
| JMeter worker | Isolated ASGI runtime that receives and executes performance-test assignments. |
| Provider | Concrete LLM inference backend such as Ollama, OpenAI-compatible HTTP, or Bedrock. |
| Provider Manager | Runtime owner that resolves and invokes configured provider adapters. |
| Registry/catalog | Validated provider and model definitions built from `mcp-server/config/llm.yaml`. |
| Credential backend | Platform/storage mechanism used to retrieve provider secrets. |
| Conversation | Stateful sequence of messages and transitions orchestrated by `ConversationService`. |
| ChatOps | Event-driven lifecycle/status delivery through a channel-neutral notification layer, currently with Slack support. |
| MCP tool | Only an HTTP operation whose operation ID is explicitly included in `MCP_OPERATIONS`. |
| Composition root | `bootstrap.py`/startup code that is allowed to know and assemble concrete implementations. |
| Drift | A mismatch between an Intelligence document's recorded source hash and current Git-visible source state; it requires re-review, not blind baseline acceptance. |
| Planned | Described as a target but not evidenced as working code. |

## Related Documents

[system-overview.md](system-overview.md) · [module-map.md](module-map.md) · [MAINTENANCE.md](MAINTENANCE.md)

## Last Updated

2026-08-28 — terminology re-reviewed against current product and AIOS.
