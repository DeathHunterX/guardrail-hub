# Glossary

## Purpose
Define product- and codebase-specific terms so an AI assistant doesn't have to infer meaning from context every time one appears.

## Scope
Terms specific to Guardrail Hub the product and its codebase. Does not redefine AIOS terminology (Kernel, Router, Agent, etc.) — see [`.ai/foundation/vision.md`](../foundation/vision.md) and [`.ai/foundation/architecture.md`](../foundation/architecture.md) for those.

## AI Usage Guidance
Consult this when a term in code, config, or the root README is unfamiliar or ambiguous before guessing its meaning. Terms are grouped by theme, not alphabetically, since related terms are more useful read together.

## Main Content

### Product Concepts

| Term | Meaning |
|---|---|
| **Guardrail Hub** | The product: a security testing and QA orchestration platform connecting multiple scanning tools behind one workflow (web dashboard, mobile app, MCP server). |
| **MCP (Model Context Protocol)** | The protocol Guardrail Hub uses to expose scanning tools to AI assistants as callable operations. Implemented via the `fastapi-mcp` package, mounted at `/mcp` in `app/main.py`. |
| **Tool Gateway** | A README-described concept: the layer that would broker access to all scanning tools with policy enforcement and audit logging. Not implemented — `app/client/`, `app/policies/`, `app/runner/` are empty. |
| **Runner** | A README-described concept: the execution environment(s) that actually run scanning tools (ZAP, Semgrep, etc.). Only the ZAP "runner" (a Docker container) is implemented; the generic Runner abstraction doesn't exist in code. |
| **Scan Run / Operation** | A single execution of a scanning tool against a target. Represented in code as an `OperationRecord`. |
| **Batch Type** | A category tag for an Operation (`app/constants/batch.py`, `BatchType` enum) — used to group/list operations (e.g., by tool). |
| **Tool Registry** | A README-described dashboard concept for managing which tools are available. Not implemented in code. |
| **Finding** | A README-described concept for an individual issue a scan discovers (e.g., a vulnerability). Represented today only within ZAP-specific results as `ZapAlert`/`ZapAlertInstance` — there is no tool-agnostic Finding model yet. |

### Scanning Terms

| Term | Meaning |
|---|---|
| **DAST** | Dynamic Application Security Testing — testing a running application (Guardrail Hub's implemented example: OWASP ZAP). |
| **SAST** | Static Application Security Testing — analyzing source code without running it (planned tool: Semgrep; not implemented). |
| **IaC scanning** | Scanning Infrastructure-as-Code files for misconfigurations (planned tool: Checkov; not implemented). |
| **SARIF** | Static Analysis Results Interchange Format — a standard report format the README names as a target output format. Not currently produced by any implemented code (ZAP reports are generated as HTML/JSON, not SARIF). |
| **OWASP ZAP** | Zed Attack Proxy — the one fully-implemented scanner. Runs as a Docker container (`zaproxy/zap-stable` image); driven via its REST API by `ZapClient`. |
| **Spider / Active Scan / Passive Scan** | ZAP-specific scan phases (crawling, active vulnerability probing, passive observation) — terms that appear in ZAP SDK usage and settings (`ZAP_SPIDER_TIMEOUT_SECONDS`, etc.). |

### Codebase-Specific Terms

| Term | Meaning |
|---|---|
| **DAO** | Data Access Object — this codebase's persistence pattern (hand-written classes wrapping `psycopg2`/`boto3`), used instead of an ORM. See [database-map.md](database-map.md). |
| **`DATABASE_PROVIDER`** | Env var selecting which DAO backend is active: `NONE`, `POSTGRES`, or `DYNAMODB`. |
| **`MCP_OPERATIONS`** | The whitelist (in `app/routers/endpoints.py`) of which router functions are exposed as MCP tools, as opposed to direct-HTTP-only. |
| **Token Authority** | An `AuthMixin` setting (`SELF_MANAGED` vs `PLATFORM_ISSUED`) describing where auth tokens would originate — config-only, not yet backed by implementation. See [security-map.md](security-map.md). |
| **Audit Mode** | An env var category (`AUDIT_MODE`, `AUDIT_LOG_PATH`, `AUDIT_INCLUDE_ARGUMENTS`, `AUDIT_MASK_SECRETS`) describing intended audit-logging behavior — no dedicated audit implementation exists yet (`mcp-server/audit/` is empty). |
| **Secret Guard** | `enable_secret_guard` config flag (`SecurityMixin`) — name implies a feature that blocks tool access to secret-like files; no corresponding implementation found (`app/security/` is empty). |
| **`fastapi-mcp`** | The third-party package used to mount MCP protocol support onto the FastAPI app (as opposed to Guardrail Hub's own protocol implementation). |

### AIOS Terms (for disambiguation only)

| Term | Meaning here | Not to be confused with |
|---|---|---|
| **AIOS** | The `.ai/` knowledge system governing how AI assistants work in this repo. | The Guardrail Hub *product*, which is unrelated to AI operating systems as a concept. |
| **Agent** (AIOS sense) | A capability-scoped AI executor concept defined in [`.ai/agents/README.md`](../agents/README.md). | Not the same as "AI assistant" generally, and not a Guardrail Hub product feature. |
| **Knowledge** (AIOS sense) | A category of addressable fact-units in [`.ai/knowledge/README.md`](../knowledge/README.md). | Not the same as this `intelligence/` module, which holds concrete, fixed-structure facts about the current repo rather than the addressable-unit pattern Knowledge defines — see [README.md](README.md) for how the two relate. |

## Related Documents
[system-overview.md](system-overview.md) · [security-map.md](security-map.md) · [`.ai/foundation/vision.md`](../foundation/vision.md)

## Last Updated
2026-07-03 — verified against commit `10bd79b`.
