# Architecture Maintenance Plan — From Design to Protection

**Date:** 2026-07-20
**Phase transition:** architecture design → **architecture protection**.
**Constraints honoured:** no redesign, no new architectural concepts, no new ADRs. Every invariant below is already ratified; nothing here invents one.
**Deliverable type:** plan. Implementation follows the roadmap in §8.

> **Status update — 2026-08-28:** the historical baseline below no longer describes automation coverage exactly. CI now runs `aios check` on pushes and pull requests, and that gate includes domain/runtime boundaries plus Intelligence drift. The remaining fitness-test matrix has not been re-audited; GitHub branch protection must still mark the workflow status as required.

---

## 0. The finding that shapes everything

Measured on 2026-07-20:

| | Count |
|---|---|
| Ratified backend architectural rules | **21** (backend-layering 4, domain-layer 5, persistence-dao 4, service-package-design 8) |
| Rules mechanically enforced | **2** (domain-layer D2, D3, via `aios arch`) |
| Automated gate that runs without a human choosing to | **0** — no CI, no pre-commit hook, no Makefile |

**~10% of the ratified architecture is mechanically enforced, and the enforcement that exists runs only when someone remembers to run it.**

That second fact is the more serious of the two. A perfect gate nobody runs enforces nothing. The architecture survived five audits because a motivated reviewer kept looking; that is exactly the dependency this phase must remove. Analysis in §3 shows **16 of 21 rules are statically decidable** — the gap is largely one of *implementation effort*, not of feasibility.

---

## 1. Architecture Maintenance Plan

**Principle: every ratified rule is either mechanically enforced, or explicitly declared human-judgment with a named trigger. No rule may sit in the undeclared middle** — that middle is where the six severity definitions grew.

Four pillars:

1. **Extend `aios arch` from a domain-purity check into the architecture fitness suite.** It already exists, already runs inside `aios check`, and already has the right shape (scan source, report violations, exit non-zero). Strengthening it is preferable to introducing a second tool — one command, one place to look.
2. **Make the gate run automatically.** CI on push/PR, plus a pre-commit hook and a `make check` target for local use. Until this exists, every other improvement is optional in practice.
3. **Classify enforcement honestly.** Three tiers: **Blocking** (mechanically decidable, violation is always wrong), **Warning** (heuristic, high signal but false positives possible), **Review** (genuinely needs judgment). Publish the tier per rule so nobody assumes coverage that does not exist.
4. **Close the loop on every historical defect.** §6 maps each previously-eliminated defect to the specific check that prevents its return. A defect without a check is not fixed; it is merely absent today.

**Non-goals, stated to prevent churn:** no new layers, no renames, no ADRs, no reorganisation. Architectural stability is now the objective; the plan adds *checks*, not *structure*.

---

## 2. Architecture Fitness Test Matrix

Tier key: 🔴 Blocking · 🟡 Warning · 👤 Review. Status: ✅ exists · 🔨 to build.

### 2.1 domain-layer (ADR-0007/0008)

| Rule | Invariant | Executable check | Tier | Status |
|---|---|---|---|---|
| **D1** | Canonical ownership — one definition per business concept | Name-collision scan: any `class Severity\|Finding\|FindingSummary\|FindingIdentity\|Confidence\|OperationPhase` defined outside `app/domain/**` | 🔴 | 🔨 |
| **D1b** | No shadow copies of a canonical enum | Structural: any `str, Enum` whose member-value set equals a domain enum's, defined outside `domain/` | 🟡 | 🔨 |
| **D2** | Domain purity — no framework/transport/infra | Import scan of `app/domain/**` against forbidden module roots | 🔴 | ✅ |
| **D3** | Domain depends on nothing outside domain | Import scan: no `app.*` import in `domain/` except `app.domain` | 🔴 | ✅ |
| **D4** | Canonical vocabulary | (a) same scan as D1; (b) no domain symbol named `total`; (c) forbid `NormalizedSeverity`, `Assessment` as type names | 🔴 | 🔨 |
| **D5** | Boundary translation — native models stay in adapters | Domain must not import `app.schemas.tools.*` (subsumed by D3); tool wire types must not appear in `services/notification/**` | 🟡 | 🔨 |

