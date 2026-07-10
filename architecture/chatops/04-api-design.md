# 5. API Design

> Design intent. Extends the existing FastAPI app ([`technology-stack.md`](../../.ai/intelligence/technology-stack.md)) and its `routers/{public,mcp,internal}` audience split ([`backend-layering` R2](../../.ai/standards/architecture/backend-layering.md)). No endpoint below exists yet except the ZAP scan path it generalizes.

## 5.1 API surfaces

The platform exposes four distinct surfaces, each an *adapter* over the same application core — never a separate implementation.

| Surface | Audience | Transport | Router bucket |
|---|---|---|---|
| **Guardrail API (command + query)** | ChatOps Service, CLI, CI | REST/JSON (+ optional gRPC internal) | `routers/public/` |
| **MCP tools** | AI assistants | MCP over the existing `/mcp` mount (`fastapi-mcp`) | `routers/mcp/` |
| **Inbound chat webhooks** | Slack/Discord/Teams platforms | Provider-specific signed HTTP | `routers/public/chatops/` |
| **Streaming** | Dashboard, CLI `--follow` | SSE (and WebSocket where duplex needed) | `routers/public/stream/` |

The key point: the ChatOps webhook router is *thin*. It verifies the provider signature, extracts the command, and calls the same application service the REST API calls. It shares one command path.

## 5.2 Command endpoints (write)

All writes are `POST`, all carry an `Idempotency-Key` header, all return `202 Accepted` with a `job_id` — because the work is asynchronous by nature.

```
POST /v1/projects/{project_id}/jobs
  headers: Idempotency-Key, Authorization
  body:    { "tool": "security_scan", "asset_id": "01J...", "params": {...}, "origin": "slack",
             "correlation": { "provider":"slack","channel_id":"C1","thread_ts":"169..." } }
  202: { "job_id": "01J...", "status": "CREATED", "poll": "/v1/jobs/01J...",
         "stream": "/v1/jobs/01J.../stream" }
  403 (problem+json) at admission if: asset_id is unregistered/unverified (unauthorized_target),
         the caller's chat identity is not VERIFIED (unverified_identity), or RBAC denies (rbac_denied).

POST /v1/jobs/{job_id}/cancel        -> 202  (emits UserCancelledJob)
POST /v1/jobs/{job_id}/retry         -> 202  (new job_id, links parent)
```

Idempotency contract: a repeated `Idempotency-Key` within the retention window returns the **original** `job_id` and `200`, never a second job. This is what makes chat — an at-least-once medium where a user double-clicks — safe.

## 5.3 Query endpoints (read)

```
GET /v1/jobs/{job_id}                 -> full Job projection
GET /v1/projects/{project_id}/jobs    -> ?status=&tool=&actor=&page=  (for /jobs, /status)
GET /v1/projects/{project_id}/history -> ?from=&to=&tool=            (for /history)
GET /v1/jobs/{job_id}/report          -> result_ref resolution       (for /report)
GET /v1/jobs/{job_id}/stream          -> SSE progress stream         (for --follow / dashboard)
GET /v1/projects/{project_id}/policies-> policy list                 (for /policy)
GET /v1/projects/{project_id}/benchmarks                             (for /benchmark)
```

Reads are served from **CQRS read projections** (see [database design](05-database-design.md#cqrs-read-model)), not by scanning the write store — essential at millions-of-jobs scale.

## 5.4 The ChatOps command → API mapping

The bot translates a slash command to exactly one API call. It never composes business logic across calls.

| Slash command | Maps to | Notes |
|---|---|---|
| `/run <tool> asset=<name> [params]` | `POST /jobs` | Requires a `VERIFIED` chat identity + a registered, `VERIFIED` asset; otherwise a friendly rejection. Returns ack + thread correlation. |
| `/status [job_id]` | `GET /jobs/{id}` or latest in channel | Renders the state machine snapshot. |
| `/jobs` | `GET /projects/{id}/jobs?status=active` | Paginated list. |
| `/history` | `GET /projects/{id}/history` | Time-ranged. |
| `/report <job_id>` | `GET /jobs/{id}/report` | Returns link to `result_ref`, not raw content (G1). |
| `/project <name>` | `GET/context switch` | Sets channel's default project (session state). |
| `/policy ...` | `GET /projects/{id}/policies` | Read-only from chat; edits go through the web app. |
| `/evaluation <tool>` | `POST /jobs` (evaluation tools) | Convenience alias of `/run`. |
| `/benchmark ...` | `POST /jobs` (`benchmark`) + `GET /benchmarks` | Launch or list. |
| `/help` | local | The only command that touches no API. |

> Per the brief, command **handlers are not implemented** here — this is the routing contract they will satisfy. Each handler is a `services/chatops/commands/<command>.py` unit whose sole job is: authorize → build DTO → call `GuardrailApiPort` → format ack.

## 5.5 Cross-cutting API concerns

- **AuthN:** provider signature (HMAC) on inbound webhooks; bearer token (the repo's declared-but-unused `pyjwt` becomes real here) on REST/MCP. Chat identity → Actor resolution happens in the ACL, once, at the edge.
- **AuthZ:** every command is checked against project-scoped RBAC *in the core*, never in the adapter (G2). A `403` maps to a friendly "you don't have permission" chat reply.
- **Versioning:** URI-versioned (`/v1`) for REST; integration events versioned independently (`.v1` suffix). The two version lines are decoupled.
- **Errors:** RFC 9457 `application/problem+json`; the adapter maps `type` → a channel-appropriate message.
- **Rate limiting:** per-org token bucket at the edge, returning `429` with `Retry-After`; the adapter surfaces this as "slow down" rather than erroring the thread.

## 5.6 Asset registry & identity linking (added for authorization)

Job creation now authorizes both *what* is targeted and *who* is asking — in the core, at admission, never in the adapter.

```
# Asset registry — the targets a job may reference (registration/verification are web-app/CLI flows; chat is read-only over assets)
GET    /v1/projects/{project_id}/assets          -> list registered assets
POST   /v1/projects/{project_id}/assets          -> register (status = PENDING)
POST   /v1/assets/{asset_id}/verify              -> submit proof-of-ownership -> VERIFIED

# Chat-identity linking — bind a chat user to an Actor, once
POST   /v1/identities/link/start                 -> issue one-time link code (authenticated web app)
POST   /v1/identities/link/confirm               -> confirm code from chat -> ChatIdentity VERIFIED
DELETE /v1/identities/{identity_id}              -> revoke (status = REVOKED)

# Admission rule (Guardrail API, not the adapter):
#   create_job REQUIRES  asset.ownership == VERIFIED
#                  AND   chat_identity.verification_status == VERIFIED (scoped to installation's org)
#                  AND   RBAC(actor, project, tool) allows
#   else -> 403 problem+json {unauthorized_target | unverified_identity | rbac_denied}
#           + emit command.rejected.v1 + audit CommandRejected
```

**Backward compatibility:** existing `/v1` read endpoints are unchanged; the only breaking change is the new required `asset_id` on job creation — a deliberate security fix, flagged in the [change summary](14-critical-remediations.md#change-summary). Read paths (`/status`, `/jobs`, `/history`, `/report`) keep their existing shapes.

Continue to [05-database-design.md »](05-database-design.md)
