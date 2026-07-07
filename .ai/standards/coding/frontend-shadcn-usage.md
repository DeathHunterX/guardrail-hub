---
id: standards/coding/frontend-shadcn-usage
title: Frontend shadcn/ui Primitive Usage
version: 1.0.0
status: Active
owner: frontend-owner
category: coding
scope: web/components/ui primitives
severity_default: blocking
applies_to: [web/components/ui/**]
enforced_by: []
depends_on: [standards/architecture/frontend-component-layering]
validated_against: [standards/architecture/frontend-component-layering@2.0.0]
---

# Frontend shadcn/ui Primitive Usage

> Distilled from [intelligence/conventions.md](../../intelligence/conventions.md) and `web/README.md`. Status `Review` pending Acceptance.

## Scope
The `web/components/ui/` primitives layer. Assumes [frontend-component-layering](../architecture/frontend-component-layering.md).

## Rule Definitions
- **R1** `components/ui/` primitives are generated/vendored via the shadcn/ui CLI — added with `npx shadcn@latest add <component>`, not hand-rolled.
- **R2** Do not heavily hand-edit a generated primitive; extend it via composition in `components/common/` instead.

## Mandatory Rules
R1–R2 are Mandatory (blocking).

## Optional Recommendations
Keep primitive customizations (theme tokens) in the shared Tailwind/theme config rather than editing each primitive.

## Exceptions
A minimal, documented patch to a primitive is permitted when the CLI offers no option — but a hand-written *new* primitive is not.

## Anti-patterns
- Hand-writing a `Button`/`Dialog` primitive from scratch in `components/ui/` instead of `npx shadcn@latest add`.
- Forking a generated primitive with heavy edits, so a future `shadcn` update can't be reapplied.

## Examples
`web/components/ui/` (button, card, dialog, tabs, table, …) is vendored via shadcn per `web/README.md` — see [intelligence/module-map.md](../../intelligence/module-map.md).
