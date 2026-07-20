# 0008 — The Canonical Domain Language of Guardrail Hub

Status: **Accepted** — ratified and implemented 2026-07-20; the vocabulary is now enforced by [domain-layer@1.0.0](../standards/architecture/domain-layer.md) D4 (canonical vocabulary) and D5 (boundary translation). Pairs with [ADR-0007](0007-domain-layer-justification.md) (Accepted): 0007 argues a Domain layer is justified; **0008 defines what the Domain actually is**. 0008 was ratified first, as intended — implementing 0007 without settled vocabulary would have encoded the prior ambiguity into the new layer.
Owner: Loi Phan
Date: 2026-07-20
Informed by: [services-responsibility-review.md](../architecture/evidence/services-responsibility-review.md), [domain-layer-growth-stress-test.md](../architecture/evidence/domain-layer-growth-stress-test.md)
Defines vocabulary. **Does not define implementation.** No code, directories, or file moves follow from this ADR.

---

## 1. Recommendation

**Ratify a deliberately small canonical vocabulary: four fundamental concepts, six derived, everything else named as implementation detail or future concept.**

The vocabulary is definable today — so this ADR does *not* recommend delaying. But four of the terms proposed in the brief are **rejected**, and the rejections carry more architectural weight than the acceptances:

| Proposed term | Verdict |
|---|---|
| Operation *(existing)* | ✅ **Fundamental** — the root |
| Finding | ✅ **Fundamental** |
| Severity | ✅ **Fundamental** |
| OperationPhase *(Lifecycle)* | ✅ **Fundamental** |
| **Assessment / AssessmentResult** | ❌ **Rejected** — the codebase already says *Operation* |
| **NormalizedSeverity** | ❌ **Rejected** — creates the ambiguity it claims to fix |
| **Execution** | ❌ **Rejected from Domain** — mechanics, not business meaning |
| **Policy, Compliance, Metrics, Result** | ⏸️ **Future** — named, not defined, not built |
| FindingIdentity, Confidence, Location, Score | ➖ **Derived** — attributes of Finding, not roots |

---

## 2. The four rejections (stated first, because they shape everything else)

### 2.1 ❌ "Assessment" — rejected outright

Ubiquitous language means *the language the team, the code, and the users already speak* — not a vocabulary invented at design time because it sounds more domain-driven.

Verified evidence:
- **`operation_id` appears in 34 source files.**
- The persistence table is literally `operations` (`0001_create_operations_table.sql`).
- It is the **user-facing contract**: the MCP tool returns `{operation_id, status, message}` and the documented workflow is *"Check status at api/history/get-result with param operation_id."*
- **"Assessment" appears exactly once in the entire application** — in a marketing sentence in `main.py` ("perform interactive browser-based security assessments"). It is not a term of art here.

Introducing `Assessment` would create a synonym for a concept that already has a name, guaranteeing the "which one do I use?" confusion this ADR exists to eliminate — and it would require a breaking change to a published API for zero business gain.

**Decision: the root concept is `Operation`.** `Assessment` is not part of the language.

### 2.2 ❌ "NormalizedSeverity" — rejected as a concept

Having both `Severity` and `NormalizedSeverity` in the language implies two kinds of severity are both domain concepts, which reintroduces exactly the ambiguity that six competing definitions created.

**There is one `Severity`, and it is canonical by definition.** A tool's native scale (Semgrep's `ERROR`, Trivy's `UNKNOWN`, ZAP's `High`) is not a domain concept at all — it is a **wire format**, living in that tool's adapter. Normalization is therefore a *boundary responsibility* (a rule applied when translating a tool's output into a `Finding`), not a type.

This is a stronger position than the growth stress-test reached, and it resolves that document's §3.3 concern more cleanly: the domain does not need to know that Semgrep says `ERROR`; the Semgrep adapter needs to know that `ERROR` means `Severity.HIGH`.

