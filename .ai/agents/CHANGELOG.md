# Changelog — agents

Per-module changelog, per [governance/README.md](../governance/README.md#changelog-release-notes-migration-guides). One entry per version bump / status transition. Newest first.

| Date | Unit | Change | Reason / Ref |
|---|---|---|---|
| 2026-07-29 | backend/backend-agent | 1.2.0 → **1.3.0** (Minor) | Enforces the new `architecture/runtime-boundary@^1.0`, and re-pinned to `backend-layering@1.2.0`. Additive: no responsibility, authority or escalation rule changed. Without it, a backend task touching `app/runtime/` — inside this agent's `mcp-server/**` authority — would load no standard governing it. [Decision 0012](../decisions/0012-runtime-boundary.md). |
| 2026-07-06 | frontend/frontend-agent | 1.0.0 authored; status → **Active** | Second Capability Agent; Frontend Domain (M5). Passed [Review Pass 0002](../review/passes/0002-frontend-slice.md) + Acceptance; `decision_authority` verified disjoint from Backend by `aios`. |
| 2026-07-06 | backend/backend-agent | status Review → **Active** (1.0.0) | Passed [Review Pass 0001](../review/passes/0001-m3-backend-slice.md) + Acceptance Criteria; all `standards_enforced` are Active (M4). |
| 2026-07-06 | backend/backend-agent | 1.0.0 authored | First Capability Agent; Backend Domain (M3). |
