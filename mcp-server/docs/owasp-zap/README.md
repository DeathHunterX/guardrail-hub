# OWASP ZAP Tools — Overview & Decision Guide

The ZAP integration exposes three security-scanning tools as MCP tools. They
share one authentication model, one queue/worker pipeline, and one report style,
so learning one makes the others easy. This page helps you pick the right tool;
each tool has its own full reference.

| Tool | Scan unit | Auth | Use it when | Reference |
|---|---|---|---|---|
| `scan_api` | one endpoint | single request | You have a single URL + method to test | [scan_api.md](scan_api.md) |
| `scan_api_scenario` | an ordered workflow | multi-step (login → …) | Endpoints need an authenticated, stateful sequence | [scan_api_scenario.md](scan_api_scenario.md) |
| `scan_api_suite` | a whole application | per-category defaults | You have many services/specs to scan as one app | [scan_api_suite.md](scan_api_suite.md) |

## Decision tree

```
Do you need to scan more than one endpoint?
│
├─ No ──────────────────────────────► scan_api
│        (one URL + method, optional auth)
│
└─ Yes
   │
   ├─ Are the endpoints a single authenticated WORKFLOW
   │  (each step depends on state/tokens from the previous step,
   │   e.g. Login → Get Profile → Create Order → Checkout → Logout)?
   │        │
   │        └─ Yes ─────────────────► scan_api_scenario
   │
   └─ Are they multiple independent SERVICES / OpenAPI specs
      that together form one application
      (Authentication, Users, Orders, Payments)?
             │
             └─ Yes ────────────────► scan_api_suite
```

Quick heuristics:

- One endpoint → **scan_api**.
- "I must log in first, then hit these endpoints in order" → **scan_api_scenario**.
- "Here are 4 OpenAPI files for my app's services" → **scan_api_suite** (which
  internally runs many `scan_api` scans in parallel).

## Common concepts (shared by all three)

- **Asynchronous by design.** Every tool returns immediately with an
  `operation_id` and `status: queued`. A background Dispatcher assigns the work
  to a ZAP worker when one is free. Poll results with
  `GET /api/history/get-result?operation_id=<id>`.
- **Scan mode.** `quick` = spider + fast active scan of URL params (good for CI
  gates). `full` = context-scoped active scan including body fuzzing (thorough,
  pre-release).
- **Authentication.** Provide a `token` (with `token_type` = `bearer` | `jwt` |
  `access_token` | `custom`) and/or a `cookie`. See each tool's Authentication
  section for exact fields and examples.
- **Reports.** Single scans produce ZAP's HTML + JSON. The suite additionally
  produces an aggregated application report in **Markdown**, **JSON**, and
  **SARIF 2.1.0** — same findings, three formats.

## Tool comparison

| Aspect | scan_api | scan_api_scenario | scan_api_suite |
|---|---|---|---|
| Execution strategy | worker-bound (SEQUENTIAL) | worker-bound (SEQUENTIAL) | orchestration (FAN_OUT) |
| Occupies a worker | yes (1) | yes (1) | no — children do |
| Parallelism | — | — | yes, across the pool |
| Input | 1 target | ordered `steps` | `categories` of OpenAPI specs |
| Auth | per request | captured + propagated across steps | per-category `defaults` |
| Output | ZAP HTML + JSON | ZAP HTML + JSON | aggregated MD + JSON + SARIF |
| Report scope | endpoint | workflow endpoints | application (exec + category + findings) |

## Where things live (for contributors)

- Request models: `app/schemas/tools/owasp_zap/`
- Services (submit + execute): `app/services/tools/owasp_zap/`
- Generic execution layer (frozen): `app/services/tools/owasp_zap/execution/`,
  `.../worker/`
- Architecture docs: `architecture/zap-generic-execution/`
