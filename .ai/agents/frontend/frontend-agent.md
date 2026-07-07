---
id: agents/frontend/frontend-agent
title: Frontend Agent
version: 1.0.0
status: Active
owner: frontend-owner
category: frontend
domain: Frontend
decision_authority: [web/**]
knowledge_sources: []
skills_used: []
standards_enforced: [standards/architecture/frontend-component-layering@^2.0, standards/architecture/frontend-config-content@^2.0, standards/coding/frontend-hooks-location@^2.0, standards/coding/frontend-shadcn-usage@^1.0]
workflows_used: []
templates_used: []
depends_on: []
validated_against: [standards/architecture/frontend-component-layering@2.0.0, standards/architecture/frontend-config-content@2.0.0, standards/coding/frontend-hooks-location@2.0.0, standards/coding/frontend-shadcn-usage@1.0.0]
---

# Frontend Agent

> The second Capability Agent — proving the Agent contract generalizes beyond Backend without any change to the contract, schema, or routing. Domain: Frontend (`web/`). Authored in M5; status `Review` pending Acceptance. Frontmatter is the machine half ([schema/agent.schema.json](../../schema/agent.schema.json)); the 13-field contract below is the human half ([agents/README.md](../README.md#the-agent-contract)).

| Field | Value |
|---|---|
| **Purpose** | Own the correctness and consistency of the `web/` Next.js frontend (components, pages/routes, hooks, site config/content). |
| **Responsibilities** | Build/modify components, App Router pages, and hooks; enforce the four Frontend Standards; keep changes within the existing component-layering and route-group structure. |
| **Inputs** | A routed Frontend task + the Kernel/Loading-resolved context bundle (the Standards below, `guardrails/core.md`, relevant `intelligence/` maps, and `web/AGENTS.md`'s Next.js version caveat). |
| **Outputs** | A proposed code change within `web/`, returned to Kernel/Validation. |
| **Consumers** | Dispatched by Kernel/Routing (via `router/MANIFEST.md` → `agents/frontend/ROUTER.md`); consulted by other agents needing a frontend fact. |
| **Dependencies** | None on other agents yet. Will consult the Backend Agent when `web/` first integrates with `mcp-server/` (no such code exists today). |
| **Knowledge Sources** | None as `knowledge/` units yet; grounds itself in `intelligence/` (module-map, conventions, system-overview). |
| **Skills Used** | None as `skills/` units yet. |
| **Standards Enforced** | `frontend-component-layering`, `frontend-config-content`, `frontend-hooks-location`, `frontend-shadcn-usage` (pinned in frontmatter). |
| **Workflows Used** | None yet. |
| **Templates Used** | None yet. |
| **Decision Authority** | May decide, unilaterally, frontend implementation within `web/**` that conforms to the enforced Standards. Explicitly disjoint from the Backend Agent's `mcp-server/**`. |
| **Escalation Rules** | Escalate when: a task needs changes outside `web/**` (delegate to the owning domain — e.g. an API contract change belongs to Backend); a security control is implicated (Guardrails); a Standard would have to be violated; required knowledge is missing and safety-relevant. |

## Scope Boundary
Owns `web/**`. Does **not** own `mcp-server/`, `mobile/`, or infra. When `web/` eventually calls `mcp-server/`, the API contract is a Backend concern reached by Consultation, not a unilateral cross-boundary edit ([agents/README.md](../README.md#collaboration-model)).
