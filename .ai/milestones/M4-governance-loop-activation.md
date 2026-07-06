# Milestone Review — M4: Governance Loop Activation

Closed: 2026-07-06
Roadmap: [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md), milestone M4

---

## 1. Objective

Run the governance processes that were designed but never executed — RFC, Review, Acceptance, Evaluation, Changelog — for real, proving they are working infrastructure rather than specifications. Definition of Done ([Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)): one real RFC merged through the full flow; one Review pass producing all five required outputs. Plus the layer the user added at the M3→M4 boundary: **Acceptance Criteria**, introduced as M4's first RFC.

## 2. Planned Scope vs. Actual Scope

Delivered the plan. The Acceptance Criteria addition was incorporated as **RFC-0001** (human-ratified approach — dogfood the RFC flow on a substantive governance change). One in-scope integrity fix was folded in: stale module-README summary tables left over from M3 (see §7). No other scope change.

## 3. Files Changed

**New record locations (frameworks anticipated them; first instantiated now):**
- `governance/rfcs/` — [README](../governance/rfcs/README.md) + [RFC-0001 (Acceptance Criteria)](../governance/rfcs/0001-acceptance-criteria.md) + [RFC-0002 (Activate Core Guardrails)](../governance/rfcs/0002-activate-core-guardrails.md).
- `review/passes/` — [README](../review/passes/README.md) + [Pass 0001 (M3 Backend slice)](../review/passes/0001-m3-backend-slice.md).
- `evaluation/benchmarks/` — [fix-bug](../evaluation/benchmarks/fix-bug.md) benchmark unit.
- Per-module changelogs: `guardrails/CHANGELOG.md`, `standards/CHANGELOG.md`, `agents/CHANGELOG.md`.

**RFC-0001 applied changes:** `foundation/architecture.md` (lifecycle `Approved → Active` now guarded by Acceptance), `governance/README.md` (Acceptance section + changelog-instantiation note), `standards/`, `agents/`, `guardrails/README.md` (per-type Acceptance Criteria).

**Status transitions (→ Active):** 4 Standards + Backend Agent (via Review Pass 0001 + Acceptance); `guardrails/core` 0.2.0 → 1.0.0 (via RFC-0002 + security sign-off).

**Integrity fixes (§7):** `standards/README.md` and `agents/README.md` stale summary tables replaced with pointers to the generated indexes / real ROUTER; `evaluation/README.md` Index updated with the Fix Bug result.

## 4. Verification Performed

**Governance processes executed (the milestone's substance):**
- **RFC flow, twice** — RFC-0001 (Acceptance Criteria) and RFC-0002 (guardrail activation) each ran Proposal → Architecture Review → (conditional module reviews: none triggered) → Evaluation → Merge, with applied-changes recorded. DoD "one full RFC merged" — met (two).
- **Review pass** — [Pass 0001](../review/passes/0001-m3-backend-slice.md) produced all five required outputs (Summary, Risk Analysis, Violations, Recommendations, Approval Decision) across the 5 M3 units; Approved with 3 logged Minor findings. DoD "one Review pass, five outputs" — met.
- **Acceptance gate** — each unit checked against its type's new Acceptance Criteria before `Active` (Standards A1–A5, Agent A1–A4, Guardrail A1–A4). All passed.
- **Evaluation** — [Fix Bug benchmark](../evaluation/benchmarks/fix-bug.md) established and run: **Pass**, at Expected Context (Constitution-tier docs not loaded). Now the regression baseline.

**By tool (dogfooding):**
- `aios validate` → 7 units, 0 errors (6 prior + the fix-bug benchmark).
- `aios check` → PASS (validate + links + lint) after all M4 files exist.
- The link-checker caught, in real time, forward-references to not-yet-created M4 files (RFC-0002, this review) — integrity enforcement during the milestone, not after.

## 5. Lessons Learned

- **Dogfooding the first RFC on a real change was the right call.** RFC-0001 delivered a genuine governance improvement (the Acceptance layer) *and* exercised the flow — far better evidence than an RFC on a throwaway change would have given.
- **Bootstrapping a governance loop has real chicken-and-egg moments, and honesty beats faking them.** RFC-0001's Evaluation step had no benchmark baseline (the benchmark didn't exist yet); rather than invent a result, the RFC records the gap explicitly, and RFC-0002 then ran against the now-existing baseline. The loop closed *within* the milestone, visibly.
- **The Validation/Review/Acceptance separation earned itself immediately.** The Agent's Acceptance criterion A2 ("all `standards_enforced` are Active") forced the correct ordering — Standards to `Active` first, then the Agent — a readiness constraint neither correctness nor quality checks would have caught.

## 6. Deviations

- **Fixed M3-introduced drift during M4.** `standards/README.md` still said "0 standards" and `agents/README.md` "no ROUTER" — factual contradictions once M3 added content. Per the repository-integrity rule, these were fixed (replaced with pointers to the generated/real sources) while those files were already open for Acceptance Criteria. In-scope integrity fix, recorded here.
- **Instantiated three new record-location trees** (`governance/rfcs/`, `review/passes/`, `evaluation/benchmarks/`). Anticipated by the frameworks; not new architecture, just first use.

## 7. Technical Debt / Backlog Discovered

- **Manual module-README summary tables are a systemic drift risk.** M3 proved it: adding units silently staled the `standards`/`agents` README tables. Fixed those two by pointing to source-of-truth. But `knowledge/`, `skills/`, `workflows/`, `templates/`, `playbooks/` README Index tables still say "0 units" — currently accurate, but they will drift the moment those modules gain content. Candidate: convert all such tables to pointers, or generate them. Not urgent (those modules are empty).
- **Only Fix Bug benchmark exists.** The other benchmarks (Implement API, Create Scanner, …) await the Domains/Workflows they exercise (M5+).
- **Latent, unchanged:** block-list frontmatter unsupported (M3), lifecycle-restatement in 6 modules (M0), `Retired` terminology note, no product CI to auto-run `aios check`.

## 8. Prerequisites Met for M5

- The full governance loop is proven executable end-to-end: RFC (×2), Review pass (5 outputs), Acceptance gate, Evaluation baseline, Changelog. ✓
- The Backend vertical slice is fully `Active` — a complete, live reference for the next Domain to copy. ✓
- Acceptance Criteria exist for the three instantiated unit types; the pattern for adding others is documented. ✓

**M5 — Horizontal Expansion** is now unblocked: repeat the M3 pattern (author → validate → Review → Accept → Activate, all dogfooded) for the next real Domain — Frontend/`web` per [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md) — reusing the proven loop. M5 is steady-state, not a bounded milestone.
