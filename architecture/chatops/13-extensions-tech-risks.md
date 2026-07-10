# 13. Extensions · Technologies · Risks · Trade-offs · Best Practices

> Design intent and recommendations.

## Future Extension Points

The architecture is designed so each of these is an *addition*, not a *modification* — the open/closed principle at the system level.

| Extension | How it plugs in | Core changes |
|---|---|---|
| **New chat channel** (Teams, Discord, Mattermost, Google Chat) | Implement inbound adapter (driving) + `NotificationChannelPort` (driven) + templates | None |
| **New Evaluation tool** | Add `schemas/tools/<tool>/`, `services/tools/<tool>/`, `integrations/<tool>/`, a worker slice (ZAP layout, R3) | None to ChatOps/Notification — `tool` is data |
| **New notification target** (PagerDuty, Opsgenie, SMS, Jira) | New consumer group on `security.*`/`job.*` + one channel adapter | None to producers |
| **New event subscriber** (SIEM export, data lake, billing meter) | New consumer group; read at own offset | None |
| **New API consumer** (CI plugin, IDE extension, GitHub App) | New driving adapter over the Guardrail API | None |
| **Observability backends** (Datadog, New Relic) | OTel exporter swap | None |
| **Scheduled/recurring scans** | A scheduler service that submits jobs via the same API | None |
| **Approval workflows** | An interaction command + a policy gate in the core | Core only, not adapters |

