# Router Manifest — Tier 0

> **This is Tier 0: the one file (besides `guardrails/core.md`) loaded on every session.** It is a static lookup table, not prose to reason through. Its only job: classify an incoming task into a Domain, then point at that Domain's Router. Keep it small — it must stay a fast scan no matter how large `.ai/` grows. See [kernel/README.md](../kernel/README.md#context-budget--loading-strategy) and [router/README.md](README.md).

Skeleton created in Roadmap M1 ([Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)); the Backend Domain went live in M3. Format is established; further Domains register additively (M5).

## Lane Classification

Before consulting the Domain table, classify the task into a lane (per [kernel/README.md Startup Sequence](../kernel/README.md#startup-sequence)):

| If the task is… | Lane | Then |
|---|---|---|
| An ordinary product task (edit/add code in `mcp-server/`, `web/`, `mobile/`, …) | **Product** | Match a Domain below, load its Domain Router. |
| AIOS meta-work (author a Standard/Agent, change `.ai/` structure) | **Meta** | Load the Constitution (`foundation/`, full `kernel/`, `router/README.md`, `agents/README.md`); this table is not the entry point for meta-work. |
| From a tool/session with no prior AIOS context | **First-Contact** | Run [foundation/bootstrap.md](../foundation/bootstrap.md) once, then re-enter here. |

## Domain Table (Product Lane)

| Task pattern | Domain | Domain Router | Status |
|---|---|---|---|
| Code, config, or tests under `mcp-server/` (FastAPI, MCP tools, scanners, DAO) | Backend | [agents/backend/ROUTER.md](../agents/backend/ROUTER.md) | **Active** |
| Code, components, or config under `web/` (Next.js App Router, shadcn/ui, hooks) | Frontend | [agents/frontend/ROUTER.md](../agents/frontend/ROUTER.md) | **Active** |

Mobile, Security, Infrastructure, and others register here — one row each — only when their vertical slice is built, per [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)'s additive-expansion model. Adding a Domain row is the rarest routing change and the only event that mutates this Tier 0 file — but it is purely *additive* (a new row), never a change to the routing model itself, so it needs no RFC.

## No Match

If a Product-lane task matches no Domain row, this is the `no-capability-match` case: hand to [Kernel/Recovery](../kernel/recovery/README.md), treated as safety-relevant by default rather than dispatched to a best-guess Domain (see [router/README.md Unknown Request Handling](README.md#unknown-request-handling)).
