---
id: standards/architecture/frontend-config-content
title: Frontend Config & Content Separation
version: 1.0.0
status: Active
owner: frontend-owner
category: architecture
scope: web/ site metadata, marketing copy, and tooling config placement
severity_default: blocking
applies_to: [web/config/**, web/content/**, web/components.json]
enforced_by: []
depends_on: [standards/architecture/frontend-component-layering]
validated_against: [standards/architecture/frontend-component-layering@1.0.0]
---

# Frontend Config & Content Separation

> Distilled from [intelligence/conventions.md](../../intelligence/conventions.md). Status `Review` pending Acceptance.

## Scope
Where site metadata, marketing copy, and frontend tooling config live in `web/`. Assumes [frontend-component-layering](frontend-component-layering.md) (declared dependency).

## Rule Definitions
- **R1** Site metadata lives in `web/config/site.ts`; marketing copy lives in `web/content/site.ts` — both separate from component code.
- **R2** shadcn/ui CLI configuration lives in `web/components.json`.
- **R3** Components read metadata/copy from `config`/`content`; they do not inline site-level constants.

## Mandatory Rules
R1–R3 are Mandatory (blocking).

## Optional Recommendations
Keep copy that a non-engineer might edit in `content/`, not `config/`.

## Exceptions
Purely presentational, non-reused strings local to one component may stay inline.

## Anti-patterns
- Hardcoding the site name or nav links inside a `layout/` component instead of reading `config/site.ts`.
- Putting marketing copy directly in a `sections/` component instead of `content/site.ts`.

## Examples
`web/config/site.ts` + `web/content/site.ts` + `web/components.json` are the reference — see [intelligence/conventions.md](../../intelligence/conventions.md).