The single rule that keeps this true: **new integrations subscribe to events and implement ports; they never edit producers or the core.** ([Event catalog §4.6](03-event-catalog.md#46-how-a-new-integration-subscribes-without-touching-the-core).)

## Recommended Technologies

Chosen to **extend the existing stack** ([`technology-stack.md`](../../.ai/intelligence/technology-stack.md)) rather than replace it.

| Concern | Recommendation | Why (vs. alternative) |
|---|---|---|
| Language / framework | **Python 3.12 + FastAPI** (existing) | Already the backend; async-native; keeps one stack. |
| MCP exposure | **`fastapi-mcp`** (existing) | Already mounted; AI-assistant surface for free. |
| Event bus | **Kafka/Redpanda** (SaaS/Enterprise), **NATS JetStream** (self-hosted) | Durable, partitioned, replayable. Redpanda = Kafka API without JVM; NATS = lighter for small deploys. RabbitMQ rejected: weaker replay/log semantics for event sourcing. |
| Job queue | **Redis Streams** default, **SQS** on AWS | Consumer groups + visibility timeout without new infra (Redis already needed for sessions). Celery rejected as too opinionated/heavy for per-tool sandboxed scans. |
| Cache / live state / throttle | **Redis** | One tool for sessions, dedupe, throttle buckets, live progress. |
| Persistence | **Postgres + DynamoDB via existing DAO** | Honors `DATABASE_PROVIDER` pluggability; no ORM per repo rule. |
| Blob store | **S3-compatible** (S3/MinIO) | Reports/transcripts off the hot path; MinIO for self-hosted. |
| Streaming to clients | **SSE** (WebSocket where duplex needed) | SSE is simpler, proxy-friendly, sufficient for one-way progress. |
| Observability | **OpenTelemetry → Prometheus + Grafana + Tempo/Loki** | Exactly the brief's named integrations; vendor-neutral. |
| Orchestration | **Kubernetes + Helm**, **KEDA** for workers | Per-tool autoscaling on queue lag; Compose retained for self-hosted. |
| Secrets | **Vault / cloud KMS**, `.env` for local | Upholds **G1**; never secrets in source. |
| Auth | **`pyjwt`** (already declared) + provider HMAC | Activates the currently-unused JWT dependency for real. |

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **Business logic leaks into adapters** over time | Erodes the core constraint; the bot becomes un-maintainable | Enforce via `backend-layering` anti-pattern checks in `aios check`/CI; code review gate; ports make the wrong thing hard to write. |
| **Notification storms** (mass regression → thousands of messages) | Users muted; rate-limit bans from Slack | Throttle + batch + per-destination caps + circuit breaker ([doc 08](07-notification-architecture.md)). |
| **Chat as at-least-once medium** → duplicate jobs | Wasted compute, confusion | Idempotency keys end-to-end; DB uniqueness/conditional-put. |
| **PII/secret leakage via a notification** | Security incident in a *security* product (violates G1) | Redact at source; templates reference artifacts, never inline; log redaction. |
| **Event schema drift** breaks subscribers | Silent notification/metric loss | Versioned `.v1` integration events; backward-compatible evolution; schema registry. |
| **Outbox relay lag / failure** | "Ghost" jobs — done in DB, no notification | `ghub_outbox_lag_seconds` alert; relay HA; at-least-once + dedupe. |
| **Noisy-neighbor tenant** at 100k orgs | One org starves others | `org_id` partitioning + weighted-fair scheduling + per-org rate limits. |
| **Fabricated/relayed-wrong posture** | Trust collapse (violates G3) | Alerts trace to real Policy-context judgements; posture dashboards sourced only from real events. |
| **Greenfield scope vs. thin current codebase** | Over-building ahead of product | Evolutionary path ([deployment §11.4](11-deployment.md#114-path-from-today-to-target-evolutionary-not-big-bang)); ship the spine before the breadth. |
| **Scanner sandbox escaping / scanning wrong target** | Legal/security exposure (violates G4) | Per-scan sandbox, egress allow-list, explicit target authorization before run. |

## Trade-offs

| Decision | We gain | We give up | Why the trade is right here |
|---|---|---|---|
| **Event-driven + outbox** over synchronous calls | Decoupling, extensibility, resilience, replay | Eventual consistency; more moving parts; harder local reasoning | The workload is long-running and multi-subscriber; sync would block Slack's 3s window and couple every integration to the core. |
| **CQRS read projections** | Fast lists at millions-of-jobs scale | Read lag; projector to maintain | `/jobs`/`/history` must be instant; write store can't serve them cheaply. |
| **Hexagonal ports/adapters** | Channels/tools are pluggable; testable core | More interfaces/indirection; boilerplate | The system's raison d'être is many external integrations — exactly what hexagonal optimizes. |
| **Per-tool queues + workers** | Isolation, independent scaling | More queues/pools to operate | Prevents cheap jobs starving expensive scans; matches per-tool `integrations/<tool>/` model. |
| **Pluggable Postgres/DynamoDB via hand DAO** (no ORM) | Deployment flexibility; matches repo rule | Hand-written mapping; two impls to test | Already the repo's chosen posture; SaaS vs. self-hosted need different stores. |
| **Redis for live progress**, DB only on transitions | DB not hammered by progress spam | Live state is ephemeral if Redis drops | Progress is cheap-to-recompute; durable events still record transitions. |
| **Throttled chat vs. real-time dashboard**, same data | No chat spam; dashboards stay live | Chat is slightly behind the dashboard | Chat surfaces can't take 200 edits; users prefer coalesced updates. |

## Best Practices

1. **Keep the adapter dumb.** If a change adds a domain `if` to an adapter, it's in the wrong layer. Guard this in review and CI (`aios check`).
2. **One correlation id everywhere.** `job_id` = event key = trace id anchor = log field. Never invent a second one.
3. **Idempotency by default** on every command and every delivery — assume at-least-once everywhere.
4. **Publish through the outbox**, never a bare "write DB then call bus." Atomicity or bust.
5. **Version integration events** (`.v1`); evolve additively; break only via a new version.
6. **Redact at the source**, not at the edge — a payload that never contained a secret can't leak one (G1).
7. **Derive audit and metrics from the event stream**, not from hand-placed counters, so posture data can't disagree with reality (G3/G5).
8. **Fail loud, degrade gracefully:** DLQs and alerts for the invisible failures (outbox lag, notification exhaustion); back-pressure over collapse under load.
9. **Least privilege for scans:** explicit target authorization, sandboxed execution, egress allow-lists (G4).
10. **Label planned vs. built.** In a security product, an unearned "it works" is a liability — mark design intent as design intent (G5), exactly as this document set does.

← Back to [README / index](README.md) · Related decision: [ADR 0004](../../.ai/decisions/0004-chatops-platform-architecture.md)
