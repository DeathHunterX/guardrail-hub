# 0001 — AIOS Implementation Roadmap & Bootstrap Strategy

Status: **Accepted**
Owner: Loi Phan
Date: 2026-07-06

---

## Context

Architecture v1.0 of the AIOS (`.ai/`) is frozen: Context Loading Strategy (4-tier Router — Global → Domain → Category → Unit), Namespace/Dependency/Versioning conventions, Scalability model (bounded fan-out, frontmatter-driven indexing), Governance & Lifecycle (unified state machine, Impact Analysis, Archive), and the foundational operating principle:

> AI is responsible for reasoning. Repository is responsible for truth. Automation is responsible for determinism.

None of this has been built yet. Every module beyond `intelligence/` is still "Specified, zero units." The question this decision answers is not *what* the architecture is — that is settled — but **in what order it gets built**, given that a wrong build order can silently re-introduce the exact failures the architecture exists to prevent (divergent truth between docs, AI doing mechanical work Automation should own, content authored before there's anything to validate it against).

## Decision

Implementation proceeds through five ordered milestones, M0 through M4, followed by an open-ended steady-state phase M5. A milestone does not start until its prerequisites are met; where prerequisites are independent, work inside a milestone runs in parallel.

| Milestone | Goal | Depends on | Parallelizable internally | Definition of Done |
|---|---|---|---|---|
| **M0 — Constitution Reconciliation** | Rewrite `kernel/README.md`, `router/README.md`, `agents/README.md`, `governance/README.md`, `guardrails/README.md`, `kernel/boot/README.md`, `kernel/routing/README.md`, `foundation/architecture.md` (Lifecycle diagram only), plus small terminology/completeness fixes to `standards/README.md`, `knowledge/README.md`, `workflows/README.md`, `templates/README.md`, `skills/README.md` so they describe the *frozen* v1.0 model (two-lane startup, 4-tier Router as static artifact, Domain-grouped Agents, Guardrails in the always-full-RFC list, unified lifecycle with `Archived`), not the pre-v1.0 model they currently describe. | None | Yes — 13 independent file edits | No sentence in any `.ai/` doc contradicts a v1.0 decision. |
| **M1 — Schema & Skeleton** | Define one canonical frontmatter schema (base + per-module extension fields); create empty scaffolding: `router/MANIFEST.md` with a first real Domain (Backend), `guardrails/core.md` (empty), template `INDEX.md` per existing category. | M0 | Yes — schema authoring and skeleton creation are independent tracks | Schema file exists and is referenced by every module contract; skeleton files exist in correct locations and format. |
| **M2 — Deterministic Tooling** | Build the scripts Automation owns: schema validator (first), then in parallel — index generator, reverse-dependency builder, link/reference checker, line-count ceiling linter — then Impact Analysis (depends on reverse-dependency builder). | M1 | Yes, except Impact Analysis waits on reverse-dependency builder | Every script runs cleanly against the empty M1 tree; a synthetic two-unit test with a declared `depends_on` proves reverse-dependency + Impact Analysis work end-to-end. |
| **M3 — First Vertical Slice** | Push one real Domain (Backend/`mcp-server`, per `intelligence/module-map.md` — the only domain with real code) end-to-end: real Guardrail core rules, one real Agent, one Domain Router, 3–5 real Standards distilled from `intelligence/conventions.md`, a real `router/MANIFEST.md` entry, a real `AGENTS.md` + thin `CLAUDE.md` adapters. | M2 (may overlap with it — see Trade-offs) | Standard-authoring and Agent-contract-authoring can proceed in parallel | A fresh AI session completes a real `mcp-server` coding task using only the Product Lane, never touching `foundation/` or framework docs; an intentional Major bump on one of the 3–5 Standards is correctly flagged by Impact Analysis. |
| **M4 — Governance Loop Activation** | Run the designed-but-never-executed processes for real: one Review pass, one Evaluation benchmark ("Fix Bug"), one full RFC. | M3 | No — this is a linear proof exercise | One real RFC has merged through the full flow; one Review pass produced all five required outputs per `review/README.md`. |
| **M5 — Horizontal Expansion** *(steady state, not a one-time milestone)* | Repeat the M3 pattern per new Domain (Frontend/`web` next, then Security, Infra, …), each addition purely additive to Global Router. | M4 | Yes — different Domains are independent by design | N/A — this is the system's permanent operating mode, not a phase with an exit. |

---

## Why M0 → M5, specifically

Each boundary marks a *different kind of prerequisite becoming satisfied* — not an arbitrary chunking of work:

- **M0 exists because "Repository is responsible for truth" fails silently otherwise.** The current text of `router/README.md`, `kernel/README.md`, etc. describes the pre-v1.0 model. Building `router/MANIFEST.md` (v1.0) while `router/README.md` still describes the old 2-hop model creates exactly the "divergent truth" failure Phase 0 was written to prevent — inside the very system meant to prevent it. This has already happened once in this project's short life (the original `CLAUDE.md` pointer had to be corrected once we learned more about actual tool behavior); M0 exists to not repeat that at architectural scale.
- **M1 exists because every later artifact needs one shared shape.** Scripts (M2) parse frontmatter; content (M3) carries frontmatter. If schema isn't fixed before either starts, both will drift out from under it. M1 is only scaffolding, not content — kept deliberately cheap and fast.
- **M2 exists as its own milestone, before content, per the frozen operating principle** — see next section.
- **M3 exists as a single Domain, not all Domains, before M4** — see the Vertical Slice section below.
- **M4 exists to distinguish "designed" from "proven."** Review, Evaluation, and Governance's RFC process were specified across five prior architecture conversations but have zero execution history. A framework that has never processed one real case is a hypothesis, not infrastructure.
- **M5 is explicitly not bounded** because the whole point of the preceding four milestones is to make Domain-addition a repeatable, additive operation — once proven once, it has no natural "done."

## Why Automation is built (M2) before Content is authored (M3)

This is the direct, literal application of the frozen principle: *Automation is responsible for determinism.* Two concrete failure modes motivate sequencing it first rather than deferring it until volume "justifies" it:

1. **Retrofitting is more expensive than building in advance.** If Standards/Knowledge/Agents are authored first without frontmatter discipline, adding it later means re-authoring every existing unit rather than producing new ones correctly from the start — the same reason a test harness is cheaper to build before a large test suite than after.
2. **A volume threshold that "justifies" tooling is a moving, self-serving target.** Deferring Automation until "enough" units exist means AI keeps doing Automation's job (duplicate-checking, manual dependency tracking) for an undefined, likely-underestimated stretch — precisely the condition the frozen principle exists to close off. Building the tooling first removes the judgment call of "is it worth it yet" entirely.

This does not mean zero manual work during bootstrap — see Trade-offs below for the one deliberate, bounded exception (M2/M3 overlap).

## Why Vertical Slice (M3) before Horizontal Expansion (M5)

Per `intelligence/system-overview.md`, exactly one Domain — Backend/`mcp-server` — has real, working code today; every other candidate Domain (Frontend beyond the marketing page, Mobile, Security, Infrastructure) is either a stub or has no code at all. Two consequences follow:

1. **Testing the pipeline against a real Domain validates against reality; testing against a fictional one validates against assumptions.** An Agent contract, a Standard, or a Domain Router written for a Domain with no real code cannot be checked against anything — its correctness is unverifiable by construction.
2. **A single Domain bounds the blast radius of an architecture mistake.** If the 4-tier Router, the frontmatter schema, or the Agent contract shape turns out to be wrong in some way only real use reveals, discovering that with one Domain costs one rework; discovering it after populating fifteen Domains costs fifteen.

## Trade-offs Considered and Rejected

| Rejected alternative | Why rejected |
|---|---|
| **Content-first, tooling deferred until volume justifies it** | Directly contradicts the frozen operating principle; see above. |
| **Skip M0, fix the descriptive docs opportunistically later** | Leaves `.ai/` self-contradictory for an unbounded period — a live violation of single-source-of-truth, not a cosmetic one. |
| **Fill all twelve modules broadly and shallowly across every anticipated Domain at once (horizontal-first)** | Spreads Review/Impact-Analysis testing across mostly-fictional Domains; violates the Architecture's own caution against creating structure ahead of real need. |
| **Pre-declare the complete Domain taxonomy before any implementation** | Contradicts "Additive Evolution" (Phase 0) — Domains are meant to register as real need appears, not be exhaustively planned upfront. |
| **Fully parallelize M0 through M5 to save calendar time** | Building Impact Analysis (M2) against a frontmatter schema that content-authoring (M3) is simultaneously still shaping risks building automation against a moving target. The one exception granted — M2/M3 may overlap — is bounded specifically because M3's unit count is small enough (3–5 Standards, 1 Agent) for a human to reconcile by hand once M2 lands; this does not generalize to overlapping schema design with content authoring at any larger scale. |

## Conditions That Would Require Revising This Roadmap

This roadmap is the execution plan until one of the following is observed during implementation — at which point it is *this decision* that gets superseded by a new one, not silently reordered:

- **M3 reveals the Backend Domain doesn't generalize** (e.g., its Agent/Standard shape turns out to be Backend-specific in ways that don't transfer) — revisit before starting M5, not after multiple Domains have copied a flawed pattern.
- **A second Domain's real code emerges before M4 completes** (e.g., `web/` gains real dashboard functionality) — the reasoning for strict M3-before-M5 sequencing was the *absence* of a second real Domain; that premise changing is grounds to run two vertical slices concurrently.
- **Impact Analysis (M2) proves impractical to build or maintain at current unit counts** — grounds to extend the manual-bootstrap exception rather than block on tooling that isn't paying for itself yet.
- **Governance overhead (RFC/Review per Major bump) measurably blocks legitimate velocity once M5 is underway** — grounds to revisit *severity thresholds* (what qualifies as Major), not the M0–M5 sequence itself.
- **A security-relevant gap is found in Guardrails before M3's scheduled `guardrails/core.md` work** — per the standing exception already agreed (serious issues found during implementation override sequencing), Guardrail authoring jumps ahead of its M3 slot immediately, without waiting for a new decision record.