### 2.2 backend-layering

| Rule | Invariant | Executable check | Tier | Status |
|---|---|---|---|---|
| **R1** | Only sanctioned top-level roles exist | Directory-name allowlist under `app/` | 🔴 | 🔨 |
| **R2** | Audience/tool sub-partitioning where it already exists | Naming convention check under `routers/`, `schemas/`, `services/` | 🟡 | 🔨 |
| **R3** | A new tool follows the ZAP layout | For each `services/tools/<t>/`, require `schemas/tools/<t>/`, `integrations/<t>/`, `routers/mcp/<t>_router.py` | 🟡 | 🔨 |
| **R4** | Dependency direction `routers → services → integrations\|dao → domain` | **Full import-graph check across all layers** (today only the domain leg is covered) | 🔴 | 🔨 |
| **R4b** | No circular imports anywhere | Import-graph cycle detection | 🔴 | 🔨 |

**R4 is the single highest-value check not yet built.** It is the rule the whole taxonomy rests on, and four of five audits had to verify it by hand.

### 2.3 service-package-design (ADR-0006)

| Rule | Invariant | Executable check | Tier | Status |
|---|---|---|---|---|
| **R1** | Package root holds only application services | No `@dataclass`/`Enum`/`Protocol` defined at a `services/*/` root module | 🔴 | 🔨 |
| **R2** | Every package has an intentional façade | Each `services/*/` has `__init__.py` declaring `__all__` | 🟡 | 🔨 |
| **R3** | No construct-named subpackages | Directory-name denylist: `utils, helpers, misc, common, shared, models, types, base, objects` under `services/**` | 🔴 | 🔨 |
| **R4/R5** | Composition Root Exception + internal package protection | **Only `bootstrap.py`/`main.py` may import `services/*/<internal-subpkg>/**`; everything else imports package roots** | 🔴 | 🔨 |
| **R6** | Promotion is a deliberate decision | Diff-scoped: façade `__all__` grew → require justification in the PR | 👤 | 🔨 |
| **R7** | Package size trigger (>7 root files) | Count root-level modules per service package | 🟡 | 🔨 |
| **R8** | Architecture review trigger | Diff-scoped: new file adds a second renderer/adapter/policy to a package | 👤 | — |

**R4/R5 is the second highest-value check** — it protects every public API boundary established in the third pass, and is trivially decidable.

### 2.4 persistence-dao

| Rule | Invariant | Executable check | Tier | Status |
|---|---|---|---|---|
| **R1** | No ORM | Forbid `sqlalchemy`/`sqlmodel`/`tortoise` imports anywhere in `app/` | 🔴 | 🔨 |
| **R2** | One interface, one impl per backend | Structural: each `dao/<backend>/` implements `BaseOperationDAO` | 🟡 | 🔨 |
| **R3** | Backend chosen by config, not at call site | Forbid `dao.postgres`/`dao.dynamodb` imports outside `dao/` and its factory | 🔴 | 🔨 |
| **R4** | Services depend on the DAO interface | Same check as R3 | 🔴 | 🔨 |

### 2.5 Ratified invariants outside the four standards

| Invariant | Source | Executable check | Tier | Status |
|---|---|---|---|---|
| **Notification boundary** — adapters never parse rendered output | `notification-boundary-port-change.md` | Forbid `re` / `import re` under `app/integrations/**` | 🔴 | 🔨 |
| **Event contracts** — no untyped payloads | `event-contracts-migration.md` | Forbid `.payload` attribute access; forbid `DomainEvent(` direct construction outside `contracts.py` | 🔴 | 🔨 |
| **No transport types in services** | ADR-0006 step 6 | Forbid `fastapi`/`starlette` imports under `app/services/**` | 🔴 | 🔨 |
| **No empty scaffold packages** | ADR-0005 | Fail on any directory under `app/` containing no `.py` | 🔴 | 🔨 |
| **No 0-byte modules** | ADR-0005 | Fail on any 0-byte `.py` under `app/` | 🔴 | 🔨 |
| **AIOS unit integrity** | governance | `aios validate` (schema, id=path, version drift) | 🔴 | ✅ |
| **Doc link integrity** | governance | `aios links` | 🔴 | ✅ |
| **Routing file budget** | kernel | `aios lint` | 🔴 | ✅ |

