# Database Map

## Purpose

Describe persisted state, stores and schema ownership.

## Scope

Operation and conversation persistence in `mcp-server`; generated report files are noted but are not a database.

## AI Usage Guidance

Check both configured database modes before changing operation data. PostgreSQL migrations are the schema source of truth; there is no ORM migration layer.

## Main Content

### Operation records

Operations are the durable unit for asynchronous ZAP/JMeter work. Records carry an operation ID, batch/tool type, lifecycle status, request/result/error payloads, timestamps, and worker/queue metadata used for claiming and recovery.

| Backend | Implementation | Notes |
|---|---|---|
| PostgreSQL | DAO plus SQL migrations | Preferred relational path; transactional queue claims and queue index are implemented. |
| DynamoDB | DAO implementation | Alternative operation store selected by configuration. |
| In-memory/runtime registries | Worker registries | Worker presence and leases are process-local, not durable business history. |

PostgreSQL migrations currently establish the operations table, queue-oriented indexing/claim support, and conversations.

### Conversations

Conversation persistence stores conversation identity, state, messages/turns and state-transition history. Startup currently selects:

- In-memory store when `DATABASE_PROVIDER=NONE`; this is ephemeral and unsuitable for durable multi-instance operation.
- PostgreSQL store whenever an operation DAO exists. This is correct for `POSTGRES`, but the current wiring also selects it for `DYNAMODB`; there is no DynamoDB conversation-store adapter.

Conversation redaction updates stored message content through the conversation service. Published audit events are in-process; persistence of conversation data must not be mistaken for a durable, tamper-evident audit log.

### File outputs

Scan reports and public artifacts are written under the configured public/report directory and served at `/public`. Their lifecycle is separate from database records.

### Known data constraints

- No cross-store transaction spans operation persistence, notifications and external engines.
- DynamoDB operation mode does not provide a matching conversation store; conversation wiring still depends on PostgreSQL.
- Worker registration is not a durable service-discovery system.
- The application owns SQL directly rather than through an ORM.
- Multi-instance behavior depends on the selected durable backend and is not provided by in-memory conversation/worker state.

## Related Documents

[codegraph.md](codegraph.md) · [deployment-map.md](deployment-map.md) · [security-map.md](security-map.md)

## Last Updated

2026-09-17 — DAOs, migrations and conversation-store selection re-reviewed at `3632394`.
