# Milestone Review — M2: Deterministic Tooling

Closed: 2026-07-06
Roadmap: [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md), milestone M2

---

## 1. Objective

Build the Automation layer that owns every mechanical check — validation, link checking, index generation, reverse-dependency/impact analysis, ceiling linting — so that from this point on those checks run by tool, not by hand. Definition of Done: every check runs cleanly against the M1 tree; a synthetic unit test with a declared `depends_on` proves reverse-dependency + Impact Analysis end-to-end.

## 2. Planned Scope vs. Actual Scope

Delivered as planned, shaped by the three principles adopted at the M1→M2 boundary ([Decision 0001 addendum](../decisions/0001-aios-bootstrap-roadmap.md)):

- **Dependency principle → stdlib-only.** The M1 review's tentative "install pyyaml + jsonschema" was evaluated and rejected. Frontmatter is parsed by a stdlib subset parser; schemas by a ~150-line mini JSON-Schema validator covering exactly the feature set the shipped schemas use. Human-ratified before coding.
- **Unified-CLI principle → one `aios` entry point** with seven subcommands, not seven scripts.
- **Dogfooding principle → the CLI is now the only sanctioned verification.** The throwaway stdlib scripts from M1 (`verify_m1.py`, `linkcheck_m1.py`) are superseded by `aios validate` / `aios links` and discarded.

No mid-milestone scope expansion.

## 3. Files Changed

**Created (3):**
- `tools/aios.py` — the CLI: frontmatter parser, fail-loud mini JSON-Schema validator, and the `validate` / `links` / `index` / `impact` / `lint` / `check` / `selftest` subcommands.
- `tools/schema-map.json` — path-glob → schema mapping (first-match-wins); encodes the provisional `guardrails/core.md → base` mapping pending M3's rule-granularity decision.
- `tools/README.md` — CLI docs, the standard-library-only rationale, non-module status, dogfooding contract.

No `.ai/` content files were changed — M2 is tooling, not content, so the tree it operates on is exactly M1's.

## 4. Verification Performed (by tool, per the dogfooding principle)

All via CLI invocation — no hand checks:

- **`aios selftest` → PASS (7/7 checks):** major bump propagates transitively (a→b→c + playbook); minor bump gives agents `Informational` but playbooks `NeedsRevalidation`; patch propagates to nobody; a guardrail change fans out to every agent; the validator accepts a valid unit and rejects an invalid one; an unsupported schema keyword fails loud; **every shipped schema stays within the validator's supported feature set** (regression guard so M3's first real Standard/Agent/Guardrail can't crash on an unexercised keyword). This exceeds the DoD's "two-unit `depends_on`" bar.
- **`aios check` → PASS** on the whole `.ai/` tree: 1 unit validated (`guardrails/core.md` vs `base.schema.json`, `id`==path confirmed), 465 relative links resolve, 1 routing file under the 150-line ceiling.
- **Individual subcommands** exercised: `validate` (verbose), `index --dry-run` (0 indexes — correct, no category units exist yet), `impact guardrails/core --change patch` (0 consumers — correct, no agents exist yet), `lint`.

## 5. Lessons Learned

- **The stdlib decision paid off with one non-obvious safety requirement: fail-loud.** A hand-rolled validator's real risk isn't the features it implements but the ones it silently ignores. Making unsupported keywords a hard error — plus a selftest that asserts every shipped schema is covered — converts "we didn't check that" from an invisible gap into a loud failure. Without that, stdlib-validation would have been a false economy.
- **Dogfooding immediately retired manual work, as intended.** M0 and M1 verification tables listed hand checks; this one lists CLI commands. The transition the dogfooding principle mandated happened cleanly at exactly the milestone it was scheduled for.
- **selftest is the right home for engine-correctness proofs.** Putting the impact-rule and validator proofs inside `aios selftest` (temp fixtures, no repo pollution) means they run as a permanent regression gate, not a one-time demonstration.

## 6. Deviations

- None from sequencing or DoD intent.
- One *additive* hardening beyond the literal DoD: selftest check (7) verifies all shipped schemas are within the validator's supported set. Not required by the DoD, added because the alternative — discovering an unsupported keyword only when M3 authors its first unit — would be a latent crash. Additive, not a deviation.

## 7. Technical Debt / Backlog Discovered

- **M1 open question still open (now with a provisional handling): guardrail rule granularity.** `schema-map.json` maps `guardrails/core.md → base` and `guardrails/**/*.md → guardrail` as a placeholder. M3 must decide whether core rules live in `core.md`'s body or as per-rule files, then update the map. Flagged for M3, not resolved here.
- **`index` and `impact` are proven by logic (selftest) but not yet by real repo data**, because no category units or inter-unit dependencies exist yet. M3 is their first real exercise — watch for surprises when the first Standard/Agent lands.
- **No CI to run `aios check` automatically.** It is manual-invoke until the product repo gains CI ([intelligence/deployment-map.md](../intelligence/deployment-map.md) confirms none exists). Expected, not a defect; wiring `aios check` as a non-blocking CI step is the natural task once a pipeline exists.
- **Latent from M0/M1, unchanged:** lifecycle-restatement debt (6 modules) and the `Retired` terminology note. Neither blocks M3.

## 8. Prerequisites Met for M3

- `aios validate` exists → M3's real units (Standard/Agent/Guardrail) get validated through the tool as they're authored, satisfying dogfooding from unit one. ✓
- `aios index` exists → the first category to gain a unit gets a generated INDEX.md. ✓
- `aios impact` exists → the M3 DoD ("an intentional Major bump on one of the 3–5 Standards is correctly flagged by Impact Analysis") is now runnable, not aspirational. ✓
- `schema-map.json` is ready to route the new unit types (Standard, Agent, Guardrail extensions all confirmed within the validator's feature set). ✓
- One decision M3 must make early: **guardrail rule granularity** (§7) — it gates how guardrail rules are authored and mapped.

**M3 — First Vertical Slice (Backend) may begin.**