### 2.3 ❌ "Execution" — rejected from the Domain

`ExecutionStrategy`, `ZapOperationType`, worker pools, dispatch, fan-out/fan-in: these describe *how work is scheduled and run*. They carry no business meaning — a user does not care whether their scan ran `SEQUENTIAL` or `FAN_OUT`, and changing the execution model changes no business truth. Execution is application/tool mechanics and stays where it is.

**Test applied:** if the concept's definition changes when we swap infrastructure, it is not domain. Execution fails this test; Severity passes it.

### 2.4 ⏸️ "Result" / "AssessmentResult" — deferred, not rejected

The stress test showed JMeter (performance) cannot produce `Finding`s, implying a broader `Result` root with `Findings` and `Metrics` as kinds. That reasoning is sound **for the day JMeter exists**. Today there is exactly one kind of result, so a `Result` abstraction would have exactly one implementation — an abstraction justified by elegance, not evidence, which this ADR's own rules forbid.

**Decision: `Finding` is a root today.** §6 records `Result` as a future root with an explicit trigger. Note honestly: promoting `Finding` under a `Result` root later is a *refactor*, and this ADR accepts that cost in exchange for not building a speculative hierarchy now.

---

## 3. Fundamental Concepts

Four. Each is a root: it has identity or intrinsic meaning, and is not defined in terms of another concept.

### 3.1 `Operation` — **the root aggregate**

- **Definition:** one requested unit of security work, from submission to terminal outcome. The thing a user starts, tracks, and retrieves results for.
- **Owner:** Operations capability (`domain/lifecycle/` per ADR-0007, or a capability named `operation`).
- **Responsibility:** identity of the work, and the phase it is in.
- **Invariants:** (I1) has a stable, unique `operation_id` for its whole life; (I2) is in exactly one `OperationPhase` at a time; (I3) once in a terminal phase, never leaves it (terminal states are absorbing); (I4) identity never changes.
- **Lifecycle:** `QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED`.
- **Dependencies:** none. In particular **`Operation` does not depend on `Finding`** — an operation is meaningful before any finding exists, and for tools that produce none.
- **Existing realizations (implementation, not domain):** `OperationRecord` (persistence), `operation_id` (API contract), the `operations` table.

### 3.2 `OperationPhase` — the lifecycle vocabulary

