# System Overview

## Purpose

Give AI assistants a current, evidence-based view of Guardrail Hub and clearly separate shipped capabilities from product ambition.

## Scope

The product code and infrastructure. AIOS mechanics are described in [`.ai/README.md`](../README.md).

## AI Usage Guidance

Use this document for orientation, then consult the narrower map for implementation work. Treat the root product README as direction, not proof that a feature exists.

## Main Content

Guardrail Hub is becoming a security and performance-testing orchestration platform. The substantially implemented subsystem is a Python FastAPI/MCP server. It currently orchestrates OWASP ZAP and Apache JMeter, persists operation state, manages self-registering worker pools, emits lifecycle notifications through a Slack-capable ChatOps layer, and exposes an LLM/conversation runtime with pluggable providers and credential backends.

| Area | Current reality |
|---|---|
| MCP server | Implemented for queued ZAP API scans, JMeter execution/result analysis, and operation queries. |
| HTTP API | Health, history, worker lifecycle, and conversation endpoints are implemented. |
| Intelligence | Provider registry/catalog, Ollama, OpenAI-compatible and Bedrock adapters, credentials, chat/stream/embed/rerank/vision service paths, conversations, and an operator CLI for provider setup and validated `llm.yaml` topology changes are implemented. Generic policy engines and provider health are incomplete. |
| Persistence | Operations use PostgreSQL or DynamoDB when configured and have no durable store in `NONE` mode. Conversations use memory in `NONE` mode and currently select the PostgreSQL store whenever an operation DAO exists, including DynamoDB mode. |
| ChatOps | Event-driven notification architecture and Slack adapter are implemented. |
| Web | A multi-page marketing/product site exists. It is not an operational Guardrail Hub dashboard and is not integrated with the backend. |
| Mobile/API/docs | Mobile and top-level API remain scaffolds; `docs/` is a documentation-site scaffold. |
| Security controls | Outbound secrets have production-aware handling, but inbound API authentication, authorization, policy enforcement, rate limiting, and durable audit enforcement are not implemented. |
| Product vision | Additional scanners, a unified dashboard, mobile client, broader governance, and enterprise controls remain targets. |

The main architectural boundary is deliberate: transport routers call application services; integrations and persistence sit behind ports or service boundaries; the domain layer owns framework-free findings and lifecycle vocabulary. `app/bootstrap.py` and startup code are composition roots and may wire concrete implementations.

## Related Documents

[project-map.md](project-map.md) · [module-map.md](module-map.md) · [codegraph.md](codegraph.md) · [security-map.md](security-map.md)

## Last Updated

2026-09-17 — full mapped-source re-review at `3632394`.
