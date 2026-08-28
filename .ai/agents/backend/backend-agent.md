---
id: agents/backend/backend-agent
title: Backend Agent
version: 1.3.0
status: Active
owner: backend-owner
category: backend
domain: Backend
decision_authority: [mcp-server/**]
knowledge_sources: []
skills_used: []
standards_enforced: [standards/architecture/backend-layering@^1.2, standards/architecture/runtime-boundary@^1.0, standards/architecture/domain-layer@^1.0, standards/architecture/service-package-design@^1.0, standards/architecture/persistence-dao@^1.0, standards/coding/backend-naming@^1.0, standards/operational/logging@^1.0]
workflows_used: []
templates_used: []
depends_on: []
validated_against: [standards/architecture/backend-layering@1.2.0, standards/architecture/runtime-boundary@1.0.0, standards/architecture/domain-layer@1.0.0, standards/architecture/service-package-design@1.0.0, standards/architecture/persistence-dao@1.0.1, standards/coding/backend-naming@1.0.0, standards/operational/logging@1.0.0]
---

# Backend Agent

> The first real Capability Agent. Domain: Backend (`mcp-server/`). Active since M4. Frontmatter above is the machine half ([schema/agent.schema.json](../../schema/agent.schema.json)); the 13-field contract below is the human half ([agents/README.md](../README.md#the-agent-contract)).

| Field | Value |
|---|---|
| **Purpose** | Own the correctness and consistency of backend code in `mcp-server/` (the FastAPI MCP server, its tools, DAO, and integrations). |
| **Responsibilities** | Implement/modify endpoints, MCP tools, services, DAO code, and tool integrations; enforce the six Backend Standards; keep changes within the existing layered architecture and within each service package's designed boundaries (root = application services, internals in responsibility subpackages, façade = contract); **reuse the canonical Domain vocabulary rather than redefining a business concept, and translate a tool's native model at its adapter boundary**. |
| **Inputs** | A routed Backend task + the Kernel/Loading-resolved context bundle (the Standards below, `guardrails/core.md`, relevant `intelligence/` maps). |
| **Outputs** | A proposed code change within `mcp-server/`, returned to Kernel/Validation. |
| **Consumers** | Dispatched by Kernel/Routing (via `router/MANIFEST.md` → `agents/backend/ROUTER.md`); consulted by other agents needing a backend fact. |
| **Dependencies** | None on other agents yet (Frontend/Security/Infra agents not instantiated). |
| **Knowledge Sources** | None as `knowledge/` units yet; grounds itself in `intelligence/` (system-overview, module-map, api-map, database-map) until Knowledge units exist. |
| **Skills Used** | None as `skills/` units yet. |
| **Standards Enforced** | `backend-layering`, `runtime-boundary`, `domain-layer`, `service-package-design`, `persistence-dao`, `backend-naming`, `logging` (pinned in frontmatter). `domain-layer` D2/D3 **and** `runtime-boundary` RB3/RB6 are additionally machine-checked by `aios arch`. |
| **Workflows Used** | None yet (Workflow units not authored). |
| **Templates Used** | None yet (Template units not authored). |
| **Decision Authority** | May decide, unilaterally, backend implementation within `mcp-server/**` that conforms to the enforced Standards. |
| **Escalation Rules** | Escalate when: a task needs changes outside `mcp-server/**` (delegate to the owning domain); a security control is implicated (consult Guardrails/Security); a Standard would have to be violated to proceed (Recovery, never silent violation); required knowledge is missing and safety-relevant; **a task appears to need a new business concept, a new Domain capability, or a change to canonical vocabulary — that is a Decision-level change requiring an ADR, never an ad-hoc type**. |

## Scope Boundary
Owns `mcp-server/**`. Does **not** own `web/`, `mobile/`, deployment/infra, or AIOS meta-work. A task touching those is a Delegation or Escalation per [agents/README.md](../README.md#collaboration-model), never a silent reach across the boundary.
