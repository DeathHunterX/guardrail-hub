# Release Notes — OWASP ZAP Module

Milestone: **Generic execution architecture + API scanning tool suite**
Status: **Release Candidate**

## Highlights

The OWASP ZAP integration evolved from a single hard-wired tool into a scalable,
generic execution platform with three production-ready API scanning tools, a
consistent authentication model, and aggregated multi-format reporting.

### New tools

- **`scan_api`** — security-scan a single API endpoint (quick or full).
- **`scan_api_scenario`** — scan an authenticated, ordered API workflow. Replays
  steps in dependency order, capturing and propagating variables, cookies, and
  JWT/bearer tokens between steps, then scans the authenticated endpoints.
- **`scan_api_suite`** — scan a whole application composed of multiple API
  services. Expands each service's OpenAPI spec into child `scan_api` scans, runs
  them in parallel across the worker pool, and aggregates into an application
  report.

### Architecture

- **Generic execution layer** — a strongly-typed operation registry
  (`ZapOperationType` → `ZapOperation`) with a `ZapOperationHandler` strategy and
  an `ExecutionStrategy` (worker-bound vs. orchestration). The background
  Dispatcher is fully tool-agnostic: adding a tool is one registration line, with
  **no** Dispatcher or WorkerService change.

### Developer & operator experience

- Request-time validation with actionable HTTP 422 messages (invalid URLs, bad
  auth config, circular/unknown/duplicate scenario dependencies, malformed or
  empty OpenAPI specs, duplicate categories).
- Rich request schemas: field descriptions, enum docs, and per-tool examples,
  surfaced in the MCP tool catalog and OpenAPI schema.
- Aggregated suite reporting in **Markdown**, **JSON**, and **SARIF 2.1.0** with
  Executive Summary, Scan Summary, Severity Summary, Category Summary,
  Recommendations, and Detailed Findings — deduplicated and deterministically
  ordered.
- Comprehensive documentation: overview + decision tree, per-tool references,
  troubleshooting, and a migration guide (`docs/owasp-zap/`).

## Compatibility

- **Backward compatible.** No request fields were renamed; existing `scan_api`
  usage, persisted operation metadata, the operation queue, and existing reports
  all continue to work.
- Legacy queued operations without an `operation_type` default to `api_scan`.
- `scan_api_suite`: the request field `application_name` is renamed to `suite_name` (a user-facing scan-run name); `application_name` is still accepted on input as an alias. The aggregated **report** key changed from `application_name` to `suite_name` — update report consumers accordingly.
- **Behavioural note:** some previously-*invalid* requests (e.g. relative URLs)
  now fail fast at submit with a clear 422 message instead of failing later. See
  [`MIGRATION.md`](MIGRATION.md). No action required for valid requests.

## Quality

- 66 ZAP-module tests (validation, ordering, propagation, OpenAPI expansion,
  orchestration, aggregation, reporting determinism, cross-format consistency,
  backward compatibility); full suite green aside from 2 pre-existing,
  unrelated notification-renderer failures.
- pyflakes clean; pylint 9.6/10; AIOS `check` passes; no import cycles.

## Not included (intentionally deferred)

- `scan_web_application` and `scan_interactive_session` (browser automation
  architecture still under evaluation). No Playwright/Selenium/WebSocket code.
- Scenario: loops, conditional/parallel branches, retries, data-driven runs.
- Suite: incremental scans, historical comparison, dashboards, scheduling,
  portfolio management.

## Known limitations

See [`../../architecture/zap-generic-execution/PRODUCTION-READINESS.md`](../../architecture/zap-generic-execution/PRODUCTION-READINESS.md)
for the full review. In brief:

- Concurrent suite orchestrations are bounded by the Dispatcher's orchestration
  executor (4 threads); additional suites queue.
- A suite spanning many endpoints with few workers can run long (children are
  scheduled as workers free up).
- Scenario steps do not assert HTTP response status (a failed login still
  proceeds unauthenticated) — candidate hardening for a future milestone.
- Orphaned pre-milestone scaffolding files exist for the future web/interactive
  tools; slated for a follow-up cleanup.
