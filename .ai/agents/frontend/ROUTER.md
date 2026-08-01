# Frontend Domain Router — Tier 1

> Reached from [router/MANIFEST.md](../../router/MANIFEST.md) when a task is classified into the **Frontend** Domain. Holds this Domain's Agent registry and maps Frontend task-subtypes to the resources to load. A materialized routing artifact (no frontmatter, not a unit) — see [router/README.md](../../router/README.md). Created in M5 ([Decision 0001](../../decisions/0001-aios-bootstrap-roadmap.md)); mirrors [agents/backend/ROUTER.md](../backend/ROUTER.md) without any change to the routing model.

## Agent Registry (Frontend Domain)

| Agent | Owns | Contract |
|---|---|---|
| Frontend Agent | `web/**` | [frontend-agent.md](frontend-agent.md) |

## Task-Subtype → Resources

Always loaded for any Frontend task: `guardrails/core.md` (Tier G) + the Frontend Agent contract + `web/AGENTS.md` (Next.js version caveat) + [knowledge/concept/engineering-philosophy](../../knowledge/concept/engineering-philosophy.md) (the default lean between options the Standards leave open; ranks below every rule per [AGENTS.md](../../../AGENTS.md) conflict order).

| Frontend task subtype | Standards to load | Also consult |
|---|---|---|
| Add/modify a component | [architecture/](../../standards/architecture/INDEX.md) (frontend-component-layering), [coding/](../../standards/coding/INDEX.md) (frontend-shadcn-usage) | `intelligence/module-map.md` |
| Add/modify a page or route | [architecture/](../../standards/architecture/INDEX.md) (frontend-component-layering, frontend-config-content) | `intelligence/module-map.md` |
| Add/modify a hook | [coding/](../../standards/coding/INDEX.md) (frontend-hooks-location) | — |
| Site metadata / copy change | [architecture/](../../standards/architecture/INDEX.md) (frontend-config-content) | — |
| **More than one valid implementation approach exists** (which option is preferred, and when to escalate instead of implement) | [core/](../../standards/core/INDEX.md) (**decision-policy**) | — |

The category indexes ([architecture/](../../standards/architecture/INDEX.md), [coding/](../../standards/coding/INDEX.md)) list standards from **all** domains; the Frontend Agent's `standards_enforced` selects the `web/`-scoped ones. This is the concern-category / path-scope design working across domains — the same indexes serve Backend and Frontend without duplication.

## Escalation Out of Domain
A task touching `mcp-server/`, `mobile/`, deployment/infra, or AIOS meta-work is out of Frontend's Decision Authority — delegate or escalate per [agents/README.md](../README.md#collaboration-model).
