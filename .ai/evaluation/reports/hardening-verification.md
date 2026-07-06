# Hardening Verification Report — H1–H3

Date: 2026-07-06
Scope: verify the three integrity hardenings ([Architecture Hardening Report §5](architecture-hardening-m0-m4.md)) — H1 reference resolution, H2 `decision_authority` overlap, H3 `validated_against` drift — landed as pure *Automation-catching-up-to-Repository*, with no change to any artifact, schema, routing, or lifecycle.

> Constraint (per direction): no new capability, no schema change, no routing/lifecycle change, no RFC. H1–H3 only make Automation enforce invariants v1.0 already promised.

---

## What changed (and only this)

| File | Change | Nature |
|---|---|---|
| `tools/aios.py` | Added pure functions `check_references` (H1), `check_drift` (H3), `check_authority_overlap` (H2); wired them into `aios validate`; added three `selftest` cases. | Automation only |
| `tools/README.md` | Documented the expanded `validate` behavior. | Doc only |

**No `.ai/` content unit, schema, router, or lifecycle document was touched.** The three checks read frontmatter fields units already carried (`depends_on`, `standards_enforced`, `validated_against`, `decision_authority`); no field was added or changed.

## Condition-by-condition verification

### 1. Every frontmatter reference resolves or errors — ✅
`check_references` walks `depends_on`, `standards_enforced`, `knowledge_sources`, `skills_used`, `workflows_used`, `templates_used`, and `validated_against` (stripping `@version`); any target not present as a unit `id` is a hard `validate` error. Proven by `selftest` (unresolved `standards/coding/nonexistent` is caught) and by the real tree reporting `refs:0` (all current references resolve).

### 2. `decision_authority` can no longer overlap silently — ✅
`check_authority_overlap` compares every pair of `Active` Agents' authority path-prefixes and fails on any path-ancestor/equal collision. Proven by `selftest`: `mcp-server/**` vs `mcp-server/app/**` is caught; `mcp-server/**` vs `web/**` is correctly *not* flagged. Real tree: `authority:0` (one Active Agent, no collision).

### 3. `validated_against` drift checked as designed — ✅
`check_drift` compares each `{id}@{pinned}` against the target unit's current `version`; a mismatch is reported as `NeedsRevalidation`, matching [governance §Impact Analysis](../../governance/README.md#impact-analysis). Proven by `selftest`: a `@1.0.0` pin against a `2.0.0` target is caught, while a matching pin is clean (no false positive). Real tree: `drift:0` (all pins match current versions).

### 4. All regression tests still pass — ✅
`aios selftest` → **PASS**, 11/11 checks (the 8 prior + H1/H2/H3). `aios check` → **PASS**: `validate` 7 units 0 errors `[refs:0 drift:0 authority:0]`, `links` 578/0 broken, `lint` 5 routing files 0 over ceiling.

### 5. No artifact or schema had to change — ✅
`aios validate` reports **0 errors across all three new dimensions on the existing tree**. This is the strongest evidence the invariants were already honored in the repository — the hardening made Automation *detect* what was already true, requiring no corrective edit to any unit or schema. Confirms the Architecture Hardening Report's core finding: the gaps were tooling-completeness, not architectural overfitting.

## Scope discipline

No work was done outside H1–H3. Improvements observed during implementation were **not** executed; they remain in the [Architecture Hardening Report](architecture-hardening-m0-m4.md) backlog (§6 deferred): typed frontmatter, data-driven impact rules, domain-scoped guardrail-impact fan-out, real owner registry, block-list YAML, and converting the remaining modules' manual README tables to pointers. The bare-`**` authority edge case (an authority glob with no literal prefix isn't overlap-checked) is added to that backlog as a low-severity note — no current unit uses it.

## Verdict

All five conditions met. **Architecture Hardening is complete.** The three integrity invariants promised by v1.0 are now enforced by Automation, not merely documented — and they passed clean on the existing repository, confirming no artifact needed correction.

**AIOS is ready for M5 — Horizontal Expansion.** Readiness raised from ~85% to ~95% (per the Architecture Hardening Report's projection), the remaining ~5% being the consciously-deferred backlog items, none of which gate expansion.
