# Milestone Review — M3: First Vertical Slice (Backend)

Closed: 2026-07-06
Roadmap: [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md), milestone M3

---

## 1. Objective

Push one real Domain (Backend/`mcp-server`) end-to-end through the whole AIOS so the architecture is proven against real code, not assumptions. Per the two principles adopted at the M2→M3 boundary, the Definition of Done was raised: not merely "Guardrails + Agent + Standards exist," but **a real Backend task resolves along the complete Product Lane** — User Task → MANIFEST → Backend Domain → Agent → Standards → Guardrails → Validation → Review — with every hop landing on a real, loadable resource. Validation is performed *during* authoring, not batched.

## 2. Planned Scope vs. Actual Scope

Delivered the planned slice. One blocking prerequisite was resolved first: the M1/M2 open question on guardrail rule granularity, decided in [Decision 0002](../decisions/0002-guardrail-rule-granularity.md) (core rules live in `core.md`'s body, versioned as a set; no Kernel change, no premature RFC). One tooling extension was made (see Deviations). No other scope change.

## 3. Files Changed

**Content units created (Review-status, pending M4 activation):**
- `guardrails/core.md` — 5 core rules G1–G5 authored (0.1.0 → 0.2.0).
- `standards/architecture/backend-layering.md`, `standards/architecture/persistence-dao.md`, `standards/coding/backend-naming.md`, `standards/operational/logging.md` — 4 Standards distilled from `intelligence/conventions.md`.
- `agents/backend/backend-agent.md` — the first real Capability Agent (13-field contract + machine frontmatter).

**Routing artifacts:**
- `agents/backend/ROUTER.md` — the first Domain Router (Agent registry + task-subtype→resource map).
- `router/MANIFEST.md` — Backend Domain flipped from *Pending* to **Active**.
- `standards/{architecture,coding,operational}/INDEX.md` — **generated** by `aios index` (not hand-written).

**Adapters:**
- `AGENTS.md` (repo root) — canonical, cross-vendor, two-lane entry point.
- `.claude/CLAUDE.md`, `mcp-server/CLAUDE.md`, `web/CLAUDE.md`, `mobile/CLAUDE.md` — reduced to thin `@../AGENTS.md` imports (retiring the old pre-two-lane "read .ai/README.md then kernel" pointers).

**Governance/tooling:**
- `decisions/0002-*.md` + `decisions/README.md` index.
- `tools/aios.py` — impact engine extended (reference fields as dependency edges) + a selftest case.

## 4. The Product Lane, Proven End-to-End

Worked task: **"Add a Nuclei scanner integration to the MCP server."** Every hop resolves to a real file (validated by `aios`):

| Hop | Resolves to | What happens |
|---|---|---|
| **User Task** | — | Code work under `mcp-server/`. |
| **Adapter** | `mcp-server/CLAUDE.md` → `@../AGENTS.md` | Classified as **Product Lane**; Constitution deliberately *not* loaded. |
| **Tier G** | [`guardrails/core.md`](../guardrails/core.md) | G1–G5 resident (no secrets, don't weaken controls, don't fabricate scan results, no unauthorized outward actions, label inference). |
| **Tier 0 / MANIFEST** | [`router/MANIFEST.md`](../router/MANIFEST.md) | `mcp-server/` pattern → **Backend** Domain. |
| **Backend Domain** | [`agents/backend/ROUTER.md`](../agents/backend/ROUTER.md) | Subtype "add MCP tool integration" → load `architecture`+`coding`+`operational` Standards; dispatch Backend Agent. |
| **Agent** | [`agents/backend/backend-agent.md`](../agents/backend/backend-agent.md) | `decision_authority: mcp-server/**` → in scope. Proposes `schemas/tools/nuclei/`, `services/tools/nuclei/`, `integrations/nuclei/`, `routers/mcp/nuclei_router.py`. |
| **Standards** | the 4 units via their `INDEX.md` | ZAP-layout (backend-layering R3), `Nuclei*`/`<Tool><Role>` naming (backend-naming), `MCPLogger` only (logging), DAO if persisting (persistence-dao). |
| **Guardrails** | `guardrails/core.md` | G3 forces a *real* Nuclei run, not stubbed findings; G1 no secrets; G2 no control-weakening. |
| **Validation** | [`kernel/validation/`](../kernel/validation/README.md) six checks | Architecture (stayed in `mcp-server/**`), Naming, Standards (the 4), Workflow (n/a — none authored), Security (Guardrails), Completeness. |
| **Review** | [`review/`](../review/README.md) 12-dimension checklist | Owner `backend-owner` signs off before the change reaches `Active`. |

**No dead hops.** Empty stations (Workflow, Template, Knowledge, Skill units) are documented no-ops, not breaks — the lane completes without them. The *execution* of the Validation and Review gates as governance processes on a real asset is M4's charter; M3 proves the **path resolves end-to-end and every station is a real, reachable resource**.

## 5. Verification Performed (by tool, per the dogfooding principle)

- **`aios validate` → 6 units, 0 errors** — run *incrementally at each authoring step* (principle 1), not batched.
- **`aios check` → PASS** — 6 units valid, 506 relative links resolve, 5 routing files under the 150-line ceiling.
- **`aios selftest` → PASS (8/8)** — including the new case proving a Standard referenced via `standards_enforced` (with an `@version` pin) is an impact edge.
- **`aios impact standards/coding/backend-naming --change major` → flags `agents/backend/backend-agent` (NeedsRevalidation)** — the M3 DoD impact proof. `backend-layering --change major` additionally flags `persistence-dao` transitively via `depends_on`.
- **`aios index` → 3 INDEX.md generated** from frontmatter (never hand-written).
- **Adapter references** (`AGENTS.md` + 4 `CLAUDE.md`): 17 links/imports resolve (checked separately, as they live outside `aios`'s `.ai/` root).

## 6. Lessons Learned

- **Validate-during-authoring paid off immediately.** The Backend Agent's frontmatter was first written with block-style YAML lists (`- item`); `aios validate` rejected it on the spot (the stdlib parser accepts only inline `[a, b]` lists). Caught at authoring, fixed in seconds — exactly the failure that batched, end-of-milestone verification would have surfaced late and expensively.
- **Real data exercised the impact engine and found a gap, as M2 predicted.** `depends_on` alone did not flag an Agent when a Standard it *enforces* changed. Extending edges to `standards_enforced` (and the other reference fields) was the fix — the "surprise" M2's review told M3 to watch for.
- **The Product Lane genuinely stays cheap.** The Nuclei task loads Tier G + MANIFEST + one Domain Router + 4 small Standards + one Agent — never `foundation/`, never full `kernel/`. The two-lane model's central promise held on a real task.

## 7. Deviations

- **Extended `tools/aios.py` (M2 artifact) during M3.** Adding `standards_enforced` et al. as impact edges. Justified and foreseen: M2's own review flagged "impact proven by logic, not real repo data — M3 is its first real exercise; watch for surprises." This was that surprise; handling it is inherent to M3's first real use, not a scope violation. Re-dogfooded (selftest 8/8, check PASS).
- **M3 units are `Review`, not `Active`.** Reaching `Active` requires M4's Review pass / guardrail RFC. Intentional hand-off to M4, not a shortfall.

## 8. Technical Debt / Backlog Discovered

- **Block-style YAML lists unsupported (ergonomic cost).** Multi-item frontmatter (`standards_enforced` with 4 version-pinned ids) is a long inline line. Supporting block lists (`key:` + `- item`) is a candidate *deliberate* tooling extension with doc updates — not to be slipped in silently, since the flat-inline subset is a documented constraint ([Decision 0002](../decisions/0002-guardrail-rule-granularity.md), [schema/README](../schema/README.md)).
- **Product Lane has empty stations.** Workflow, Template, Knowledge, Skill units don't exist; the lane completes but those hops are no-ops until M5-era authoring. Not blocking.
- **All M3 content sits at `Review`.** `guardrails/core.md` (G1–G5), the 4 Standards, and the Backend Agent await M4 activation (Review→Active; guardrail RFC).
- **Latent from M0–M2, unchanged:** lifecycle-restatement debt, `Retired` terminology note, no product CI to run `aios check` automatically.

## 9. Prerequisites Met for M4

- Real, validated assets now exist to run the governance loop against — Review can review the 4 Standards + Agent; the guardrail RFC has `core.md` to act on; the "Fix Bug" benchmark has a real Domain to exercise. ✓
- The Product Lane resolves end-to-end (§4). ✓
- Impact analysis is proven on real data (§5). ✓
- M4 targets: activate the governance loop — run a real Review pass (M3 units `Review`→`Active`), the first full RFC (guardrails `core.md` → `Active` with security sign-off), and the "Fix Bug" Evaluation benchmark.

**M4 — Governance Loop Activation may begin.**
