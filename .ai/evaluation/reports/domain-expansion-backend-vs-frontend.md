# Domain Expansion Report — Backend vs. Frontend

Date: 2026-07-06
Purpose: prove that the *same* AIOS architecture serves at least two genuinely different domains (Backend/`mcp-server` and Frontend/`web`) **without any change to the Constitution** (foundation, kernel, routing model, schema, lifecycle, governance).
Gate: further horizontal expansion (Mobile, Security, …) proceeds only if this evidence holds.

---

## 1. Side-by-Side

| Dimension | Backend (M3–M4) | Frontend (M5) | Same mechanism? |
|---|---|---|---|
| Pipeline | Author → `aios validate` → Review → Acceptance → Activate | Author → `aios validate` → Review → Acceptance → Activate | **Identical** |
| Domain scope | `mcp-server/**` | `web/**` | Same field (`decision_authority`), disjoint values |
| Standards authored | 4 (layering, dao, naming, logging) | 4 (component-layering, config-content, hooks-location, shadcn-usage) | Same contract + schema |
| Standard categories used | `architecture`, `coding`, `operational` | `architecture`, `coding` | **Shared categories**, not per-domain forks |
| Agent | backend-agent (13-field contract) | frontend-agent (13-field contract) | **Same contract**, zero changes |
| Domain Router | `agents/backend/ROUTER.md` | `agents/frontend/ROUTER.md` | Same format |
| MANIFEST | Backend row | + Frontend row (additive) | Same Tier-0 file, one new row |
| Review | Pass 0001 (5 outputs) | Pass 0002 (5 outputs) | Same framework |
| Acceptance | Standards A1–A5, Agent A1–A4 | Standards A1–A5, Agent A1–A4 | **Same criteria** |
| Impact edges | `standards_enforced` → agent | `standards_enforced` → agent | Same engine |
| Guardrails | Tier G core G1–G5 | *reused unchanged* (no domain guardrail needed) | Core is domain-agnostic |

## 2. The Concern-Category Design, Validated

The single most load-bearing genericity claim from the [Architecture Hardening Report](architecture-hardening-m0-m4.md) was: *Standards are organized by concern and scoped by path, so domains share category trees rather than forking parallel ones.* Frontend proves it concretely — the generated indexes now interleave both domains:

- [`standards/architecture/INDEX.md`](../../standards/architecture/INDEX.md): `backend-layering` + `persistence-dao` (mcp-server) **and** `frontend-component-layering` + `frontend-config-content` (web) — 4 units, one category, two domains.
- [`standards/coding/INDEX.md`](../../standards/coding/INDEX.md): `backend-naming` (mcp-server) **and** `frontend-hooks-location` + `frontend-shadcn-usage` (web) — 3 units, two domains.

Each Agent's `standards_enforced` selects only its domain's units; the shared index is not a collision, it is the point. No `standards/frontend/` or `standards/backend/` silo was created. Had the design been domain-siloed, this expansion would have required new category trees — it did not.

## 3. Cross-Domain Invariants, Enforced by Tooling (not by trust)

The two-domain state is the first real exercise of the H1–H3 hardenings:

- **Authority disjointness (H2):** with *two* Active Agents, `aios validate` reports `authority:0` — it mechanically confirmed `web/**` and `mcp-server/**` do not overlap. This check did nothing observable with one domain; with two, it is the guarantee that the domains can't silently claim each other's code.
- **Reference integrity (H1):** all Frontend `depends_on` / `standards_enforced` / `validated_against` refs resolve (`refs:0`) — including the intra-Frontend chain `frontend-config-content → frontend-component-layering`.
- **Impact scoping:** `aios impact standards/coding/frontend-hooks-location --change major` flags **only** `agents/frontend/frontend-agent` — not the Backend Agent. Impact is correctly per-domain, driven by declared edges, not by module-wide fan-out.

## 4. What Was Reused Unchanged (the Constitution)

Not one of these was edited to add Frontend:

- `foundation/` (vision, architecture, bootstrap) — untouched.
- `kernel/` (boot, behavior, routing, loading, validation, recovery, guardrails, lifecycle) — untouched.
- The **routing model** in `router/README.md` — untouched (only MANIFEST *content* gained a row).
- **Schema** (`base`, `standard`, `agent`, `guardrail`) — untouched; the Frontend units fit the existing fields exactly.
- **Lifecycle** — untouched; Frontend used the same `Proposed→…→Approved→(Acceptance)→Active`.
- **Governance** (RFC/Review/Acceptance/Impact/Changelog) — untouched; **no RFC was needed** because adding a domain is additive.
- **Tooling** (`aios.py`) — untouched; the same binary validated, indexed, and impact-analyzed Frontend.

## 5. What Was Added (purely additive)

New files only, plus additive rows: 4 Frontend Standards, 1 Frontend Agent, 1 Domain Router, 1 Review Pass; one row each in `router/MANIFEST.md` and the `agents/README.md` domain registry; the `web/CLAUDE.md` adapter updated to point at the new domain; regenerated category indexes; changelog entries. Every one of these is an *instance* of an existing type, not a change to any type.

## 6. Constitution-Untouched: Verification

`aios check` → **PASS**: 12 units `[refs:0 drift:0 authority:0]`, 619 links, 6 routing files under ceiling. `git diff --stat` scope for M5 is confined to new domain files + additive registry/manifest/adapter/changelog lines — no `foundation/`, `kernel/`, `schema/`, `governance/` framework, `router/README.md`, or `tools/aios.py` edits.

## 7. Verdict

**The abstraction generalizes to two distinct domains with zero Constitution change.** Backend (Python/FastAPI/DAO) and Frontend (Next.js/React/shadcn) are about as different as two web-stack domains get, yet both are expressed entirely through the same contracts, schema, routing model, lifecycle, governance, and tooling — the only differences are *content* and *scope values*.

Two concrete design bets paid off: (a) concern-categories shared across domains (§2), and (b) authority disjointness enforced mechanically (§3). Both are exactly what the next domains will lean on.

**Further horizontal expansion (Mobile, Security, Infrastructure, …) is evidentially justified.** Each follows the identical additive pipeline. The deferred backlog from the Architecture Hardening Report (typed frontmatter, data-driven impact rules, domain-scoped guardrail fan-out, owner registry, block-list YAML) remains untriggered by this expansion; none is a prerequisite for the next domain — revisit only if a future domain produces real evidence it is needed, per the frozen-architecture rule.
