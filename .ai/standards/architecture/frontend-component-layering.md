---
id: standards/architecture/frontend-component-layering
title: Frontend Component Layering & Route Groups
version: 1.0.0
status: Active
owner: frontend-owner
category: architecture
scope: web/ component organization and App Router page structure
severity_default: blocking
applies_to: [web/components/**, web/app/**]
enforced_by: []
depends_on: []
validated_against: []
---

# Frontend Component Layering & Route Groups

> Distilled from observed conventions in [intelligence/conventions.md](../../intelligence/conventions.md) and [intelligence/module-map.md](../../intelligence/module-map.md). Status `Review` pending Acceptance.

## Scope
Component and page organization under `web/`. Does not govern `mcp-server/` (that is [backend-layering](backend-layering.md)'s concern) — the two share this `architecture` category but are scoped apart by `applies_to`.

## Rule Definitions
- **R1** Components are layered by reusability scope: `components/ui/` (shadcn/ui primitives — see [frontend-shadcn-usage](../coding/frontend-shadcn-usage.md)), `components/shared/` (hand-built reusable pieces), `components/sections/` (page-specific composition, one file per section), `components/layout/` (site-wide chrome).
- **R2** Pages use the App Router with parenthesized route groups: `web/app/(marketing)/`. A new product area (e.g. a dashboard) follows the same pattern: `web/app/(dashboard)/`.
- **R3** A component's placement matches its reuse scope — a reusable piece does not live in `sections/`, a page-specific composition does not live in `shared/`.

## Mandatory Rules
R1–R3 are Mandatory (blocking).

## Optional Recommendations
Keep one section component per file under `sections/`, matching the existing marketing-page structure.

## Exceptions
None. A genuinely new layer is an architecture decision, not an ad-hoc folder.

## Anti-patterns
- A reusable animated-number component dropped in `components/sections/` instead of `components/shared/`.
- A new page created at `web/app/dashboard/` (no route group) instead of `web/app/(dashboard)/`.
- Site chrome (header/footer) placed in `sections/` rather than `layout/`.

## Examples
The current marketing site is the reference: `components/{ui,shared,sections,layout}/` with `app/(marketing)/` — see [intelligence/module-map.md](../../intelligence/module-map.md).
