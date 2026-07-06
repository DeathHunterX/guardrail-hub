# Architecture Hardening Report — M0–M4

Date: 2026-07-06
Scope: the AIOS implementation after M0–M4, assessed for **generality** — do the abstractions hold beyond Backend, or are they overfit to the one vertical slice built so far?
Method: critical re-read of schema, tooling, routing, governance, and the Backend slice, with code-level verification of tooling claims.

> Gate: M5 (Horizontal Expansion) proceeds only if the architecture is stable enough. Verdict in §7.

---

## 1. Strengths (abstractions that are genuinely generic)

- **The Product Lane is domain-agnostic.** Tier G → MANIFEST → Domain Router → Agent → Standards → Guardrails → Validation → Review is pure mechanism; only the *content* per hop is Backend-specific. Frontend/Security reuse the identical lane. Proven, not asserted.
- **Standards are organized by concern, scoped by path.** `category` is a concern (`coding`, `architecture`, …), and `applies_to` globs carry the domain scope (`mcp-server/**`). A future `frontend-naming` is `category: coding, applies_to: [web/**]` — it lives beside `backend-naming` under `standards/coding/`, distinguished by scope, not siloed per domain. This is the single most important genericity win: domains share concern-categories rather than forking parallel trees.
- **Schema fields are reference/glob-shaped, not Backend-shaped.** `decision_authority`, `applies_to` (path globs), `standards_enforced`, `depends_on` (id refs) all generalize to any domain unchanged. No field encodes "Backend."
- **Routing cost is bounded by *domain count*, not *unit count*.** MANIFEST grows one row per Domain; Domain Routers and Category Indexes shard by the recursive ceiling rule. 500 units do not enlarge Tier 0.
- **The tooling/content split held under real load.** Every M3–M4 unit was validated, indexed, and impact-analyzed by `aios`; the dogfooding principle caught real errors (block-list YAML, forward-ref links) at authoring time.
- **Governance composes cleanly.** Validation/Review/Acceptance are three orthogonal gates; the RFC/Impact/Changelog machinery ran twice for real without contradiction.

## 2. Weaknesses (genericity gaps found)

- **W1 — Frontmatter cross-references are not integrity-checked.** *(verified in code: `cmd_validate` checks schema + `id`==path only.)* A typo in an Agent's `standards_enforced` or a unit's `depends_on` (e.g. `standards/coding/backend-namng`) **validates clean** and silently creates no edge. The namespace-as-contract promise ("a rename that breaks a reference is detectable") is **documented but not enforced.**
- **W2 — `validated_against` is authored but never consumed.** *(verified: no command reads it.)* The governance producer/consumer version-sync mechanism (§Release Management, §Impact Analysis) exists on paper; no tool checks that a unit's `validated_against: X@1.0.0` still matches X's current version. Version drift is currently invisible to automation.
- **W3 — Agent `decision_authority` overlap is a prose Acceptance criterion, not a tool check.** Acceptance A1 ("no two Active Agents own the same path") is checked by hand. Deterministic, automatable — currently isn't.
- **W4 — The impact "guardrail → all agents" rule is core-guardrail-shaped.** `compute_impact` flags *every* agent on any `guardrails/*` change. Correct for Tier G core rules (they bind everyone); over-broad for future *domain* guardrails (`guardrails/security/*`), which should flag only affected agents.
- **W5 — Owners are nominal strings.** `backend-owner`, `security-owner`, `evaluation-owner` don't resolve to real accountable parties. Fine for bootstrap; unsound as an accountability model at scale.

## 3. Technical Debt

- **TD1 — Manual module-README summary tables drift.** Proven in M4 (standards/agents tables went stale in M3). Fixed for those two (pointers to generated indexes); `knowledge`/`skills`/`workflows`/`templates`/`playbooks` still carry manual "0 units" tables — accurate now, will drift on first content.
- **TD2 — Impact rules encode module semantics as string-prefix checks** (`startswith('guardrails/')`, `'agents/'`, `'playbooks/'`). Works; not data-driven. A new consumer type needs a code edit, not config.
- **TD3 — Frontmatter is stringly-typed.** The parser stringifies everything; the validator has only object/array/string. A future numeric/boolean field (`priority: 3`, `blocking: true`) can't be typed correctly.
- **TD4 — Block-list YAML unsupported** (from M3): multi-item fields are long single lines.
- **TD5 — Lifecycle chain restated in 6 module READMEs** (from M0): a future lifecycle change touches all six.
- **TD6 — Benchmark coverage is one path** (Fix Bug). RFC Evaluation can only regress against the Backend path.

