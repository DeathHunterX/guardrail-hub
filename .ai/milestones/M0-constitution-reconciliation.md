# Milestone Review — M0: Constitution Reconciliation

Closed: 2026-07-06
Roadmap: [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md), milestone M0

---

## 1. Objective

Rewrite the descriptive documents in `.ai/` so none of them still describes the pre-v1.0 model, leaving the repository self-consistent with frozen Architecture v1.0 before any new file (`router/MANIFEST.md`, `guardrails/core.md`, …) is created. Definition of Done: *no sentence in any `.ai/` doc contradicts a v1.0 decision.*

## 2. Planned Scope vs. Actual Scope

- **Planned:** 5 files — `kernel/README.md`, `router/README.md`, `agents/README.md`, `governance/README.md`, `guardrails/README.md`.
- **Actual:** 13 files, reached through three documented scope expansions, each stopped-and-confirmed with the human before proceeding:

| Expansion | Added | Trigger |
|---|---|---|
| 5 → 7 | `kernel/boot/README.md`, `kernel/routing/README.md` | Kernel sub-files restated the old Tier 0 (`foundation/`+`kernel/`) and a flat Agent registry |
| 7 → 8 | `foundation/architecture.md` (Lifecycle diagram only) | The canonical lifecycle diagram every module links to still ended at `Deprecated → [*]`, no `Archived` |
| 8 → 13 | `standards/`, `knowledge/`, `workflows/`, `templates/`, `skills/README.md` (+ `agents/` diagram) | Six modules *restate* the lifecycle chain rather than linking it; all stale after the `Archived` addition |

Sequencing and reasoning of the roadmap were unchanged — only M0's file-list boundary grew.

## 3. Files Changed

**Reconciled (13):** `kernel/README.md`, `kernel/boot/README.md`, `kernel/routing/README.md`, `router/README.md`, `agents/README.md`, `governance/README.md`, `guardrails/README.md`, `foundation/architecture.md`, `standards/README.md`, `knowledge/README.md`, `workflows/README.md`, `templates/README.md`, `skills/README.md`.

**Supporting (not reconciliation targets, changed as part of recording M0):** `decisions/0001-aios-bootstrap-roadmap.md` (three addenda documenting the scope expansions; Decision table file-list updated), `decisions/README.md` (scope widened to admit AIOS-process narrative records; Index added — done when 0001 was first created).

**Substantive changes by theme:**
- Two-lane startup (Product / Meta / First-Contact) replacing the single linear chain — `kernel/README.md`.
- Tier redefinition: Tier G = `guardrails/core.md`, Tier 0 = `router/MANIFEST.md`, Constitution demoted to Meta-Lane-only — `kernel/README.md`, `kernel/boot/README.md`.
- Router as materialized static artifact (4-tier) rather than runtime algorithm; routing cache = the persisted files — `router/README.md`.
- Domain as routing namespace above flat-authority Agents; per-Domain registry — `agents/README.md`, `kernel/routing/README.md`.
- Guardrails in the always-full-RFC set + core/domain split + no `Stale` — `guardrails/README.md`, `governance/README.md`.
- Impact Analysis gate, Archived state, Release Management added — `governance/README.md`, `foundation/architecture.md`.
- Unified lifecycle terminology (`Archived`, `UnderRevision`) propagated across six restating modules.

## 4. Verification Performed

- **Per-file contradiction check** against each v1.0 decision — every one of the 13 maps to a specific corrected passage (verification table produced at milestone close).
- **Link/anchor audit** of all newly introduced cross-references — found and fixed **3 self-introduced broken anchors** (`#automation-and-human-review`, and two `#automation` links to a non-existent heading) plus one stale count ("Three mechanisms" → "Four").
- **Coherence re-read** of the three most heavily edited files (`kernel/README.md`, `router/README.md`, `governance/README.md`) end-to-end after all edits.
- **Non-contradiction check** of untouched files (`kernel/behavior|loading|validation|recovery|lifecycle`, `review/`, `evaluation/`, `memory/`, `playbooks/`, `intelligence/*`) — confirmed none asserts the pre-v1.0 model.

## 5. Lessons Learned

- **Single-source-of-truth was itself violated by the pre-v1.0 docs.** The old lifecycle chain was *copied* into six modules rather than referenced once — which is exactly why M0 ballooned from 5 to 13 files. The v1.0 principle "link, don't restate" should be applied to these six as a cleanup so the next lifecycle change touches one file, not seven (logged as debt below).
- **M0 was a live demonstration of why M2 (Automation) is worth building.** Every broken anchor, stale count, and copied-diagram found here is exactly what a link/consistency checker would catch mechanically. Until M2 exists, every doc edit carries a manual-audit tax — this is the bounded "AI plays Automation by hand" window Decision 0001 explicitly anticipated, and it was real, not hypothetical.
- **Stop-and-report earned its keep.** All three scope expansions were surfaced and confirmed rather than silently absorbed; each is now traceable as an addendum. The alternative (quietly fixing the extra files) would have left the Decision's file list wrong and the expansions unexplained.

## 6. Deviations

- File count grew 5 → 7 → 8 → 13. Not a deviation from roadmap *sequencing or reasoning* — M0's charter ("reconcile everything that contradicts v1.0") was always the true scope; the initial "5 files" was an under-estimate of how widely the old model had been restated. All three expansions are documented as addenda to Decision 0001 and were human-confirmed before execution.
- No other deviation. Order of milestones, DoD, and the Automation-before-Content principle were untouched.

## 7. Technical Debt / Backlog Discovered

- **Lifecycle restatement debt (low urgency).** Six modules (`standards/`, `knowledge/`, `workflows/`, `templates/`, `skills/`, `agents/`) hold their own copy of the lifecycle chain. They are now consistent, but any future lifecycle change must edit all of them again until they are converted to pure references to `foundation/architecture.md`. Candidate cleanup for a later milestone.
- **No consistency tooling yet (expected, = M2 charter).** M0 relied entirely on manual auditing for links, anchors, and cross-file consistency. This is not a surprise — M2 is scheduled precisely to remove it — but it is a standing risk on every doc edit until then.
- **Terminology collision to watch: `Retired`.** `evaluation/README.md`'s benchmark lifecycle legitimately keeps a `Retired` terminal state (a benchmark is a different artifact than a knowledge/standard unit). Since the general unit lifecycle's old `Retired` was renamed to `Archived` in `agents/`, the word `Retired` now means one specific thing (benchmark-only) in the repo. Not a conflict today; flagged so a future reader doesn't reintroduce `Retired` as a general-lifecycle state.

## 8. Prerequisites Met for M1

- Definition of Done achieved: no `.ai/` document contradicts a v1.0 decision. ✓
- Repository is self-consistent and independently usable — a fresh reader today gets one coherent model, not two competing ones. ✓
- M1's only stated dependency is M0. Satisfied. ✓
- No blocking debt from §7 — all three items are either low-urgency cleanup or expected-and-scheduled (M2). None gates M1.

**M1 — Schema & Skeleton may begin.**
