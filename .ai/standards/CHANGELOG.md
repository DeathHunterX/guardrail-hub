# Changelog — standards

Per-module changelog, per [governance/README.md](../governance/README.md#changelog-release-notes-migration-guides). One entry per version bump / status transition. Newest first.

| Date | Unit | Change | Reason / Ref |
|---|---|---|---|
| 2026-07-29 | architecture/runtime-boundary | 1.0.0 authored; status → **Active** | New unit. Gives independently deployed processes a governed home, and makes their isolation mechanically enforceable. [Decision 0012](../decisions/0012-runtime-boundary.md). |
| 2026-07-29 | architecture/backend-layering | 1.1.0 → **1.2.0** (Minor) | Additive Scope carve-out for `app/runtime/`, which is not the MCP server application. No R1–R4 rule text weakened; the role whitelist is unchanged and stays blocking. Mirrors the 1.1.0 bump that added `domain/`. [Decision 0012](../decisions/0012-runtime-boundary.md). |
| 2026-07-06 | architecture/frontend-component-layering, architecture/frontend-config-content, coding/frontend-hooks-location, coding/frontend-shadcn-usage | 1.0.0 authored; status → **Active** | Frontend Domain (M5); passed [Review Pass 0002](../review/passes/0002-frontend-slice.md) + Acceptance. |
| 2026-07-06 | architecture/backend-layering, architecture/persistence-dao, coding/backend-naming, operational/logging | status Review → **Active** (all at 1.0.0) | Passed [Review Pass 0001](../review/passes/0001-m3-backend-slice.md) + Acceptance Criteria (M4). |
| 2026-07-06 | (same four) | 1.0.0 authored | Distilled from `intelligence/conventions.md` (M3). |