- **Definition:** the stage of an `Operation`'s life. Replaces today's duplicated pair `OperationStatus` + `LifecyclePhase`.
- **Owner:** Operations capability.
- **Responsibility:** the single canonical set of phases and the rule for which are terminal.
- **Invariants:** (I5) the member set is closed and changes only additively; (I6) `is_terminal` is total — every phase answers it; (I7) string values remain stable, because they are persisted.
- **Members:** `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.
- **Dependencies:** none.
- **Known future pressure:** `PARTIAL` (some children succeeded) — see §6.

### 3.3 `Finding` — a single detected issue

- **Definition:** one issue a tool detected, in one place, attributable to one rule. Tool-neutral.
- **Owner:** Findings capability.
- **Responsibility:** what was found, how bad it is, how sure we are, and where it is.
- **Invariants:** (I8) has exactly one `Severity`; (I9) has an identity (§4.1) that is stable across repeated runs of the same tool against the same target — this is what makes deduplication meaningful rather than arbitrary; (I10) a `Finding` is immutable once produced (re-scanning creates new findings; it does not mutate old ones).
- **Lifecycle:** created at detection, never mutated. (Suppression/acceptance is a *future* separate concept — §6 — deliberately not an attribute of `Finding`, so its immutability holds.)
- **Dependencies:** `Severity`, and its derived attributes (§4). **Does not depend on `Operation`** — deliberately. A finding must remain reasonable about independently for future cross-operation correlation; the finding↔operation association is an application/persistence concern.
- **Existing realization:** `ZapAlert` is ZAP's wire format, *not* the domain `Finding`. It maps into one.

### 3.4 `Severity` — how serious a finding is

- **Definition:** the canonical, tool-independent seriousness of a `Finding`. Canonical by definition (§2.2).
- **Owner:** Findings capability.
- **Responsibility:** the closed severity set and its total ordering.
- **Invariants:** (I11) **totally ordered** — any two severities compare; (I12) the set is closed and extended only additively; (I13) `INFORMATIONAL` is *not* a vulnerability (see §4.2 — this is the rule that resolves a live production conflict); (I14) every `Finding` maps to exactly one member.
- **Members (current):** `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFORMATIONAL`. `UNKNOWN` is anticipated (§6) — the reason the derived breakdown must be a mapping, not fixed fields.
- **Dependencies:** none. This is the most fundamental concept in the product.
- **Evidence of need:** six competing definitions today (ADR-0007 §2.1).

---

## 4. Derived Concepts

Defined *in terms of* the fundamentals. Real vocabulary, but not roots — none of them stands alone.

### 4.1 `FindingIdentity`
- **Derived from:** `Finding` attributes — the rule that produced it plus the `Location` it occurred at.
- **Responsibility:** answering "are these two findings the same issue?" — the basis of deduplication and counting.
- **Invariant:** (I15) two findings with equal identity are the same issue and may be collapsed into one with an instance count.
- **Note:** today's implementation deduplicates on `(rule_id, name, risk)` with a URL — a DAST-shaped key. The *concept* is family-neutral; the *current key* is not. Named here so the distinction is explicit before code moves.

### 4.2 `FindingSummary` — the count of findings by severity
- **Derived from:** a collection of `Finding` + `Severity`.
- **Replaces:** `ScanFindings`, `ZapScanSummary`, and the four ad-hoc severity tuples.
- **Shape:** a **mapping keyed by `Severity`**, never fixed fields (per the growth stress-test — makes a new severity member additive rather than breaking).
- **⚠️ This ADR settles the live `total` conflict.** Two different meanings of "total" exist in production today: `ZapScanSummary.total = len(alerts)` (includes informational) vs. `ScanFindings.total` (excludes it). The defect was **two concepts sharing one name**. The language therefore defines two distinct terms, and retires the ambiguous word "total":
  - **`finding_count`** — every finding, informational included.
  - **`vulnerability_count`** — findings whose severity is a vulnerability, i.e. **excluding `INFORMATIONAL`** (invariant I13).
  
  No domain term named `total` may exist. Any future use of the bare word in a domain signature is a violation.
- **Invariant:** (I16) `finding_count` ≥ `vulnerability_count`, always.

### 4.3 `OverallRisk`
- **Derived from:** `FindingSummary` — the highest severity present, or "none".
- **Responsibility:** the one-line posture answer.
- **Invariant:** (I17) equals the maximum severity with a non-zero count, considering vulnerabilities only (I13); "none" when `vulnerability_count == 0`.

### 4.4 `Confidence`
- **Derived status:** an **attribute of `Finding`**, not a root.
- **Definition:** how certain the tool is that the finding is real. Orthogonal to `Severity`.
- **Evidence it is real today:** `ZapAlert.confidence` already exists (`Low/Medium/High/Confirmed`) and is currently **discarded** before reaching any summary. Burp has the same notion.
- **Invariant:** (I18) confidence never modifies severity — a tentative critical is still critical. They are independent axes.

### 4.5 `Location`
- **Derived status:** an **attribute of `Finding`**.
- **Definition:** where the finding is. Today, always a URL (the only tool is DAST).
- **Why named now despite one realization:** naming it keeps `url` out of the domain's vocabulary and signatures. The *language* admits that location varies; the *implementation* stays a URL until a second shape exists. Naming is free; a premature polymorphic hierarchy is not — and this ADR does not authorize one.

### 4.6 `Score`
- **Derived status:** an **optional attribute of `Finding`** (e.g. CVSS).
- **Current evidence:** **none** — ZAP emits no numeric score.
- **Status: named, not defined.** Recorded so that when Trivy/MobSF arrive, `Score` is not reinvented as a tool-local field. No properties are specified today.

---

## 5. Implementation Details — explicitly *not* domain concepts

Naming these prevents them being mistaken for vocabulary in future reviews.

| Type | What it actually is |
|---|---|
| `ZapAlert`, `ZapScanSummary`, `ZapScanResult` | ZAP **wire formats**; map into `Finding`/`FindingSummary` at the adapter |
| `OperationRecord` | **Persistence** model of `Operation` |
| `ScanFindings`, `LifecyclePhase` | Current **implementations** of `FindingSummary` / `OperationPhase` — to be replaced, not promoted |
| `OperationProgress` | **Application/presentation** view model |
| `Notification`, `ChannelCapabilities` | **Transport contracts** |
| `ExecutionStrategy`, `ZapOperationType`, `ZapOperation`, worker pool | **Execution mechanics** (§2.3) |
| `BatchType` | **Legacy taxonomy**; overlaps `ZapOperationType` (responsibility review HIGH-2) — reconcile as mechanics, not vocabulary |
| `DomainEvent`, `EVENT_OPERATION_*` | **Integration contracts** — note the name `DomainEvent` is a misnomer; it is a *transport envelope*. Belongs in `core/` (ADR-0007 §3.4) |
| `_SEVERITY_ADVICE` | **Presentation copy** — DAST-flavoured prose, not domain knowledge |

---

## 6. Future Concepts — named, deliberately undefined

Recorded so they are not reinvented ad hoc, and so `Findings` has a defensible boundary against accretion. **None may be built without its trigger firing and its own ADR.**

| Future concept | Trigger | Why not now |
|---|---|---|
| `Result` (root; `Findings` \| `Metrics` as kinds) | First non-security tool (**JMeter**) | Would have exactly one implementation today |
| `Metrics` (latency, throughput, SLA verdict) | JMeter | No performance tool exists |
| `Severity.UNKNOWN` | First tool emitting unscored findings (**Trivy**, **Nuclei**) | ZAP always assigns a risk. *(Additive by I12 — this is why I16's breakdown is a mapping)* |
| `Policy` (gating: "fail if critical > 0") | First gating requirement | No gating exists; likely the highest-value future capability |
| `Compliance` (CWE / OWASP Top 10 / PCI mapping) | First compliance report | Hooks exist (`ZapAlert.cwe_id`, `wasc_id`) but nothing consumes them |
| `Suppression` / `Baseline` (accepted risk, expiry) | First false-positive workflow | Kept out of `Finding` to preserve immutability (I10) |
| `Correlation` (same issue found by ZAP *and* Burp) | Second overlapping tool | Requires `Location` polymorphism first |
| `OperationPhase.PARTIAL` | Formal partial-success semantics | Suite models it informally today; additive when needed (I5) |

---

## 7. Ownership Matrix

The canonical reference for future architecture reviews.

| Concept | Kind | Owner (capability) | Layer | Public API | Future evolution |
|---|---|---|---|---|---|
| `Operation` | Fundamental (root) | Operations | Domain | identity + phase | Stable. May gain `parent` if nesting is formalized |
| `OperationPhase` | Fundamental | Operations | Domain | members, `is_terminal` | Additive only; `PARTIAL` anticipated |
| `Finding` | Fundamental (root) | Findings | Domain | severity, confidence, location, rule, identity | May become a kind of `Result` |
| `Severity` | Fundamental | Findings | Domain | ordered members, comparison | Additive only; `UNKNOWN` anticipated |
| `FindingIdentity` | Derived | Findings | Domain | equality/grouping key | Generalizes with `Location` |
| `FindingSummary` | Derived | Findings | Domain | severity-keyed counts, `finding_count`, `vulnerability_count` | Mapping shape absorbs new severities |
| `OverallRisk` | Derived | Findings | Domain | single risk answer | May become policy-driven |
| `Confidence` | Derived (attribute) | Findings | Domain | value only | Stable |
| `Location` | Derived (attribute) | Findings | Domain | opaque value | Polymorphic when tool #2 lands |
| `Score` | Derived (named only) | Findings | Domain | — undefined — | Defined when a scoring tool lands |
| Execution mechanics | Not domain | ZAP tool package | Application | tool-internal | Generalizes per its own ADR |
| Wire formats (`ZapAlert`, …) | Not domain | Each tool adapter | Schemas/Infrastructure | tool-specific | One per tool; never shared |
| Event envelope | Not domain | Ports | Contracts (`core/`) | `publish` | Typed payloads per ADR-0007 §3.4 |

---

## 8. Dependency Rules

Explicit answers to the questions posed:

| Question | Answer | Reasoning |
|---|---|---|
| **Can Findings depend on Lifecycle?** | **No** | A finding's severity and identity are true regardless of the operation's phase. |
| **Can Lifecycle depend on Findings?** | **No** | Phase transitions are valid for tools producing zero findings. Where `complete(findings=…)` passes both, the **application service composes them** — that is not a domain dependency. |
| **Findings ↔ Lifecycle** | **Mutually independent siblings** | This is the load-bearing result: two capabilities with *no* edge between them. It independently validates ADR-0007's two-package split — if either depended on the other, one package would be correct. |
| **Can Domain depend on Services?** | **No, never** | Inverts layering. The first thing a reviewer should check. |
| **Can Services depend on Domain?** | **Yes** | The intended direction. |
| **Can Infrastructure depend on Domain?** | **Yes** | Deliberate — it lets the Slack adapter receive a `FindingSummary` instead of regex-parsing rendered text (responsibility review CRITICAL-2). |
| **Can Infrastructure *own* Domain concepts?** | **No** | Sharp distinction: infrastructure may **depend on** domain concepts, never **define** them. Today's violation is exactly this — the Slack adapter defines its own severity list, and `OperationStatus` is defined inside a *ZAP tool schema*. Both are ownership violations, not merely placement errors. |
| Can Domain depend on frameworks (FastAPI, Pydantic, Slack SDK)? | **No** | Per ADR-0007 §5. |

---

## 9. How future ADRs use this document

1. **Reference, never redefine.** A later ADR needing "severity" cites ADR-0008 §3.4. Redefining a concept is a governance violation.
2. **New concepts extend the language.** Anything not listed here is presumed *not* a domain concept until an ADR adds it, with the qualification evidence ADR-0007 §3 requires.
3. **The future table is a contract.** A concept in §6 may only be built when its stated trigger has actually fired — no anticipatory implementation.
4. **Invariants I1–I18 are checkable.** They are the assertions a domain test suite should encode; I13/I16 in particular pin the bug that motivated this work.

---

## 10. Ratification

**Recommend: ratify.** The brief's fallback — *"if the vocabulary cannot be clearly defined, delay implementation"* — was taken seriously and does **not** apply. The four fundamentals are each backed by present-day evidence (six severity definitions, two lifecycle definitions, 34 files using `operation_id`, a discarded `confidence` field), and the genuinely uncertain concepts have been pushed to §6 rather than guessed at.

Two caveats on the record:

- **`Finding`-as-root is a considered bet.** If JMeter arrives early, `Finding` moves under a `Result` root. This ADR accepts a future refactor over a present speculative abstraction. That trade is explicit, not overlooked.
- **Ratification order matters.** ADR-0008 (language) should be ratified **before** ADR-0007 (layer) is implemented. Building the layer first would encode the current ambiguity — most damagingly the two meanings of `total` — into the very structure meant to eliminate it.

**Not authorized by this ADR:** any code, directory, file move, or AIOS standard change. The governance rules ADR-0007 §7 proposes should be updated to reference this vocabulary once both are ratified.