**Totals: 26 invariants — 4 enforced today, 20 mechanically buildable, 2 human-judgment by nature.**

---

## 3. AIOS Enforcement Gap Analysis

**Where AIOS is already strong.** `aios validate` catches version drift and broken `validated_against` pins — that is genuine, unusual rigour, and it caught real cascades during the domain migration. `aios links` and `aios lint` keep the governance corpus navigable. `aios arch` proves domain purity on every run and was verified by negative test.

**Gap 1 — Coverage (2 of 21 rules).** The standards are well-written but mostly advisory. Every rule tiered 🔴 in §2 and marked 🔨 currently depends on a reviewer noticing. Historical record shows what that produces: six severity definitions, a persistence model in the API package, a 307-line helper class at a top-level role — none of which any check would have caught.

**Gap 2 — Execution (no automatic trigger).** This is the critical gap. `aios check` is documented as "intended to run non-blocking until the product repository gains CI." That CI never arrived. Consequently *zero* architectural enforcement is guaranteed on any change. **Fixing Gap 2 is worth more than any single new check**, because it converts existing checks from optional to mandatory.

**Gap 3 — Scope mismatch.** `aios arch` scans only `DOMAIN_ROOTS`. The other 19 rules govern `app/**`. The command needs to grow from a domain check to an architecture check — same command, wider scan, rule-tagged output.

**Gap 4 — Undeclared human rules.** D1, D4, D5, R6, R8 currently look enforced (they are Mandatory in Active standards) but are not. Any rule that cannot be automated must be *labelled* as review-tier so the team knows where discipline is genuinely load-bearing.

**Gap 5 — No architecture regression tests.** The 195 tests verify behaviour. None asserts an architectural invariant. Fitness tests should be runnable as tests too (`pytest tests/architecture/`), so a violation fails the normal test run even where CI is unavailable.

**Recommendation: strengthen, do not redesign.** Keep the AIOS structure exactly as ratified — extend `cmd_arch` into a rule-registry-driven check, add rule ids to output (`D2`, `R4`, …) so a failure cites the standard it violates, and wire it into CI. No new AIOS concepts, no new modules, no schema changes.

---

## 4. Continuous Architecture Workflow

| Stage | Runs | Checks | Outcome |
|---|---|---|---|
| **Author (local, optional)** | `make check` | Full suite + tests | Fast feedback; never the only gate |
| **Pre-commit hook** | on `git commit` | 🔴 fast static checks only (forbidden imports, denylists, empty dirs) | Blocks the commit; <2s budget |
| **Pull request (CI)** | on PR to `main` | `aios check` + `pytest` + full fitness suite | **🔴 blocks merge**; 🟡 posts warnings as review comments |
| **Diff-scoped review triggers** | on PR, from the diff | R6 (façade grew), R8 (second renderer/adapter/policy), any new top-level dir | **👤 requires human architectural sign-off** — labelled, not auto-blocked |
| **Merge to `main`** | post-merge | Full suite | Alerts on any escape |
| **Weekly scheduled** | cron | Full suite + drift + **intelligence-map freshness** | Warning-only; catches doc rot, not code |
| **On standard change** | when `.ai/standards/**` changes | `aios validate` + `aios impact` | Forces re-validation of dependent units |

**Auto-fixable (no human needed):** import formatting/ordering, empty `__pycache__`, trailing whitespace, regenerating `INDEX.md` via `aios index`. **Never auto-fixed:** anything moving a symbol between packages — that is an architectural decision even when the fix looks obvious.

---

## 5. Merge Gate Checklist

A PR merges only when all of the following hold.