## Consequences

- No new `.ai/` file is created before M0 is complete — this decision itself is the only exception, being the record of the plan rather than a build artifact.
- Every subsequent implementation session can check its own step against this table instead of re-deriving sequencing from conversation history that isn't persisted anywhere else in the repository.
- Deviating from this order — other than the explicitly named exceptions above — requires a new Decision record marking this one Superseded, not a silent reordering.
- Each milestone closes with a **Milestone Review** logged in [`.ai/milestones/`](../milestones/README.md) — a historical record of how that milestone's execution actually went (planned vs. actual scope, files changed, lessons, debt). Milestone Reviews are bookkeeping, not governance: they never authorize or supersede a Decision. See [milestones/README.md](../milestones/README.md) for the record contract.

## Addendum — 2026-07-06: M0 scope expanded from 5 to 7 files

While executing M0, two Kernel sub-module documents not in the original file list were found to restate the pre-v1.0 model in ways that would leave `.ai/` internally contradictory even after the original 5 files were reconciled:

- `kernel/boot/README.md` defined Tier 0 as `foundation/` + `kernel/` loaded unconditionally every session — the exact definition M0 exists to retire.
- `kernel/routing/README.md` described a single, flat Agent registry, without the Domain-grouping introduced for dispatch-table lookup at scale.

