# DX/Usability Phase — Migration Notes

This phase improved developer/operator experience across the ZAP tools. **All
changes are additive and backward-compatible — no request field was renamed, no
existing behaviour was removed, and the frozen generic execution layer
(Dispatcher, WorkerService, registry, handler, operation type, execution
strategy) was not touched.**

## No breaking changes

- No field renames. `target_url` (alias of `url`), `token`, `token_type`,
  `cookie`, etc. are unchanged.
- Existing valid requests continue to validate and run identically.
- Existing persisted operations and reports remain readable; the aggregated
  suite report **adds** sections but keeps `application_summary` and `categories`.

## What changed (additive)

### Validation now fails fast (HTTP 422) with actionable messages

Previously some errors surfaced only at execution time; they are now caught when
the request is submitted. If you were sending an already-valid request, nothing
changes. Newly rejected (previously would run/fail later):

| Now rejected at submit | Message hint |
|---|---|
| Non-absolute `target_url` (e.g. `api.example.com/x`) | "not a valid absolute URL" |
| `token_prefix` set with no `token`/`token_field` | "token_prefix is set but no 'token' …" |
| Scenario: duplicate step names | "Each step must have a unique name." |
| Scenario: `depends_on` unknown step | "depends on unknown step 'x'." |
| Scenario: circular `depends_on` | "Circular dependency between steps: …" |
| Scenario: duplicate `extract` variables | "captured by more than one step" |
| Suite: duplicate category names | "Duplicate category name 'x'." |
| Suite: category with zero endpoints | "expands to zero endpoints." |
| Suite: malformed OpenAPI spec | "openapi_spec is not valid JSON or YAML" |

Note: templated scenario URLs (`https://api/users/${uid}`) are intentionally
**not** rejected — they are validated after step resolution.

### Richer request schemas

Field descriptions, enum docs, and per-model examples were added (visible in the
OpenAPI schema and the MCP tool catalog). No field semantics changed.

### Enhanced aggregated suite report

The suite JSON/Markdown now include, in order: Executive Summary, Scan Summary,
Severity Summary, Category Summary, Recommendations, Detailed Findings, and
Endpoints by Category — consistent with the SARIF output. `application_summary`
and `categories` are retained for any existing consumer.

### MCP tool metadata

Each tool now exposes a concise `summary`, a detailed description (purpose,
when-to-use, when-not, inputs, output), and request examples — so the tools are
understandable directly from an MCP client's catalog.

### Documentation

New reference docs under `mcp-server/docs/owasp-zap/`: an overview + decision
tree (`README.md`) and one page per tool.

## `application_name` → `suite_name` (scan_api_suite)

The suite request field `application_name` was renamed to **`suite_name`** to
reflect its real purpose: a user-defined name for the scan run (shown as the
report title).

- **Input — backward compatible.** `application_name` is still accepted as an
  alias, so existing callers and replayed (older) queued operations keep working.
  New submissions should send `suite_name`.
- **Report output — changed key (potentially breaking for report consumers).**
  The aggregated report now uses the key `suite_name` instead of
  `application_name` (top-level JSON and the `executive_summary` block; the
  Markdown title shows the suite name). SARIF is unaffected (it never carried this
  field). Any dashboard/tool that read `report["application_name"]` must read
  `report["suite_name"]`.

## Operation metadata (unchanged shape, documented)

Persisted operation metadata is intentionally minimal and sufficient for audit,
replay, tracing, and aggregation:

- `operation_type` — routes execution (e.g. `api_scan`, `api_scenario`, `api_suite`).
- `request` — the full request, so an operation is deterministically replayable.
- `name`, `target_url`/`suite_name`, `method` — human/trace context.
- `parent_operation_id` — set on child scans created by a suite (parent/child
  aggregation and auditing).

## Action required

None. If any client relied on a previously-accepted **invalid** request (e.g. a
relative URL), update it to a valid one — the 422 message states exactly what to
fix.
