# 0005 — Architecture Hardening Refactor & Working-Tree Corruption Recovery

Status: **Accepted**
Owner: Loi Phan
Date: 2026-07-10

---

## Context

A full architectural review of `mcp-server/` was commissioned to enforce strict, scalable layering ahead of scaling to 15+ security tools and 100+ modules. The review confirmed the backend was already largely well-architected (correct `routers → services → integrations|dao → core` layering, an isolated Worker Registry / Scheduler / Pool Manager / Dispatcher split, an extracted ZAP helper module, a hexagonal ports-and-adapters event/notification spine per [Decision 0004](0004-chatops-platform-architecture.md)). It did **not** exhibit the classic problems the review guarded against — no God routers, no DAO orchestration, no scheduler embedded in the registry.

The review did surface a set of concrete defects, and — critically — discovered that several source files in the working tree were **corrupted** (NUL-byte padding and mid-statement truncation), leaving the backend un-importable. The corruption was independent of the refactor (the committed blobs were clean or newer-but-truncated); it is consistent with a filesystem/editor crash artifact. Because the guardrails forbid presenting a broken state as working ([guardrails/core.md](../guardrails/core.md) G3/G5), recovering these files was a precondition for any refactor.

## Decision

Perform a behavior-preserving hardening refactor of `mcp-server/`, recover the corrupted files, mirror the test suite to the source tree, and re-synchronize the governance layer (`.ai/`, `AGENTS.md`, architecture docs) so no document describes an outdated architecture. No new runtime dependencies, test frameworks, CI, or linters were introduced (verification is static: `python -m py_compile`, import-graph, NUL/CRLF scans, and `aios check`).

### 1. Corruption recovery (correctness precondition)
- Stripped trailing NUL padding from `integrations/owasp_zap/pool.py`, `dao/operation_dao.py`, `core/mcp_logger.py`, and two test files.
- Reconstructed mid-statement truncations, preserving the **newer** working-tree behavior (not reverting to older committed blobs) where the working copy was ahead:
  - `dao/postgres/operation_dao.py` — completed `get_queued_operations()` + restored `_from_row`.
  - `dao/dynamodb/operation_dao.py` — completed `initialize_schema()` (local-create branch reconstructed to match its documented behavior and the table DDL in the module docstring; the exact original bytes were unrecoverable) + restored `_paginated_scan`/`_from_item`.
  - `schemas/tools/owasp_zap/common.py` — completed the `ScannerThresholdOverride` model (the working copy adds the `QUEUED` status used across the queue).
  - `services/tools/owasp_zap/api_scanner.py` — reconstructed the truncated tail of `zap_full_scan_worker` from the QUICK-worker pattern, adapted to the worker-pool API.
  - `helpers/tools/owasp_zap_helpers.py`, `integrations/owasp_zap/client.py` — restored truncated method tails.

### 2. Logging standard enforcement ([operational/logging](../standards/operational/logging.md))
- Replaced stdlib `logging.getLogger(__name__)` with `MCPLogger` in `integrations/owasp_zap/client.py`, `services/tools/owasp_zap/web_scanner.py`, and `services/tools/owasp_zap/interactive_scanner.py` (the only three violations of R1/R2).
- Standardized `MCPLogger` instance names to the `<ClassName>` convention (e.g. `"OWASP ZAP"` — which also produced a space in the log filename — became `OwaspZapApiScanService` / `OwaspZapApiScanHelpers`).

### 3. Router → service layering ([backend-layering](../standards/architecture/backend-layering.md) R4)
- Extracted `ZapWorkerService` (`services/tools/owasp_zap/worker_service.py`). `routers/public/zap_worker_router.py` no longer calls the DAO or the Registry directly; it is a thin HTTP adapter. The "fail an operation orphaned by a removed/dead worker" rule now has one home (`ZapWorkerService.fail_orphaned_operation`), shared with the dispatcher's heartbeat sweep.
- Extracted `HealthService` (`services/public/health_service.py`). The storage-probing helpers (`_tcp_check`, `_postgres_target`, `_dynamodb_target`, `_storage_check`) moved out of `health_router.py`, which is now HTTP-only.

### 4. Role & folder consolidation ([backend-layering](../standards/architecture/backend-layering.md) R1)
- Removed two roles not sanctioned by the layering standard:
  - `app/utils/` — its single unit `LoggerUtils` moved to `app/core/logger_utils.py`, resolving a `core → utils` dependency inversion (`core/mcp_logger` had imported upward).
  - `app/prompts/` — three 0-byte, unreferenced files; deleted as dead scaffold.
- Removed empty scaffold directories (`app/client`, `app/policies`, `app/runner`, `app/security`, `app/integrations/jmeter`, `app/services/internal`, `app/services/tools/jmeter`, `app/schemas/public`, `app/schemas/tools/{playwright,selenium}`) and 0-byte stub files (`routers/internal/token_router.py`, `routers/mcp/{playwrights,selenium}_router.py`, `schemas/internal/audit_request.py`), per the repo's own no-empty-scaffold anti-pattern.

### 5. Stale/broken import fixes
- `web_scanner.py` and `interactive_scanner.py` imported `app.services.owasp_zap.client`, a path that no longer exists (the client had moved to `app.integrations.owasp_zap.client`). Repointed; both files were previously un-importable dead code.

### 6. Test suite mirrors the source tree ([review target 15])
- The 11 flat `tests/test_*.py` files were reorganized into a tree mirroring `app/` (`tests/services/{evaluations,notification,operations,platform}/`, `tests/integrations/chat/slack/`, `tests/flows/` for cross-module flow tests), each test renamed to match the module under test. The suite remains `unittest`-based; no runner was added.

## Consequences

- The backend compiles cleanly (`py_compile` across all of `app/` and `tests/`), has no NUL corruption, no stale imports, and no non-English comments (three Vietnamese comments in `mcp_logger.py` were translated per the project's English-only comment rule).
- External behavior is unchanged: HTTP routes, MCP operation IDs, request/response shapes, and the queue/dispatch model are all preserved. Internal import paths changed (all updated).
- `initialize_schema`'s DynamoDB-local table-creation branch is a faithful reconstruction, not the original bytes — flagged for review if the original is recovered from a backup.
- Line-ending inconsistency (CRLF vs LF) across the tree was left as-is except in files rewritten during recovery (now LF); normalizing the whole repo (via a `.gitattributes` `eol=lf` rule) is deferred as tracked technical debt.

## Supersedes / relates to
Extends the layering discipline of [Decision 0004](0004-chatops-platform-architecture.md); enforces [backend-layering](../standards/architecture/backend-layering.md) and [operational/logging](../standards/operational/logging.md). Triggers a re-verification of [intelligence/](../intelligence/README.md) (its baseline `10bd79b` predates both the ChatOps work and this refactor).
