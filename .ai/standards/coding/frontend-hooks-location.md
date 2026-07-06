---
id: standards/coding/frontend-hooks-location
title: Frontend Hooks Location
version: 1.0.0
status: Active
owner: frontend-owner
category: coding
scope: React hook placement in web/
severity_default: blocking
applies_to: [web/lib/hooks/**, web/hooks/**]
enforced_by: []
depends_on: []
validated_against: []
---

# Frontend Hooks Location

> Distilled from [intelligence/conventions.md](../../intelligence/conventions.md) and [intelligence/module-map.md](../../intelligence/module-map.md). Status `Review` pending Acceptance.

## Scope
Where React hooks live in `web/`.

## Rule Definitions
- **R1** Hooks live in `web/lib/hooks/` (e.g. `use-local-storage`, `use-media-query`, `use-mounted`).
- **R2** The root `web/hooks/` folder is an unused leftover (contains only `.gitkeep`); do not add hooks there.

## Mandatory Rules
R1–R2 are Mandatory (blocking).

## Optional Recommendations
Name hook files `use-*.ts` (kebab-case), matching the existing `lib/hooks/` files.

## Exceptions
None.

## Anti-patterns
- Creating `web/hooks/use-thing.ts` instead of `web/lib/hooks/use-thing.ts`.
- Splitting hooks across both folders, re-fragmenting what the convention consolidated.

## Examples
`web/lib/hooks/{use-local-storage,use-media-query,use-mounted}.ts` are the reference — see [intelligence/module-map.md](../../intelligence/module-map.md).
