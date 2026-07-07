---
id: standards/architecture/frontend-config-content
title: Frontend Config & Content Separation
version: 2.0.0
status: Active
owner: frontend-owner
category: architecture
scope: web/ site metadata, external links, marketing copy, shared types, and tooling config placement
severity_default: blocking
applies_to: [web/config/**, web/content/**, web/constants/**, web/types/**, web/components.json]
enforced_by: []
depends_on: [standards/architecture/frontend-component-layering]
validated_against: [standards/architecture/frontend-component-layering@2.0.0]
---

# Frontend Config & Content Separation

> Distilled from [intelligence/conventions.md](../../intelligence/conventions.md). Supersedes v1.0.0 — splits `config/site.ts`'s `links` object out into `constants/`, and adds `types/` for cross-cutting type definitions.

## Scope
Where site metadata, external link destinations, marketing copy, cross-cutting types, and frontend tooling config live in `web/`. Assumes [frontend-component-layering](frontend-component-layering.md) (declared dependency).

## Rule Definitions
- **R1** Site metadata (name, description, canonical URL, in-app route constants) lives in `web/config/site.ts`; marketing copy lives in `web/content/*.ts` — both separate from component code.
- **R2** External destinations the site links out to (GitHub, docs, social, status page) live in `web/constants/external-links.ts`, not inline in `config/site.ts` or scattered across components.
- **R3** shadcn/ui CLI configuration lives in `web/components.json`.
- **R4** A type used by more than one `features/` module or by both a `content/` module and a component outside that feature (e.g. navigation link shapes consumed by both the header and the footer) lives in `web/types/<domain>.ts`. A type used by exactly one feature module stays colocated in that module's `types.ts` per [frontend-component-layering](frontend-component-layering.md).
- **R5** Components read metadata/copy/links from `config`, `content`, or `constants`; they do not inline site-level constants.

## Mandatory Rules
R1–R5 are Mandatory (blocking).

## Optional Recommendations
Keep copy that a non-engineer might edit in `content/`, not `config/`. Don't create a `types/` file for a single type with one consumer — that's what a feature-local `types.ts` is for.

## Exceptions
Purely presentational, non-reused strings local to one component may stay inline.

## Anti-patterns
- Hardcoding the site name or nav links inside a `layout/` component instead of reading `config/site.ts` / `content/site.ts`.
- Putting marketing copy directly in a `features/` component instead of that module's `data.ts` or the shared `content/site.ts`.
- Re-inlining a `github`/`docs`/`discord` URL in a component instead of importing it from `constants/external-links.ts`.
- Duplicating a shared interface (e.g. `NavLink`) into two feature-local `types.ts` files instead of promoting it to `types/navigation.ts`.

## Examples
`web/config/site.ts` + `web/constants/external-links.ts` + `web/content/{site,pricing,testimonials}.ts` + `web/types/{navigation,marketing}.ts` + `web/components.json` are the reference — see [intelligence/conventions.md](../../intelligence/conventions.md).
