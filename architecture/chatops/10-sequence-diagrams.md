# 10. Sequence Diagrams

> Design intent. Illustrative flows for the target system.

## 10.1 End-to-end: `/run` a security scan, streamed to Slack

The canonical happy path — command in, long-running job, progress and completion out — showing why the request path and the event path are decoupled.

```mermaid
sequenceDiagram
    actor U as User
    participant SL as Slack
    participant SA as Slack Adapter
    participant CO as ChatOps Core
    participant API as Guardrail API
    participant Q as Job Queue
    participant W as Worker (Eval Engine)
    participant OB as Outbox
    participant BUS as Event Bus
    participant NS as Notification Svc

    U->>SL: /run security_scan asset=web-api
    SL->>SA: signed webhook
    SA-->>SL: 200 "⏳ launching…"
    SA->>CO: Command (verified identity)
    CO->>API: POST /jobs (asset_id, Idempotency-Key)
    API->>API: admission: asset VERIFIED + identity VERIFIED + RBAC
    API->>OB: insert job.created + audit (same txn as job row)
    API-->>CO: 202 {job_id}
    CO-->>SA: ack → thread "queued"
    OB-->>BUS: job.created.v1 (relay)
    API->>Q: enqueue
    Q->>W: lease job
    W->>OB: job.started + stage.started (spider)
    OB-->>BUS: job.started.v1, stage.started.v1
    BUS->>NS: events
    NS->>SL: edit thread "▶ running: spider"
    loop while scanning
        W->>W: progress
        W->>OB: job.progressed
        OB-->>BUS: job.progressed.v1
        BUS->>NS: (throttled ~5s)
        NS->>SL: edit thread "45% · active_scan · ETA 6m"
    end
    W->>OB: job.completed (result_ref)
    OB-->>BUS: job.completed.v1
    BUS->>NS: event
    NS->>SL: final card "✅ done · 3 findings · report ↗"
```

## 10.2 Idempotent double-submit (chat retry)

Why a double-tap or a Slack redelivery never launches two scans.

```mermaid
sequenceDiagram
    participant SA as Slack Adapter
    participant CO as ChatOps Core
    participant API as Guardrail API
    participant DB as DAO

    SA->>CO: Command (retry of same interaction)
    CO->>API: POST /jobs (Idempotency-Key = K)
    API->>DB: conditional insert (UNIQUE project_id,K)
    DB-->>API: conflict → existing job_id
    API-->>CO: 200 {job_id, status: existing}
    CO-->>SA: "already running (Job 01J…)"
```

## 10.3 Security regression alert with escalation

A Policy-context judgement fanning out, with `critical` bypassing quiet hours.

```mermaid
sequenceDiagram
    participant EE as Eval Engine
    participant POL as Policy Engine
    participant OB as Outbox
    participant BUS as Event Bus
    participant NS as Notification Svc
    participant SL as Slack #sec-alerts
    participant PD as PagerDuty (on-call)

    EE->>POL: findings + baseline
    POL->>POL: compare → jailbreak succeeded
    POL->>OB: security.jailbreak.detected (critical)
    OB-->>BUS: security.jailbreak.detected.v1
    BUS->>NS: event
    NS->>NS: route(#sec-alerts) + escalate(on-call)
    NS->>NS: severity=critical → bypass batching & quiet hours
    NS->>SL: alert card (transcript_ref, not inline)
    NS->>PD: page on-call
    NS->>BUS: NotificationSent (audit)
```

## 10.4 Cancellation from chat

Cooperative cancel via a button interaction.

```mermaid
sequenceDiagram
    actor U as User
    participant SL as Slack
    participant SA as Slack Adapter
    participant CO as ChatOps Core
    participant API as Guardrail API
    participant R as Redis
    participant W as Worker

    U->>SL: click [Cancel] on job card
    SL->>SA: interaction payload
    SA->>CO: CancelCommand(job_id)
    CO->>API: POST /jobs/{id}/cancel
    API->>R: set cancel flag job:{id}
    API-->>CO: 202
    CO-->>SA: "cancelling…"
    W->>R: check flag at stage boundary
    R-->>W: cancel = true
    W->>W: stop, emit job.cancelled
    Note over W,SL: job.cancelled.v1 → Notif → thread "🛑 cancelled"
```

## 10.5 Adding a new channel (Teams) — no core change

Not a runtime flow, but the *change* flow the architecture optimizes for.

```mermaid
sequenceDiagram
    participant Dev as Platform Dev
    participant Repo as Codebase
    participant BUS as Event Bus (unchanged)
    Dev->>Repo: add TeamsAdapter implements NotificationChannelPort
    Dev->>Repo: add Teams template variants
    Dev->>Repo: register channel binding + prefs
    Note over Repo,BUS: API, Job Svc, Eval Engine, event schemas: untouched
    BUS->>Repo: existing events now also deliver to Teams
```

## 10.6 Verified account linking + rejected target (admission)

Closes the two identity/target Criticals. Part 1: one-time verified linking. Part 2: an unregistered target is refused at admission — an unverified identity would be refused the same way.

```mermaid
sequenceDiagram
    actor U as User
    participant Web as Web App (authenticated)
    participant SL as Slack
    participant CO as ChatOps Core
    participant API as Guardrail API
    Note over U,API: 1 — verified account linking (once)
    U->>Web: request link code
    Web->>API: POST /identities/link/start
    API-->>U: one-time code
    U->>SL: /link <code>
    SL->>CO: confirm
    CO->>API: POST /identities/link/confirm
    API-->>CO: ChatIdentity VERIFIED (scoped to installation's org)
    Note over U,API: 2 — later, an unregistered target
    U->>SL: /run security_scan asset=unknown-host
    SL->>CO: command (verified identity)
    CO->>API: POST /jobs (asset_id?)
    API->>API: asset not VERIFIED
    API-->>CO: 403 unauthorized_target (+ command.rejected.v1 + audit CommandRejected)
    CO->>SL: "⛔ target not registered / verified"
```

Continue to [11-deployment.md »](11-deployment.md)
