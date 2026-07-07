---
id: standards/coding/frontend-hooks-location
title: Frontend Hooks Location
version: 2.0.0
status: Active
owner: frontend-owner
category: coding
scope: React hook placement in web/
severity_default: blocking
applies_to: [web/hooks/**]
enforced_by: []
depends_on: []
validated_against: []
---

# Frontend Hooks Location

> Distilled from [intelligence/conventions.md](../../intelligence/conventions.md) and [intelligence/module-map.md](../../intelligence/module-map.md). Supersedes v1.0.0: the root `web/hooks/` folder — previously a documented unused leftover — is now the canonical location; `web/lib/hooks/` no longer exists.

## Scope
Where React hooks live in `web/`.

## Rule Definitions
- **R1** Hooks live in `web/hooks/` (e.g. `use-local-storage`, `use-media-query`, `use-mounted`, `use-header-scroll`, `use-active-section`), regardless of whether they're generic or presently consumed by a single component.
- **R2** `web/lib/` holds non-hook utilities and vendor integration code (`lib/utils/`, `lib/gsap/`, `lib/screens.ts`) — a new file under `lib/` that exports a `use*` hook belongs in `hooks/` instead.

## Mandatory Rules
R1–R2 are Mandatory (blocking).

## Optional Recommendations
Name hook files `use-*.ts` (kebab-case), matching the existing `hooks/` files.

## Exceptions
None.

## Anti-patterns
- Creating `web/lib/hooks/use-thing.ts` or `web/components/**/use-thing.ts` instead of `web/hooks/use-thing.ts`.
- Splitting hooks across multiple folders, re-fragmenting what this convention consolidates.

## Examples
`web/hooks/{use-local-storage,use-media-query,use-mounted,use-header-scroll,use-active-section}.ts` are the reference — see [intelligence/module-map.md](../../intelligence/module-map.md).
