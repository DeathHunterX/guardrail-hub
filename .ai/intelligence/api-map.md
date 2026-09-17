# API Map

## Purpose

Inventory the current HTTP and MCP surfaces, including important omissions.

## Scope

FastAPI endpoints and the MCP whitelist. The standalone JMeter worker API is included separately.

## AI Usage Guidance

Do not infer MCP exposure from the existence of an HTTP route. Only operation IDs in `app/routers/endpoints.py::MCP_OPERATIONS` are MCP tools.

## Main Content

### MCP tools

Mounted at `/mcp` and backed by these HTTP operations:

| Group | Operation IDs |
|---|---|
| ZAP | `zap_scan_api`, `zap_scan_api_scenario`, `zap_scan_api_suite` |
| JMeter | `run_jmeter`, `analyze_jmeter_result` |
| History | `get_result`, `list_ids_by_type`, `list_operations` |

### Main server HTTP routes

| Prefix | Routes/purpose |
|---|---|
| `/` | Runtime metadata and advertised MCP tools |
| `/health` | Aggregate, liveness and readiness checks (`/health`, `/health/live`, `/health/ready`) |
| `/tools/zap` | Three implemented API scan submissions plus placeholder `/scan_web_application` and `/scan_interactive_web_session` |
| `/tools/jmeter` | Run tests and analyze stored results |
| `/tools/history` | Get result, list IDs by batch type, list operations |
| `/workers` | Unified worker directory GET plus legacy ZAP registration/heartbeat/drain/delete routes |
| `/zap-workers` | Canonical ZAP register, heartbeat, list, drain and delete routes |
| `/jmeter-workers` | JMeter register, heartbeat, list, drain and delete routes |
| `/conversations` | Create; get by ID; transition; synchronous turn; streamed turn; message redaction |
| `/public` | Static generated reports/assets |

Exact schemas, status codes and parameters remain source-of-truth in each router and schema module.

### JMeter worker runtime

The isolated worker exposes `/health/live`, assignment creation, assignment/result retrieval, and assignment cancellation under its own ASGI app.

### Security posture of the surface

No inbound authentication or authorization dependency/middleware is applied to the listed main-server endpoints. CORS is configurable, but CORS is not access control. Treat the API as trusted-network/development-only until an explicit security boundary is implemented.

## Related Documents

[codegraph.md](codegraph.md) · [security-map.md](security-map.md) · [database-map.md](database-map.md)

## Last Updated

2026-09-17 — route tables, schemas and MCP whitelist re-inspected at `3632394`; no surface change required.
