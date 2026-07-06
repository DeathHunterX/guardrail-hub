# Milestone Review — M1: Schema & Skeleton

Closed: 2026-07-06
Roadmap: [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md), milestone M1

---

## 1. Objective

Fix the *shape* every AIOS unit conforms to before any real content or tooling is built: one canonical machine-readable frontmatter schema (base + per-type extensions), plus the empty-but-valid skeleton files (`router/MANIFEST.md`, `guardrails/core.md`, the Category Index format). Definition of Done: schema file exists and is referenced by every module contract; skeleton files exist in correct locations and format.

## 2. Planned Scope vs. Actual Scope

Two scope interpretations were surfaced as forks and **ratified by the human before execution** (not decided inside this review):

| Fork | Ratified choice | Rationale |
|---|---|---|
| `INDEX.md` per existing category (~38 files) vs. format-template only | **Format-template only** ([router/INDEX.template.md](../router/INDEX.template.md)) | An `INDEX.md` is a *generated artifact* (M2 emits it from frontmatter); hand-creating 38 empty ones before the generator exists contradicts the model. A category gets its index when it gains its first unit. |
| Extension schemas for all unit types vs. M3 types only | **M3 types only** (Standard, Agent, Guardrail) | "Don't build ahead of need." Base schema already covers every type; other extensions are authored when their module gets a first real unit. |

Both refine the literal wording of M1's DoD ("template `INDEX.md` per existing category") toward the frozen architecture's intent. Recorded here as observations of a human-ratified interpretation, per the milestones principle that a Review observes rather than decides.

## 3. Files Changed

**Created (8):**
- `schema/base.schema.json`, `schema/standard.schema.json`, `schema/agent.schema.json`, `schema/guardrail.schema.json` — JSON Schema (draft 2020-12), base + three M3-type extensions via `allOf`.
- `schema/README.md` — spec, non-module status, `id`=path rule, extension-authoring pattern, how M2 consumes it.
- `router/MANIFEST.md` — Tier 0 lookup table; lane classification + Backend Domain registered (Domain Router marked pending M3).
- `router/INDEX.template.md` — canonical Category Index format the M2 generator emits.
- `guardrails/core.md` — valid, loadable Tier G file with base frontmatter; zero rules yet.

**Edited (12 module contracts, schema pointer added):** `standards/`, `agents/`, `knowledge/`, `skills/`, `workflows/`, `templates/`, `playbooks/`, `guardrails/`, `evaluation/`, `examples/README.md` point to their `<type>`/`base` schema; `decisions/`, `memory/README.md` carry an explicit *non-applicability* note (append-only ADRs / auto-captured entries adopt the schema only on promotion) — so "referenced by every module contract" resolves to a stated answer everywhere, not silence.

**Also:** `milestones/README.md` (added the "observations, not decisions" principle).

## 4. Verification Performed

All deterministic, via stdlib scripts — no eyeballing:

- **JSON validity** of all 4 schemas (`json.load`) → PASS.
- **`guardrails/core.md` frontmatter** structurally checked against `base.schema.json`'s required fields, `version`/`id`/`status` patterns, and the `id`=path rule → PASS.
- **Relative-link check** over all 16 created/edited M1 files (147 links) → PASS (the only miss was a forward-reference to this review file, which now resolves).

Note: full JSON-Schema validation (`pyyaml` + `jsonschema`) was **not** run — those libraries aren't installed, and installing/wiring them is M2's charter, not M1's. The stdlib checks above confirm well-formedness sufficient for a skeleton; M2's validator is what will enforce the schemas in full.

## 5. Lessons Learned

- **Building schema-as-data (M1) separately from validator-as-code (M2) held up cleanly.** The schemas are complete, valid, and ready for M2 to consume with a stock `jsonschema` validator — no rework anticipated. This is the Automation-before-Content sequencing paying off exactly as Decision 0001 predicted.
- **Verification itself re-confirmed why M2 exists.** M1 verification was done by throwaway stdlib scripts because the real validator doesn't exist yet — the same "AI plays Automation by hand" window M0 noted. The scripts written here (`verify_m1.py`, `linkcheck_m1.py`, in scratchpad) are effectively a spec for two of M2's tools (schema validator, link checker).
- **A skeleton file can still carry a latent design decision.** `guardrails/core.md` looked trivial but forced the question of guardrail-rule granularity (see debt below) — a reminder that even "empty" scaffolding commits to a shape.

## 6. Deviations

- No deviation from milestone *sequencing* or DoD *intent*. The two DoD *wording* refinements (§2) were ratified before execution.
- Unlike M0, M1 required **no mid-milestone scope expansion** — the file set was known up front and held.

## 7. Technical Debt / Backlog Discovered

- **OPEN QUESTION for M3 — guardrail rule granularity.** `guardrail.schema.json` describes an individual guardrail *rule* (`scope`, `checkpoint`, `enforcement`), but `guardrails/core.md` is the Tier G *container* file, currently validating against `base.schema.json` only. Undecided: whether core rules live as entries *in core.md's body* (keeping Tier G one file) or as *separate unit files* under `guardrails/core/` (cleaner per-rule frontmatter, but Tier G then loads a directory). This is an M3 authoring decision, not an M1 one — flagged, not resolved. When resolved, it goes through a Decision or is recorded in M3's design, per the "Reviews observe, not decide" principle.
- **`pyyaml` + `jsonschema` not installed.** M2's first setup step. Until then, all frontmatter/schema verification is stdlib-approximate.
- **Latent from M0, unchanged:** lifecycle-restatement debt (6 modules copy the chain) and the `Retired` terminology note still stand; neither blocks M2.

## 8. Prerequisites Met for M2

- Machine-readable schema exists for M2's validator to consume. ✓
- Category Index format spec exists for M2's index-generator to emit. ✓
- A minimal skeleton tree (`MANIFEST.md`, `core.md`) exists for M2's scripts to run against. ✓
- DoD met: schema files exist and every module contract references the schema (or states its non-applicability); skeleton files exist in correct locations and format (INDEX.md as ratified format-template). ✓
- No blocking debt — the one open question (§7) is M3-scope and does not gate M2's tooling work.

**M2 — Deterministic Tooling may begin.** Its first step is installing `pyyaml` + `jsonschema` and turning the M1 verification scripts into the real validator + link-checker.