**Blocking — automated, no override without a recorded exception:**

- [ ] `aios check` passes (validate · links · lint · arch)
- [ ] `pytest` passes, including `tests/architecture/`
- [ ] No forbidden import: domain purity (D2), domain isolation (D3), no ORM, no `fastapi` in `services/`, no `re` in `integrations/`, no concrete DAO outside `dao/`
- [ ] Dependency direction intact (R4); no new import cycles (R4b)
- [ ] No internal-subpackage import outside the composition root (R4/R5)
- [ ] No canonical concept redefined outside `domain/` (D1/D4)
- [ ] No construct-named package created (R3)
- [ ] No empty directory or 0-byte module added
- [ ] No `.payload` access / untyped event construction

**Warning — merges, but the reviewer must acknowledge:**

- [ ] Service package root file count ≤ 7 (R7)
- [ ] Every service package exposes `__all__` (R2)
- [ ] New tool follows the full four-location layout (R3)

**Human architectural review required when the diff:**

- [ ] adds a symbol to any façade `__all__` (R6 promotion)
- [ ] adds a second renderer, adapter, policy, or execution strategy to an existing package (R8)
- [ ] adds a top-level directory under `app/`
- [ ] changes a file under `.ai/standards/**` or `.ai/decisions/**`
- [ ] modifies `app/domain/**` (small, high-consequence surface)

---

## 6. Regression Prevention Matrix

Every defect eliminated during the architecture phase, and the specific check that prevents its silent return.

| # | Defect (as found) | Prevented by | Tier |
|---|---|---|---|
| 1 | **Severity defined six times** | D1 name-collision + D1b enum-shape scan | 🔴 + 🟡 |
| 2 | **`total` meaning two different things** | D4 — forbid a domain symbol named `total` | 🔴 |
| 3 | **`OperationStatus` inside a ZAP schema** | D1/D4 — canonical types only in `domain/` | 🔴 |
| 4 | **Suite aggregator could not represent `critical`** | D1b — severity sets must match the canonical enum | 🟡 |
| 5 | **Framework leakage into domain** | D2 (live) | 🔴 ✅ |
| 6 | **Domain importing application code** | D3 (live) | 🔴 ✅ |
| 7 | **Slack regex-parsing rendered output** | No `re` under `integrations/**` | 🔴 |
| 8 | **Untyped `dict[str, Any]` event payloads** | Forbid `.payload`; forbid direct `DomainEvent(` construction | 🔴 |
| 9 | **Dead defensive reads of never-published keys** | Typed contracts make it a `AttributeError`, not a silent `None` | structural |
| 10 | **`HTTPException` raised inside services** | No `fastapi` import under `services/**` | 🔴 |
| 11 | **Flat notification package (dumping ground)** | R7 root-file count + R8 review trigger | 🟡 + 👤 |
| 12 | **Construct-named `models/` package** | R3 directory denylist | 🔴 |
| 13 | **`helpers/` dumping ground** | R1 top-level allowlist *(after ADR-0012 removes the role)* | 🔴 |
| 14 | **Deep imports past package façades** | R4/R5 composition-root-only internal imports | 🔴 |
| 15 | **Empty scaffold dirs / 0-byte stubs** | Empty-directory + 0-byte module checks | 🔴 |
| 16 | **Duplicated constants (`_SERVER`, `SLACK_CHANNEL_NAME`)** | Duplicate-literal scan across `app/**` | 🟡 |
| 17 | **Persistence model in the API package** | R4 dependency direction + a `schemas/` purity rule | 🔴 |
| 18 | **Version drift in AIOS pins** | `aios validate` (live) | 🔴 ✅ |

**15 of 18 become mechanically prevented.** The three that do not (11 partially, 16 heuristic, 9 structural) are covered by warnings or by the type system rather than a check.

---

