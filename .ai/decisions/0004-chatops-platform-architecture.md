# 0004 — ChatOps Platform Architecture

Status: **Proposed**
Owner: Loi Phan
Date: 2026-07-07

---

## Context

Guardrail Hub's roadmap names Slack, Discord, Microsoft Teams, Email, Webhooks, Grafana, and Prometheus as future integrations, all driven by long-running jobs (Security Scan, Prompt Evaluation, Benchmark, Hallucination / Prompt-Injection / Jailbreak / PII / Toxicity detection, Agent Evaluation). Today only one execution path exists in code — the MCP server's OWASP ZAP integration ([intelligence/system-overview.md](../intelligence/system-overview.md)); there is no Job Service, Event Bus, queue, worker tier, or notification system.

A ChatOps capability could be built two ways: as a self-contained bot that talks to scanners and databases directly, or as a thin adapter over a domain core. The first is faster to a demo but puts business logic (what a scan is, what a regression means, how to route work) inside the bot — which then has to be re-implemented for every new channel and cannot be reused by the API, CLI, or CI. In a security product this also risks a channel handler fabricating or mis-relaying a posture claim, a guardrail concern ([guardrails/core.md](../guardrails/core.md) G3/G5).

The existing backend already establishes the discipline this decision must respect: one-directional layering `routers → services → integrations|dao`, a per-tool folder convention, a hand-written pluggable DAO (Postgres/DynamoDB, no ORM), and an anti-pattern rule against business logic in routers ([standards/architecture/backend-layering.md](../standards/architecture/backend-layering.md), [persistence-dao.md](../standards/architecture/persistence-dao.md)).

## Decision

**Build the ChatOps platform as a pure adapter layer over an event-driven core, using Hexagonal (Ports & Adapters) Architecture. Business logic lives only inside Guardrail Hub; the bot never contains it.** Full design: [architecture/chatops/](../../architecture/chatops/README.md).

Concretely:

- **Hexagonal boundary.** Chat surfaces (Slack/Discord/Teams/CLI) are *driving adapters*; notification channels and the Guardrail API client are *driven adapters*. The application core depends only on ports (`ChatCommandPort`, `NotificationChannelPort`, `GuardrailApiPort`, `EventPublisherPort`, `JobQueuePort`). Adding a channel or tool satisfies existing ports with zero core change.
- **Event-driven spine.** Components communicate through versioned integration events on a partitioned bus (partition key `org_id`), published via the transactional **outbox** pattern. New integrations subscribe as new consumer groups; they never modify producers.
- **Two bounded contexts owned by the platform** — ChatOps and Notification — both adapter-only. Job Orchestration, Evaluation, Policy & Governance, Identity, and Audit remain in the core.
- **Async command path.** Commands return `202` immediately with a `job_id`; all subsequent updates reach users via bus → Notification, decoupling the 3-second chat-ack window from tens-of-minutes jobs.
- **Idempotency end-to-end.** Every command carries an idempotency key enforced at the DB (Postgres `UNIQUE` / DynamoDB conditional put), because chat is an at-least-once medium.
- **Fits the existing layout.** No new top-level architectural role: ChatOps = `services/chatops` + `routers/public/chatops` + `integrations/chat`; persistence stays behind the DAO with both providers. Observability (Prometheus/Grafana/OTel) and metrics/audit are derived from the same event stream.

## Rationale

- **The adapter constraint is the whole value.** Keeping domain logic in the core means the API, CLI, CI, and every chat channel reuse one implementation, and a new channel is additive. Putting logic in the bot would force re-implementation per channel and couple integrations to internals.
- **Hexagonal generalizes the repo's own rule.** The existing "no business logic in routers" anti-pattern and one-directional dependency rule *are* ports-and-adapters at function scale; adopting hexagonal for a many-integrations subsystem is continuous with established convention, not a new paradigm.
- **Event-driven is required by the workload, not chosen for fashion.** Jobs are long-running with many independent consumers (notifications, audit, metrics, streaming, webhooks). Synchronous calls would block the chat-ack window and couple every subscriber to the core.
- **Outbox + versioned events protect posture integrity.** Atomic state-and-event writes and replayable, traceable events uphold G3/G5 (no fabricated or silently-lost posture) far better than best-effort in-handler calls.
- **Reuses the existing stack.** FastAPI, `fastapi-mcp`, pluggable DAO, and the declared-but-unused `pyjwt`/`bcrypt` are extended, not replaced — minimizing new surface.

## Alternatives Rejected

