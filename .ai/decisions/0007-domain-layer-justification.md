# 0007 — Does a Domain Layer Now Earn Its Existence?

Status: **Accepted** — ratified, implemented and verified 2026-07-20. `domain/findings/` and `domain/lifecycle/` exist; six severity definitions and two lifecycle definitions collapsed to one canonical owner each. Governance landed with it: `backend-layering` 1.1.0 (adds the `domain/` role, extends R4), new Standard [domain-layer@1.0.0](../standards/architecture/domain-layer.md) (D1-D5), Backend Agent 1.2.0, and mechanical enforcement of D2/D3 via `aios arch`. See [domain-layer-migration-report.md](../architecture/evidence/domain-layer-migration-report.md).
Owner: Loi Phan
Date: 2026-07-20
Supersedes: nothing. Amended on ratification: `standards/architecture/backend-layering` 1.0.0 → 1.1.0 (R1 gains the `domain/` role; R4's chain extends to `→ domain`).

> **As built.** [Decision 0008](0008-domain-ubiquitous-language.md) settled the vocabulary first, as this ADR required — which is why the two conflicting meanings of `total` were resolved *by naming* (`finding_count` / `vulnerability_count`) rather than carried into the new layer. 0008 also renamed the proposed `SeverityBreakdown` to `FindingSummary` and rejected `Assessment`, `NormalizedSeverity`, and `Execution` as domain vocabulary.
>
> The nine-tool stress test ([domain-layer-growth-stress-test.md](../architecture/evidence/domain-layer-growth-stress-test.md)) produced five design amendments to §4.1/§6.1 that were **applied as built**: `FindingSummary` is a severity-keyed mapping rather than fixed fields, and neither DAST-shaped deduplication nor `_SEVERITY_ADVICE` was promoted into domain. `domain/lifecycle/` was unaffected.

---

## 1. Recommendation

**APPROVE a Domain layer — but only for two capabilities, and only because of duplication that exists today.**

| Candidate concept | Verdict |
|---|---|
| Severity / Findings aggregation rules | ✅ **Approve** — `domain/findings/` |
| Operation lifecycle phases | ✅ **Approve** — `domain/lifecycle/` |
| Scenario state | ❌ **Reject** — stays in the ZAP tool package |
| Event payloads | ❌ **Reject as Domain** — this is a Contracts problem, solved in `core/` |
| Notification presentation model | ❌ **Reject** — application/presentation concern, not domain |

Two of five candidates qualify. A proposal that approved all five would be folder-maximizing, which this ADR explicitly rejects as an outcome.

**The decisive argument is not "multi-tool is coming."** It is that the *same concept already disagrees with itself in production today*, in a product whose entire value proposition is reporting security findings accurately. Deferring costs correctness, not just tidiness.

---

## 2. Evidence

### 2.1 Severity is defined **six** times, with two genuine semantic conflicts

The fourth-pass review said five. Verification for this ADR found a sixth. Every site was read; this table is declared fact, not inference.

| # | Definition | Buckets | Casing | File |
|---|---|---|---|---|
| 1 | `ScanFindings` | 5 (incl. `critical`) | lower | `services/notification/models/operation_progress.py` |
| 2 | `ZapScanSummary` | 4 + `total` | lower | `schemas/tools/owasp_zap/scan_result.py` |
| 3 | `_SEVERITIES` | **4** (no `critical`) | lower | `services/tools/owasp_zap/suite/aggregator.py` |
| 4 | `RISK_ORDER` | 4 | **Capitalized** | `services/tools/owasp_zap/suite/findings.py` |
| 5 | `findings_from_summary` | 5, `critical` hardcoded `0` | lower | `helpers/tools/owasp_zap_helpers.py` |
| 6 | `_SEVERITIES` | 5 + emoji | Capitalized | `integrations/chat/slack/channel_adapter.py` |

**Conflict A — `total` means two different things in one data flow.** `ZapScanSummary.total = len(alerts)` (verified: `build_summary`, line 128) **includes** informational alerts. `ScanFindings.total` returns `critical + high + medium + low` and **excludes** informational, with the explicit comment *"Vulnerability total excludes informational (not an actual finding)."* Both are populated from the same scan, in sequence, via `findings_from_summary`. A scan producing zero vulnerabilities and five informational alerts therefore reports **total = 5** in the persisted report and **total = 0** in the Slack notification. Same scan, same field name, two numbers.

**Conflict B — cardinality.** The suite aggregator cannot represent a `critical` finding at all (4 buckets). Any scanner that reports critical severity — Trivy, Semgrep, Snyk all do — would have its most severe findings silently dropped from suite aggregation while appearing in single-scan notifications.

This is not a naming inconsistency. It is a correctness defect in a security product, adjacent to Guardrail **G3** ("never fabricate a security result or posture claim") — an under-counted severity total is an unearned reassurance.

### 2.2 Lifecycle is defined twice, and the code says why

`OperationStatus` (`schemas/tools/owasp_zap/common.py`) and `LifecyclePhase` (`services/notification/models/operation_progress.py`) have **identical members and identical string values**. The duplication is deliberate and documented: *"It intentionally mirrors the domain `OperationStatus` values by string value, but is defined here so the notification context does not import a tool/domain enum."*

That comment is the argument for this ADR, written by the codebase about itself. The notification context correctly refused to depend on a *ZAP tool schema* for a generic operation concept — and, having nowhere neutral to put it, copied it. **The absence of a domain layer directly caused the duplication.** Note also the misplacement it worked around: operation status is not a ZAP concept, yet it lives in `schemas/tools/owasp_zap/`.

### 2.3 The "first consumer wins" placement rule is already producing drift

Four domain concepts, four unrelated homes, each chosen by whichever context needed it first: severity rules → `suite/`, findings value object → `notification/models/`, lifecycle → duplicated, scenario state → `scenario/`. There is no answer to "where does a business rule go?", so the fifth engineer will invent a fifth location. This is drift in progress, not drift predicted.

### 2.4 Evidence *against* the proposal (stated plainly)

- **Multi-tool is aspiration, not code.** `intelligence/system-overview.md` line 50 lists Semgrep, Gitleaks, Trivy, Checkov, MobSF, OSV-Scanner, Schemathesis, Playwright, Selenium, JMeter as intended — with *"zero implementation for any of these."* `schemas/tools/jmeter/` is an empty directory. `AGENTS.md` warns: *"Treat README-described features as targets, not existing code."* **Any justification resting on future scanners is speculative generality** and is rejected as a basis for this decision.
- **One real bounded context.** Today there is one tool (OWASP ZAP). "Shared across bounded contexts" is partly satisfied by *notification vs. tool*, which is a weaker claim than *tool vs. tool*.
- **The prior three passes each declined a domain layer**, correctly, on YAGNI grounds. Reversing that requires new evidence — which §2.1/§2.2 supply, and which did not exist as *verified duplication* before this audit.
- **Cost is real:** a fifth top-level role, an amended Active Standard, import churn, and a new way for contributors to be wrong (anemic domain, or domain-as-dumping-ground — the exact failure mode Decision 0006 was written to prevent).

**Weighing it:** the aspiration argument is rejected; the duplication argument stands on its own. Severity would need fixing today even if ZAP were the only tool this product ever shipped, because §2.1 Conflict A is a live inconsistency between two existing components.

---

## 3. Domain Qualification Test — per candidate

Nine criteria. A concept qualifies only if *most* hold.

### 3.1 Severity & Findings Aggregation → ✅ **QUALIFIES (9/9)**

| Criterion | Result |
|---|---|
| Shared by multiple contexts | ✅ notification, suite aggregation, ZAP helpers, Slack adapter, persisted schemas — 6 sites |
| Business meaning | ✅ severity *is* the product's core vocabulary |
| Contains business rules | ✅ risk ordering, dedup grouping by `(rule_id, name, risk)`, overall-risk derivation, remediation advice (`_SEVERITY_ADVICE`), "informational is not a vulnerability" |
| Stable semantics | ✅ CVSS-style severity has been stable for two decades; independent of ZAP |
| Currently duplicated | ✅ six definitions, two semantic conflicts (§2.1) |
| Lacks a clear owner | ✅ no single answer to "where is Severity defined?" |
| Framework-independent | ✅ plain enum + value object |
| Transport-independent | ✅ Slack's copy is the *symptom* |
| Infrastructure-independent | ✅ no I/O |

**Rejection test (arguing against):** *"Severity is just an enum — a shared constant does not justify a layer; put it in `constants/`."* — Rebutted: it is not only an enum. `findings.py` holds genuine business rules (ranking, deduplication, recommendation derivation) and `ScanFindings` holds a rule (`total` excludes informational). `constants/` cannot host behavior, and hosting rules there would make `constants/` a domain layer with a misleading name. *"ZAP tops out at High, so `critical` is dead weight."* — Rebutted: `critical` already exists in three of six definitions; the inconsistency is present regardless.
**Survives both sides. Approve.**

### 3.2 Operation Lifecycle → ✅ **QUALIFIES (8/9)**

| Criterion | Result |
|---|---|
| Shared by multiple contexts | ✅ operations, notification, ZAP dispatch/suite, DAO persistence |
| Business meaning | ✅ "an operation is queued/running/completed/failed/cancelled" is domain vocabulary |
| Contains business rules | ⚠️ **Partial** — `is_terminal` is the only rule; transition legality is implicit in `OperationService` |
| Stable semantics | ✅ unchanged since the ChatOps work (Decision 0004) |
| Currently duplicated | ✅ verbatim, with a code comment explaining why (§2.2) |
| Lacks a clear owner | ✅ currently owned by a *ZAP tool schema*, which is demonstrably wrong |
| Framework-independent | ✅ `str` enum (note: `OperationStatus` is imported by Pydantic models but is not itself framework-bound) |
| Transport-independent | ✅ |
| Infrastructure-independent | ✅ |

**Rejection test:** *"Just move `OperationStatus` to `core/` and delete `LifecyclePhase` — no layer needed."* — This is the strongest counter-argument in the ADR, and it is **half right**: it would fix the duplication. It is rejected as the *complete* answer because `core/` is currently infrastructure plumbing (config, logger, ports, events); adding business vocabulary there makes `core/` the unnamed domain layer, repeating the "first consumer wins" mistake one level down. If the owner prefers the cheaper fix, taking lifecycle to `core/` alone is a **defensible partial ratification** — recorded here so that choice is available without a second ADR.
**Survives. Approve, with the alternative noted.**

### 3.3 Scenario State → ❌ **REJECTED (4/9)**

| Criterion | Result |
|---|---|
| Shared by multiple contexts | ❌ **one consumer**, `ZapApiScenarioService` |
| Business meaning | ⚠️ workflow mechanics (placeholder substitution, cookie/JWT propagation) — HTTP-protocol shaped, not business-shaped |
| Contains business rules | ✅ dependency ordering, topological sort |
| Stable semantics | ⚠️ tied to `ScenarioStep`, a ZAP request schema |
| Currently duplicated | ❌ **not duplicated anywhere** |
| Lacks a clear owner | ❌ clearly owned by `scenario/` |
| Framework-independent | ⚠️ imports Pydantic `ScenarioStep` |
| Transport-independent | ❌ models cookies, bearer tokens, `Set-Cookie` |
| Infrastructure-independent | ✅ |

**Why not Domain:** zero duplication, one owner, one consumer, and it manipulates HTTP transport concepts. It is *pure* (no I/O), and purity is what made the fourth-pass review call it "domain-like" — but **purity is not domainhood**. Promoting it would move working, well-isolated code away from its only consumer for symmetry alone.
**Reject. It stays exactly where it is.**

### 3.4 Event Payloads → ❌ **REJECTED as Domain (problem is real, layer is wrong)**

The fourth-pass review flagged untyped `dict[str, Any]` payloads and `EVENT_OPERATION_*` living inside `operations/operation_service.py`. Both are genuine defects (HIGH-1). But an event contract is an **integration contract**, not business knowledge: it describes *how contexts talk*, not *what is true about security scanning*. Its natural home is beside the port it travels through — `core/ports/event_publisher.py` already defines `DomainEvent`.
**Reject as Domain; fix as Contracts in `core/`.** Recorded so the finding is not lost by being declined here.

### 3.5 Notification Presentation Model → ❌ **REJECTED**

`OperationProgress`'s presentation half (title, target, `next_action`, `debug`, the L1–L4 hierarchy) is view-model material. Its *domain* half is covered by §3.2 lifecycle + §3.1 findings. Presentation belongs to the application/presentation layer.
**Reject.** The split of `OperationProgress` remains an application-layer refactor, independent of this ADR.

---

## 4. Candidate Capability Boundaries

Organized by **business capability**, never by Python construct. No `models/`, `enums/`, `constants/`, or `dataclasses/` directories — a rule this ADR inherits from Decision 0006 Rule 3 and applies to itself.

```
app/domain/
    findings/          # what a security finding is, and how findings aggregate
    lifecycle/         # what an operation's lifecycle is
```

Two packages. Not three, not eight.

### 4.1 `domain/findings/`

- **Owner:** backend-owner (security domain).
- **Responsibility:** the canonical definition of severity and the rules for aggregating, ranking, deduplicating, and summarizing findings across any scanner.
- **Public API:** `Severity` (5 members: critical, high, medium, low, informational), `SeverityBreakdown` (replaces `ScanFindings` — with **one** documented `total` rule resolving §2.1 Conflict A), `Finding`, risk ordering/ranking, `aggregate`, `deduplicate`, `overall_risk`, `derive_recommendations`.
- **Explicitly NOT allowed:** Slack/Block Kit or any transport formatting; emoji tables; Markdown/SARIF/JSON rendering; Pydantic request/response models; DAO or persistence models; FastAPI types; ZAP-specific alert shapes (`ZapAlert` maps *into* `Finding` at the tool boundary); file paths, URLs, settings, logging.
- **Note:** SARIF rendering stays in `suite/reporter.py` — SARIF is an interop *format*, not domain knowledge. `_SARIF_LEVEL` correctly stays with the renderer.

### 4.2 `domain/lifecycle/`

- **Owner:** backend-owner.
- **Responsibility:** the canonical operation lifecycle and its legal transitions.
- **Public API:** `OperationPhase` (the single enum replacing `OperationStatus` + `LifecyclePhase`), `is_terminal`, and — if transition rules are made explicit — `can_transition_to`.
- **Explicitly NOT allowed:** persistence concerns; event names or payload shapes (those are `core/` contracts per §3.4); notification/presentation fields; tool vocabulary (`batch_type`, `operation_type`); Pydantic; any import from `services/`.

---

## 5. Dependency Rules

Domain is the **innermost** layer. Its defining property: it imports nothing from this application except itself.

| From ↓ / May depend on → | domain | schemas | core | dao | integrations | services | routers |
|---|---|---|---|---|---|---|---|
| **domain** | ✅ (own pkgs) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| schemas | ✅ | ✅ | ⚠️ existing | ❌ | ❌ | ❌ | ❌ |
| core | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| dao | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| integrations | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| services | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| routers | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |

Answering the ADR's required questions explicitly:

- **Who may depend on Domain?** Everyone. Domain is the one layer any other layer may import without violating direction.
- **May Infrastructure (`integrations/`, `dao/`) depend on Domain?** **Yes** — and this is deliberate. It is what lets the Slack adapter receive a `SeverityBreakdown` instead of regex-parsing rendered text (fourth-pass CRITICAL-2).
- **May Domain depend on Services?** **No. Never.** This inverts the layering and is the single most likely violation; it is the first thing a reviewer should check.
- **May Domain depend on FastAPI?** **No.** No `HTTPException`, no `APIRouter`, no request/response models.
- **May Domain depend on Slack (or any transport)?** **No.** No SDK, no Block Kit, no emoji, no channel identifiers.
- **May Domain depend on Pydantic?** **No** (stdlib `enum`/`dataclass` only). Rationale: Pydantic is a validation framework serving the HTTP boundary; coupling domain to it re-creates the "`OperationStatus` lives in a tool schema" mistake in a new form. `schemas/` may freely *reference* domain types.
- **May Domain depend on `core/`?** **No** — not even the logger. Domain does not log; callers do.

---

## 6. Migration Strategy (planning only — no files move under this ADR)

### 6.1 Candidates to move

| File / symbol | Destination | Notes |
|---|---|---|
| `ScanFindings` (`notification/models/operation_progress.py`) | `domain/findings/` as `SeverityBreakdown` | Resolve `total` semantics first (§2.1 Conflict A) — this is a **behavior decision**, not a move |
| `suite/findings.py` (`RISK_ORDER`, `_RISK_RANK`, `risk_rank`, `overall_risk`, `collect_findings`, `derive_recommendations`, `executive_summary`) | `domain/findings/` | Pure rules; the largest genuine domain asset in the repo |
| `_SEVERITIES` (`suite/aggregator.py`) | deleted → domain `Severity` | Fixes the missing-`critical` defect |
| `LifecyclePhase` (`notification/models/operation_progress.py`) | `domain/lifecycle/` as `OperationPhase` | Deduplicates with `OperationStatus` |
| `OperationStatus` (`schemas/tools/owasp_zap/common.py`) | `domain/lifecycle/` | **Highest-churn item** — imported by DAO, schemas, services, tests |

### 6.2 Files that explicitly stay

`scenario/context.py` (§3.3) · `suite/reporter.py` incl. `_SARIF_LEVEL` (format, not domain) · `suite/orchestrator.py`, `aggregator.py` structure (application coordination) · `renderer.py`, `throttle.py`, `operation_notifier.py` (application/presentation) · `EVENT_OPERATION_*` (→ `core/`, §3.4) · all Pydantic request/response schemas · `ZapOperationType`, `ExecutionStrategy` (tool execution contracts, not domain) · `BatchType`.

### 6.3 Requires further review before moving

- **`OperationProgress`** — must be split (domain snapshot vs. view model) before any part moves. Do not relocate wholesale.
- **`ZapScanSummary`** — decide whether it becomes a thin DTO over `SeverityBreakdown` or is deleted; it is persisted, so **stored-result compatibility must be checked**.
- **`BatchType` vs `ZapOperationType`** — overlapping taxonomies (fourth-pass HIGH-2); reconcile *before* touching lifecycle, or the churn compounds.
- **`findings_from_summary`** (helpers) — likely deleted once domain owns the mapping; confirm no other caller.
- **`NotificationChannel.send(message: str)`** — CRITICAL-2's fix (pass the model, not text) depends on `domain/findings/` existing. Sequence after, not during.

### 6.4 Suggested sequencing

1. Ratify this ADR; amend `backend-layering` Exceptions; add the governance rules in §7.
2. `domain/findings/` — define `Severity` + `SeverityBreakdown`, **settle the `total` rule**, add tests asserting the two former definitions now agree.
3. Repoint the six severity sites one at a time; delete duplicates last.
4. `domain/lifecycle/` — introduce `OperationPhase`; migrate `OperationStatus` (largest blast radius; own change).
5. Only then revisit CRITICAL-2 and the `OperationProgress` split.

Each step keeps the suite green; no step combines a move with a behavior change except step 2, which is *explicitly* a behavior fix and must be reviewed as one.

---

## 7. AIOS Governance Changes (if ratified)

**Amend** `standards/architecture/backend-layering` → **1.1.0** (Minor; the Exceptions clause reserves new roles for a Decision — this ADR is that Decision): add `domain/` to R1's role list, extend R4's dependency direction to `routers → services → integrations|dao → domain`, and record that `domain/` is innermost.

**New standard** `standards/architecture/domain-layer@1.0.0` (Active, backend-owner, `applies_to: mcp-server/app/**`) carrying four enforceable rules:

- **D1 — Domain Qualification Rule.** A concept enters `domain/` only by passing the nine-criterion test in §3, evidenced in the PR. Purity alone never qualifies a concept (the §3.3 precedent).
- **D2 — Canonical Ownership Rule.** Every business concept has exactly one definition. A second definition of an existing domain concept is a blocking violation — *including* a "temporary" copy made to avoid an import (the §2.2 anti-pattern, verbatim).
- **D3 — Shared Business Concept Rule.** A concept used by two or more contexts and carrying business meaning is promoted to `domain/`, never duplicated and never left owned by whichever context consumed it first ("first consumer wins" is named as the anti-pattern).
- **D4 — Domain Dependency Rule.** `domain/` imports nothing from `app/` outside itself — no `services/`, `core/`, `schemas/`, `dao/`, `integrations/`, no FastAPI, no Pydantic, no transport SDK. Mechanically checkable by import scan; recommend wiring into `aios lint`.

**Anti-patterns** the new standard must name (per the Standard contract's A1 rule): the six severity definitions; the `total`-means-two-things conflict; `OperationStatus` living in a tool schema; `domain/models/`-style construct naming.

**Also update:** Backend Agent `standards_enforced` (1.1.0 → 1.2.0), Backend ROUTER task table (a "shared business concept" subtype row), `intelligence/module-map.md`, and re-pin `evaluation/benchmarks/fix-bug` if the agent version moves.

---

## 8. Risks if REJECTED

- **Critical — incorrect security reporting persists.** §2.1 Conflict A is live: informational-only scans report `total = 5` in one surface and `0` in another. A user reasonably concludes the two disagree about whether their API is safe. Nearest Guardrail: **G3**.
- **Critical — critical findings are undroppable-by-design in suite reports.** Any future scanner reporting `critical` loses those findings in aggregation (4-bucket aggregator).
- **High — duplication compounds per tool.** Each new scanner adds severity-mapping code in ~4 places. The 6→7→8 definition count grows monotonically; the cost of consolidation grows with it.
- **High — drift becomes convention.** With no domain home, "put it where the first consumer is" is the de-facto rule; Decision 0006's Standard prevents *package* decay but is silent on *concept* ownership.
- **Medium — CRITICAL-2 stays unfixable.** Passing a model instead of rendered text requires a shared model to pass.
- **Medium — the `OperationStatus`-in-a-tool-schema misplacement becomes load-bearing** as more code imports it from there.

## 9. Risks if ACCEPTED

- **High — domain becomes the new dumping ground.** The exact failure Decision 0006 addressed for services, re-created one layer down. *Mitigation:* D1 qualification test with PR-visible evidence; this ADR's own 2-of-5 rejection rate is the precedent.
- **High — `OperationStatus` migration has wide blast radius** (DAO, schemas, services, tests, persisted values). *Mitigation:* its own migration step; string values unchanged so stored data is unaffected.
- **Medium — anemic domain.** Two packages holding an enum and a value object would be an over-engineered `constants/`. *Mitigation:* `findings/` must absorb the real rules from `suite/findings.py`, not just the enum. If in implementation it turns out that only enums move, **that is a signal to stop and re-reject** — recorded here as an explicit abort condition.
- **Medium — governance load.** A fifth role, a new Standard, an amended Standard, agent/router/benchmark churn.
- **Low — the `total` fix is a behavior change.** Some surface's number will change. *Mitigation:* deliberate, tested, changelogged — a report that changes because it was wrong is a fix, not a regression.
- **Low — premature-abstraction criticism.** Fair against the multi-tool argument, which §2.4 rejects; not fair against six existing definitions.

---

## 10. Decision Record

**Recommend: APPROVE, narrowly** — `domain/findings/` and `domain/lifecycle/` only. Scenario state, event payloads, and notification presentation are **rejected**, with event payloads redirected to `core/` as a Contracts fix.

The layer earns its existence on **present, verified duplication with a demonstrable correctness conflict** — not on a multi-tool roadmap that has zero implementation. If the owner finds §3.2's cheaper alternative (lifecycle → `core/`, no new layer) sufficient for that concept, this ADR is partially ratifiable: `domain/findings/` alone still clears the bar on its own evidence.

**Abort condition:** if, at implementation, `domain/findings/` attracts only enums and no rules, the layer has not earned itself — stop and revert to a `constants/` fix.