## 7. Remaining Architectural Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **No CI exists.** Every gate is optional in practice. | 🔴 **Critical** | §8 Phase 1 — nothing else matters until this lands |
| R2 | **D1/D4 enforcement is name-based**, so a genuinely novel duplicate concept (a new vocabulary word) escapes | 🟠 High | D1b structural scan + R6/R8 review triggers; accepted residual |
| R3 | **Two pre-existing test failures** are normalised. A permanently-red suite trains people to ignore red. | 🟠 High | Fix or quarantine with an explicit skip reason before CI turns on — a gate must start green |
| R4 | **ADR-0012 is unratified**, so `helpers/`/`constants/` remain sanctioned and R1's allowlist cannot exclude them | 🟡 Medium | Ratify ADR-0012, or encode the allowlist as-is and tighten later |
| R5 | **ADR-0009 hygiene (H1–H4) unimplemented** — the execution contract still names `ZapWorkerInfo` | 🟡 Medium | Every new tool inherits the wrong contract; cost grows with tool count |
| R6 | **Intelligence maps drift** — `module-map.md` is hand-maintained | 🟡 Medium | Weekly scheduled freshness warning |
| R7 | **Single-maintainer knowledge concentration.** The reasoning lives in review documents that no check reads. | 🟡 Medium | Rule-id-tagged failures citing the standard turn documents into runtime feedback |
| R8 | **Fitness suite itself could rot** (checks that never fire, or fire falsely) | 🟢 Low | Negative tests per check — the `aios arch` precedent: prove it fails before trusting it |

---

## 8. Prioritized Implementation Roadmap

Ordered by *protection delivered per unit of effort*, not by rule number.

### Phase 1 — Make enforcement mandatory (highest value, lowest effort)
1. **CI workflow** running `aios check` + `pytest` on every PR and push to `main`.
2. **Resolve the two failing tests** (fix or explicitly skip with a reason) so the gate starts green.
3. `Makefile` target `make check`, and a pre-commit hook running the fast 🔴 subset.

*Converts four existing checks from optional to mandatory. Nothing later matters without this.*

### Phase 2 — The two highest-value new checks
4. **R4 full dependency-direction check** across all layers + cycle detection.
5. **R4/R5 composition-root-only internal imports** — protects every façade boundary.

*Together these cover the two invariants the whole structure rests on, and both are trivially decidable.*

### Phase 3 — Close the canonical-ownership gap
6. **D1/D4 name-collision scan** (canonical types outside `domain/`; no `total`).
7. **D1b enum-shape scan** (shadow severity/phase sets).

*Directly prevents the defect that motivated the entire domain phase.*

### Phase 4 — Forbidden-import and structural sweep
8. No `fastapi` in `services/`; no `re` in `integrations/`; no ORM anywhere; no concrete DAO outside `dao/`; no `.payload` access.
9. Empty-directory, 0-byte module, and construct-named-package (R3) checks.
10. Top-level role allowlist (R1) — after ADR-0012 settles the two contested roles.

### Phase 5 — Warnings and review triggers
11. R7 package size, R2 façade presence, R3 tool layout, duplicate-literal scan → warning tier.
12. Diff-scoped review triggers (R6 façade growth, R8 second-of-a-kind) as CI labels.

### Phase 6 — Durability
13. **Negative tests for every check** — each must be proven to fail on an injected violation, following the `aios arch` precedent.
14. `tests/architecture/` mirror so fitness tests run in the normal suite.
15. Weekly scheduled run incl. intelligence-map freshness.

**Success criterion:** after Phase 4, every 🔴 invariant in §2 fails automatically on violation, and §6 shows 15 of 18 historical defects mechanically prevented. At that point the architecture no longer depends on anyone remembering why it looks the way it does — which is the only durable form of architectural stability.

---

## 9. What this plan deliberately does not do

No new layers, packages, renames, or ADRs. No changes to the ratified structure. No new architectural vocabulary. Every check proposed enforces a rule that was already ratified and already documented; the plan adds *verification*, never *design*. Where a rule genuinely cannot be automated (R6, R8, and the novel-concept half of D1), it is labelled review-tier rather than quietly assumed — because an invariant everyone believes is enforced, but isn't, is more dangerous than one openly known to need judgment.