Per the repository-integrity rule adopted before M0 began, this was stopped and reported rather than silently fixed. Decision: expand M0's file list to include both (reflected in the Decision table above) rather than defer them to backlog, because leaving them unreconciled would fail M0's own Definition of Done — an internal contradiction between `kernel/README.md` and its own sub-modules is exactly the kind of divergent truth M0 is chartered to eliminate. This is a scope clarification of M0's boundary, not a reversal of the roadmap's sequencing or reasoning, and does not require a new Decision record.

## Addendum — 2026-07-06: M0 scope expanded a second time, from 7 to 8 files

While reconciling `governance/README.md`'s lifecycle rules (adding `Archived` as a terminal state after `Deprecated`), found that `foundation/architecture.md#lifecycle-per-knowledge-unit-in-any-module` — the canonical per-unit lifecycle diagram every other module's own "Lifecycle" section links back to — still shows `Deprecated → [*]` with no `Archived` state and no `UnderRevision` loop. Leaving it unreconciled would mean the just-updated `governance/README.md` contradicts the one document every module treats as the authoritative source for this diagram — a more central inconsistency than the M0-round-one findings, since `foundation/architecture.md` is upstream of six-plus modules rather than one Kernel sub-file.

Decision: expand M0 to include `foundation/architecture.md`, scoped strictly to the Lifecycle diagram section — no other part of that document (module contracts, dependency graph, scalability strategy) is touched, since only the lifecycle diagram was found to conflict. Same reasoning as the first addendum: this is a boundary clarification of M0, not a reversal of the roadmap, and does not warrant a new Decision record.

