# Dependency Graph

## Purpose

Record the intended dependency direction and major external runtime dependencies.

## Scope

Product architecture; package versions live in [technology-stack.md](technology-stack.md).

## AI Usage Guidance

Use this before introducing imports or new adapters. Dependencies should point toward stable domain/application abstractions, with concrete construction confined to composition roots.

## Main Content

### Backend direction

```text
routers (HTTP/MCP)
    -> application services
        -> domain + ports
        -> intelligence orchestration
        -> persistence/integration abstractions

concrete adapters
    -> ports/domain schemas

bootstrap.py + core/startup.py
    -> all concrete modules (composition-root exception)
```

Rules evidenced in code and architecture checks:

- `app/domain/` imports no framework or outer application package.
- Routers translate transport concerns and delegate to services.
- Service package roots are the normal public API; deep imports are primarily a composition-root privilege.
- Tool execution does not depend directly on Slack; lifecycle events feed a channel-neutral notification pipeline.
- `app/runtime/jmeter/` is isolated from server-owned services, persistence and composition code.
- ZAP and JMeter integrations remain engine-specific adapters; canonical findings/lifecycle terms live in the domain.

### Intelligence subgraph

```text
config/llm.yaml
  -> registry/catalog
  -> ProviderManager
      -> Ollama adapter
      -> OpenAI-compatible adapter
      -> Bedrock adapter

credential backend -> CredentialStore -> provider startup
ConversationService -> LLMService -> ProviderManager
```

### External systems

| Dependency | Used for |
|---|---|
| PostgreSQL | Operation queue/state and conversation persistence |
| DynamoDB | Alternative operation persistence |
| OWASP ZAP workers | DAST execution |
| Apache JMeter workers | Performance-test execution |
| Slack API | Optional lifecycle/status notifications |
| Ollama/OpenAI-compatible HTTP APIs/AWS Bedrock | LLM inference |

The web application is independently built and currently has no operational dependency on the Guardrail backend.

## Related Documents

[codegraph.md](codegraph.md) · [database-map.md](database-map.md) · [deployment-map.md](deployment-map.md)

## Last Updated

2026-08-28 — dependency directions re-reviewed from source and architecture rules.
