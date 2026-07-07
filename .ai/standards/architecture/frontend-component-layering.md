---
id: standards/architecture/frontend-component-layering
title: Frontend Component Layering & Route Groups
version: 2.0.0
status: Active
owner: frontend-owner
category: architecture
scope: web/ component organization, feature modules, and App Router page structure
severity_default: blocking
applies_to: [web/components/**, web/features/**, web/app/**]
enforced_by: []
depends_on: []
validated_against: []
---

# Frontend Component Layering & Route Groups

> Distilled from observed conventions in [intelligence/conventions.md](../../intelligence/conventions.md) and [intelligence/module-map.md](../../intelligence/module-map.md). Supersedes v1.0.0's `components/{shared,sections}` split with a `features/` module tree — see Decision history.

## Scope
Component, feature-module, and page organization under `web/`. Does not govern `mcp-server/` (that is [backend-layering](backend-layering.md)'s concern) — the two share this `architecture` category but are scoped apart by `applies_to`.

## Rule Definitions
- **R1** Generic UI is layered by reusability scope: `components/ui/` (shadcn/ui primitives — see [frontend-shadcn-usage](../coding/frontend-shadcn-usage.md)), `components/common/` (hand-built reusable functional pieces — buttons, headers, command palette), `components/effects/` (hand-built reusable visual/motion treatments — glass panels, marquees, animated numbers), `components/layout/` (site-wide chrome: header, footer, announcement bar).
- **R2** Page-specific composition lives under `features/<domain>/<name>/`, one module per feature, never under `components/`. A feature module is: a component file (`<name>.tsx`), a `data.ts` copy/content module, an optional `types.ts` when the module exports non-trivial interfaces, and an `index.ts` barrel re-exporting the component. Domains seen today: `features/marketing/` (the landing page's sections — hero, pricing, faq, …), `features/company/`, `features/support/`, `features/trust/`, `features/legal/`.
- **R3** Pages use the App Router with parenthesized route groups: `web/app/(marketing)/`. A new product area (e.g. a dashboard) follows the same pattern: `web/app/(dashboard)/`. Within a route group, related pages may nest into a further parenthesized sub-group purely for filesystem organization — e.g. `web/app/(marketing)/(legal)/privacy/` — without changing the URL (`/privacy`, not `/legal/privacy`).
- **R4** An `app/**/page.tsx` stays a thin route: `metadata` export plus a single import of its feature component (e.g. `import { About } from "@/features/company/about"`). The page body, its data, and its types live in the matching `features/` module, not inline in `page.tsx`. A page whose entire body is one shared-component call (e.g. a legal document rendered via `LegalArticle`) may skip the wrapper component and import `data.ts` directly — do not fabricate a passthrough component for a single JSX line.
- **R5** A component's placement matches its reuse scope — a reusable piece does not live in `features/`, a page-specific composition does not live in `components/common/` or `components/effects/`.

## Mandatory Rules
R1–R5 are Mandatory (blocking).

## Optional Recommendations
Keep one feature component per file under `features/<domain>/<name>/`, matching the existing marketing-page structure. Extract a `types.ts` only when there is at least one genuinely standalone `export interface`/`export type` — a type derived inline from a `const` (e.g. `type X = (typeof data)[number]`) may stay in `data.ts` next to the value it derives from.

## Exceptions
None. A genuinely new layer is an architecture decision, not an ad-hoc folder. Do not create empty `features/` or `components/` subfolders speculatively for unbuilt functionality — a folder is added when it holds real code, not before.

## Anti-patterns
- A reusable animated-number component dropped in `features/marketing/` instead of `components/effects/`.
- A page-specific composition (e.g. the pricing page's tier grid) placed in `components/common/` instead of `features/marketing/pricing/`.
- A new page created at `web/app/dashboard/` (no route group) instead of `web/app/(dashboard)/`.
- Site chrome (header/footer) placed in `features/` rather than `components/layout/`.
- An `app/**/page.tsx` that inlines a full page body instead of delegating to its `features/` module.

## Examples
The current marketing site is the reference: `components/{ui,common,effects,layout}/` + `features/{marketing,company,support,trust,legal}/` with `app/(marketing)/{(company),(support),(trust),(legal)}/` — see [intelligence/module-map.md](../../intelligence/module-map.md).