| Alternative | Why rejected |
|---|---|
| **Self-contained bot with direct DB/scanner access** | Puts business logic in the adapter, violating the central constraint and `backend-layering`; forces per-channel re-implementation; a channel handler could mis-state security posture (G3/G5). |
| **Synchronous request/response (bot waits for job)** | A scan runs for minutes; chat platforms demand a ~3s ack. Would either time out or hold connections open at scale; couples subscribers to the request path. |
| **Point-to-point integrations (no event bus)** | Every new channel/subscriber requires editing producers — the opposite of the required "subscribe without modifying the core" property; N×M coupling. |
| **Single shared queue for all tools** | A flood of cheap checks starves expensive scans; no independent scaling. Rejected for per-tool queues + fair scheduling. |
| **New top-level `chatbot/` module** | A genuinely new architectural role is a Decision-level change ([backend-layering Exceptions](../standards/architecture/backend-layering.md)); ChatOps fits existing roles, so a new top-level folder is unwarranted structure. |
| **Adopt an ORM for the new tables** | Contradicts the repo's explicit no-ORM/hand-DAO posture and its `DATABASE_PROVIDER` pluggability. |

## Consequences

- A design doc set lands at [architecture/chatops/](../../architecture/chatops/README.md) covering all 17 required deliverables; it is design intent, not implemented code, and is labelled as such per G5.
- Implementation follows an evolutionary path (spine → first channel → breadth → scale-out); the ZAP execution path generalizes into the worker/tool model rather than being discarded.
- New infrastructure becomes required as the platform grows: an event bus (Kafka/Redpanda or NATS JetStream), Redis (sessions/throttle/live state), a worker tier, and eventually K8s + CI/CD (both absent today) — each introduced only when its step is reached.
- `pyjwt`/`bcrypt` (currently declared-unused) and token/authz controls become real; this touches security-sensitive surface and any activation is subject to guardrail review (G2).
- This decision governs *architecture*. Command handlers, concrete schemas, and infrastructure choices per deployment profile are follow-on decisions when built.

## Critical remediations applied (pre-acceptance, 2026-07-07)

An architecture-review-board gate ([REVIEW-BOARD.md](../../architecture/chatops/REVIEW-BOARD.md)) raised four **Critical** findings. They were resolved **in the design** while this decision remains **Proposed** (not Accepted); details in [14-critical-remediations.md](../../architecture/chatops/14-critical-remediations.md):

1. **Target authorization / SSRF** — a Job may only reference a registered, ownership-`VERIFIED` **Asset**; free-text targets from chat are rejected at admission. New `Asset` aggregate + Asset Registry context; admission enforced in the Guardrail API.
2. **Chat-identity spoofing** — a `ChatIdentity` must be `VERIFIED` via one-time linking and is scoped by an `Installation` to exactly one org; unverified/cross-org identities cannot act.
3. **Audit hash-chain vs at-least-once stream** — the ledger is now written transactionally with a per-tenant monotonic `tenant_seq`; the hash chain is ordered by that sequence, not by bus delivery. The bus carries only *derived* audit projections.
4. **Air-gapped ≠ cloud chat** — channels are classed cloud vs self-hostable; the air-gapped profile runs Mattermost/email/webhooks behind the same `NotificationChannelPort`. No core change.

All four are additive and backward-compatible except one deliberate breaking change: job creation now requires `asset_id`. The remaining review-board High/Medium findings are tracked as open questions and do not gate this decision's *architecture*, but must be resolved before GA.

## Evolution Points (MVP scoping)

The MVP / Foundation stage implements a Modular Monolith and defers parts of the North Star per [EVOLUTION-PLAN.md](../../architecture/chatops/EVOLUTION-PLAN.md) and [MVP-SCOPE.md](../../architecture/chatops/MVP-SCOPE.md). Deferred capabilities are recorded here rather than as empty folders in the codebase (per the [folder refactor](../../architecture/chatops/FOLDER-STRUCTURE-REFACTOR.md)):

- **Persistence provider — pluggability already realized in code.** Reconciliation against the current codebase (the source of truth) shows the pluggable-provider seam already exists as `dao/base.py` (an `ABC` interface) selected by `dao/operation_dao.get_operation_dao()` via `settings.database_provider`. **Both PostgreSQL and DynamoDB adapters are implemented and retained** — the earlier "remove DynamoDB" note is withdrawn to avoid breaking working code. MVP runs with `DATABASE_PROVIDER=POSTGRES`; DynamoDB stays available behind the same interface. Persistence ports live in `dao/` (not `core/ports/`), per the existing convention. See [MVP-FOUNDATION-RECONCILIATION.md](../../architecture/chatops/MVP-FOUNDATION-RECONCILIATION.md).
- **Deferred subsystems live in the roadmap, not the filesystem.** `workers/` (distributed execution), `routers/public/stream/` (SSE streaming gateway), and CQRS `projectors/` are Stage 2–3 components; they are documented in the Evolution Plan and removed from the MVP tree to avoid implying intent that does not yet exist. Each re-enters behind an existing port (`JobQueuePort`, event ports) without restructuring.

These are organizational/scoping notes; they do not change the North Star architecture, which remains as decided above.

## Related Documents

[architecture/chatops/](../../architecture/chatops/README.md) · [guardrails/core.md](../guardrails/core.md) · [standards/architecture/backend-layering.md](../standards/architecture/backend-layering.md) · [standards/architecture/persistence-dao.md](../standards/architecture/persistence-dao.md) · [intelligence/system-overview.md](../intelligence/system-overview.md) · [intelligence/technology-stack.md](../intelligence/technology-stack.md)