## Addendum — 2026-07-06: M0 scope expanded a third time, from 8 to 13 files

After reconciling `foundation/architecture.md`'s canonical lifecycle diagram, found six further modules that don't merely link back to it but **restate** the lifecycle chain themselves, now stale relative to the `Archived`/`UnderRevision` update: `agents/README.md` (own diagram uses `Retired` instead of the now-unified `Archived`), `standards/README.md` (own "Review Lifecycle" diagram ends at `Deprecated → [*]`), and `knowledge/README.md`, `workflows/README.md`, `templates/README.md`, `skills/README.md` (each restates the chain in one prose line ending at `Deprecated`).

Judged lower severity than the two prior findings — none of these six assert something actively false or serve as an upstream canonical source others depend on; they're self-contained restatements that simply predate the terminology update. Decision: fix anyway, since a state diagram terminating at `Deprecated → [*]` is still, strictly, a claim that nothing follows Deprecated — a real (if quiet) instance of the same contradiction class M0 exists to close. Fixes are mechanical: rename `Retired`→`Archived` in one file, append `→ Archived` to five prose/diagram chains. `evaluation/README.md`'s own "Benchmark Lifecycle" diagram was deliberately left untouched — it was never a restatement of the general unit lifecycle, it governs a different kind of artifact (a benchmark, not a knowledge/standard/etc. unit) and legitimately keeps its own `Retired` state for its own domain-specific meaning.

## Addendum — 2026-07-06: three standing implementation principles adopted before M2

Adopted by human direction at the M1→M2 boundary; they govern the remainder of implementation (M2 onward), not just M2:

1. **Evaluate before adding a dependency.** A new third-party library (pyyaml, jsonschema, …) enters the tooling only when its benefit is shown to exceed its cost (environment setup, supply-chain surface — pointedly relevant for a security platform's own tooling). Standard-library-only is the default; the burden of proof is on adding a dependency, not on avoiding one. This retires the M1 review's tentative assumption that M2 "will install pyyaml + jsonschema" — that is now a claim to be justified, not a given.
2. **One unified CLI, not a pile of scripts.** M2's tools are subcommands of a single entry point (`aios validate` / `aios index` / `aios impact` / …) so CI and any AI need remember only one command. Independent one-off scripts are not the deliverable.
3. **Dogfooding from M2 onward.** Once a tool exists, it is the *only* sanctioned way to perform its check — validation, link-checking, index generation, impact analysis all run through the CLI, never by hand. Manual verification (as used through M0–M1 out of necessity) stops being acceptable the moment the CLI can do it. A milestone's verification section from M2 on cites CLI invocations, not hand checks.

These are recorded here (rather than only in the tooling README) because principles 1 and 3 are cross-milestone governance commitments, and traceability requires them to live in the repository, not just in session history.

## Related Documents
[`.ai/README.md`](../README.md) · [`.ai/foundation/vision.md`](../foundation/vision.md) · [`.ai/governance/README.md`](../governance/README.md) · [`.ai/review/README.md`](../review/README.md) · [`.ai/intelligence/system-overview.md`](../intelligence/system-overview.md)