## 4. Scaling Risks (100+ Agents / 500+ Knowledge / many Domains)

- **SR1 (High) — Silent reference rot.** Without W1, dangling `depends_on`/`standards_enforced` accumulate invisibly across domains; Impact Analysis then under-reports blast radius (a missing edge = a consumer never flagged). This directly erodes the correctness of the governance loop *precisely* as cross-domain references multiply.
- **SR2 (High) — Authority collisions.** Without W3, two domains' agents can both claim overlapping paths (e.g. a shared `lib/`), producing ambiguous dispatch — exactly the failure a Domain namespace was meant to prevent, undetected.
- **SR3 (Medium) — Impact fan-out noise.** W4 at 100 agents: any guardrail edit flags all 100. Tolerable for rare core changes; noisy and imprecise once domain guardrails exist.
- **SR4 (Low) — Full-tree scans.** `aios` re-parses all units each run. O(n) per command; fine at CI scale to ~thousands, but there is no incremental/`--since`/`--domain` mode.
- **SR5 (Low) — Cross-domain task routing is unexercised.** MANIFEST maps a task to one Domain; genuinely cross-cutting tasks rely on the (untested) agent Consult/Delegate model.

## 5. Breaking Changes to Do Now

**None are architecturally breaking** — the schema, contracts, and routing need no incompatible redesign. That is the headline finding: the abstractions are sound. What *is* recommended before M5 are three **additive tooling** hardenings that enforce invariants M5 will immediately stress:

- **H1 (do now) — `aios validate` resolves frontmatter refs.** Every `depends_on` / `standards_enforced` / `validated_against` target must exist as a unit `id` (strip `@version`); fail loud otherwise. Closes W1/SR1. Additive, ~30 lines.
- **H2 (do now) — `aios` checks Agent `decision_authority` non-overlap** across Active agents; fail on collision. Closes W3/SR2. Additive.
- **H3 (do now, small) — `aios` flags `validated_against` version drift** (pinned version ≠ target's current version → report, matching the `NeedsRevalidation` semantics). Closes W2. Additive; makes the version-sync promise real.

All three are pure additions to the CLI — no artifact changes, no schema changes, no RFC (they don't alter Constitution). They should precede M5 because reference rot and authority overlap are cheap to prevent and expensive to unwind once N domains exist.

## 6. Breaking Changes to Defer

- **Typed frontmatter (TD3)** — add number/boolean support only when a schema actually needs a typed field. No current need; adding speculatively violates "don't build ahead of need."
- **Data-driven impact rules (TD2)** — refactor the prefix checks into config when a *new consumer type* first appears, not before.
- **Domain-scoped guardrail impact (W4)** — refine "all agents" to "affected agents" when the *first domain guardrail* is authored (M5-era), which is when the distinction first exists.
- **Real owner registry (W5)** — replace nominal owner strings with a resolvable registry when there are real teams to map; premature now.
- **Converting remaining manual README tables to pointers (TD1)** — do it lazily, per module, as each gains its first unit.
- **Block-list YAML (TD4)** — a deliberate, documented parser extension if multi-item fields proliferate; not urgent.

## 7. Readiness for M5

**~85%.**

- **Architecture / abstractions: ~95% ready.** No breaking changes needed; genericity verified (Product Lane, concern-scoped Standards, glob/ref-shaped schema, domain-bounded routing). This is the part that had to be right before scaling, and it is.
- **Tooling completeness: ~70% ready.** Three integrity invariants the architecture *promises* (ref resolution, authority non-overlap, version-drift) are not yet enforced by automation — and M5 is exactly the workload that stresses them.

**Recommendation:** do **H1–H3** (additive, no rework, no RFC) as a short pre-M5 hardening step, then begin M5. With H1–H3 landed, readiness is ~95% and Horizontal Expansion rests on enforced — not merely documented — invariants. Proceeding to M5 *without* them is possible but accepts SR1/SR2 as growing silent debt.

**The architecture is stable enough to expand; the tooling should be hardened first.**
