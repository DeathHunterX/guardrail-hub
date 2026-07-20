# Growth Stress-Test of the Proposed Domain Layer

**Date:** 2026-07-20
**Subject:** [ADR-0007](../../decisions/0007-domain-layer-justification.md) (Proposed) re-evaluated against a five-year, nine-tool scenario: OWASP ZAP, JMeter, Semgrep, Trivy, Checkov, MobSF, Nuclei, Burp Suite, + future scanners.
**Status:** Analysis. No code, no ADR ratification, no directories created.

---

## 1. Verdict

| Proposed capability | Under 1 tool (ADR-0007) | Under 9 tools | Change |
|---|---|---|---|
| `domain/lifecycle/` | Approve | **Approve — strengthened** | Additive pressure only |
| `domain/findings/` | Approve | **Approve the concept, reject the proposed shape** | Structural redesign required |

**The domain layer survives the stress test. The ADR's *design* of `findings/` does not.**

Three defects would surface, in rough order of severity: (1) the tool list is not one family — JMeter is not a security scanner and breaks the findings abstraction outright; (2) `SeverityBreakdown` as five fixed integer fields is a breaking-change generator; (3) the aggregation rules the ADR proposes to promote are DAST-shaped and would freeze web-scanner assumptions into a universal layer.

Critically, **all three are cheaper to fix now, on paper, than after `domain/findings/` exists and nine tools import it.** That is the value of running this test before ratification.

---

## 2. The load-bearing discovery: these nine tools are not one family

ADR-0007 implicitly assumed "more scanners, same shape." The user's own list disproves it. Grouping by *result shape* rather than by vendor:

| Family | Tools | Finding identity | Severity native scale | Notes |
|---|---|---|---|---|
| **DAST** (web, runtime) | ZAP, Burp, Nuclei | URL + param + rule | High/Med/Low/Info (+ **confidence**) | The only family today's code models |
| **SAST** (code) | Semgrep | file + line + rule | ERROR/WARNING/INFO (3) | No URL exists |
| **SCA / vulnerability** | Trivy | package@version + CVE | CRITICAL…LOW + **UNKNOWN**, CVSS score | Has *fix version* — remediation is data, not prose |
| **IaC / config** | Checkov | resource id + file + check | varies | Emits **passed** checks — compliance needs pass/fail ratios |
| **Mobile** | MobSF | app component + rule | CVSS-derived | Hybrid static/dynamic |
| **Performance** | **JMeter** | ⚠️ **none — no findings at all** | ⚠️ **none** | p95 latency, throughput, error rate, SLA verdict |

Two structural consequences:

**2.1 JMeter has no findings.** A load test produces `p95 = 812ms, throughput = 240 rps, errors = 0.3%, SLA = FAIL`. There is no severity, no rule id, no vulnerability. Under ADR-0007 as written, JMeter results must either be force-fitted into `SeverityBreakdown` with fabricated severities — which corrupts the domain model *and* edges toward Guardrail G3 (a fabricated security-posture signal) — or bypass the domain layer entirely, at which point `domain/findings/` is not the universal result abstraction the ADR claims.

The correct resolution is a level of indirection the ADR does not have: **an operation produces a `Result`, of which `Findings` is one kind and `Metrics` is another.** That is a genuine domain distinction (security posture vs. performance characteristics), not a folder split.

**2.2 Finding *identity* is family-specific.** Verified in the current code: `collect_findings` deduplicates on `(rule_id, name, risk)` and records `example_url`. That key is DAST-shaped. Semgrep's identity is `(rule_id, file, line)`; Trivy's is `(cve, package, version)`; Checkov's is `(check_id, resource)`. Promoting `suite/findings.py` verbatim into `domain/findings/`, as ADR-0007 §6.1 proposes, would install web-scanner deduplication as the universal rule — the exact "first consumer wins" failure the ADR was written to end, re-committed one layer down.

The fix is a `Location` value object (URL | file+line | package@version | resource) with identity derived from it, so dedup becomes polymorphic over location kind rather than hardcoded to URLs.

---

## 3. `domain/findings/` — what specifically becomes unstable

### 3.1 `SeverityBreakdown` as five fixed fields → **structurally unstable (High)**

ADR-0007 §4.1 specifies five integer fields (critical/high/medium/low/informational). Under growth:

- **Trivy and Nuclei emit `UNKNOWN`** for CVEs lacking a CVSS score. Adding an `unknown` field later is a breaking change to every consumer, every persisted record, and the Slack adapter.
- **Checkov emits passed checks.** Compliance reporting needs `passed/failed`, which a severity-only breakdown cannot express.
- **Semgrep has three levels**, requiring a mapping decision (`WARNING` → medium or low?) that has real consequences — it determines whether a build fails.

**Recommendation:** model the breakdown as a *mapping keyed by `Severity`* (with a total rule), not as fixed fields. Adding a severity member then becomes additive rather than breaking. This is a small change on paper and an expensive one after nine integrations exist.

### 3.2 Severity loses information → **misplaced abstraction (High)**

Two dimensions are discarded by the proposed model:

- **Confidence.** Verified: `ZapAlert.confidence` already exists in this codebase (`Low/Medium/High/Confirmed`) and is dropped before reaching `ScanFindings`. Burp has the same concept (Certain/Firm/Tentative). Confidence is orthogonal to severity and is a primary triage filter — "high severity, tentative confidence" is a different action than "high severity, certain."
- **CVSS score.** Trivy and MobSF carry numeric scores. Bucketing 9.8 and 7.1 both into `HIGH` destroys ordering that users will demand for prioritization.

Under nine tools, `Severity` as a bare bucket is not wrong but is **insufficient**: it should be one attribute of a `Finding`, alongside optional `confidence` and `score`, rather than the only expressed dimension.

### 3.3 Severity normalization becomes a first-class domain rule → **strengthens the ADR (new capability)**

Nine tools means nine native scales mapping into one. That mapping is not plumbing — it decides whether a release is blocked. It is business knowledge with exactly the properties ADR-0007's qualification test demands: shared, stable, rule-bearing, transport-free, and *currently duplicated* (the `findings_from_summary` helper is a hand-rolled instance of it today).

This is the single strongest new argument **for** the domain layer under growth — and it must be explicit in the design: **native severity ≠ domain severity**, with normalization owned by domain and applied at each tool's boundary.

### 3.4 `_SEVERITY_ADVICE` → **misplaced under growth (Medium)**

Current text: *"Address High-risk findings before release — these are exploitable vulnerabilities (e.g. injection, broken auth)."* That is AppSec/DAST prose. Trivy's real advice is "upgrade `openssl` to 3.0.7"; Checkov's is "set `encryption = true`". Remediation guidance is **tool- and finding-specific**, and Trivy/Checkov supply it as *data*, not prose.

Promoting this constant into `domain/findings/` — as ADR-0007 §6.1 implies by moving `findings.py` wholesale — would freeze web-app language across nine unrelated tools. **Recommendation:** `Finding.remediation` becomes an optional data field populated per tool; generic severity prose stays out of domain, or moves to presentation.

### 3.5 Capabilities that would accrete onto `findings/` → **needs a boundary now (Medium)**

Under nine tools, four capabilities predictably arrive, all with genuine domain character:

| Emerging capability | Why it is domain | Risk if unplanned |
|---|---|---|
| **Suppression / baseline** (accepted risks, false positives, expiry) | Business policy about what counts | Accretes into `findings/` as ad-hoc filters |
| **Policy gating** ("fail build if critical > 0") | *The* DevSecOps product value | Ends up in routers or CI glue |
| **Cross-tool correlation** (ZAP and Burp find the same XSS) | Deduplication across families | Impossible without a `Location` abstraction (§2.2) |
| **Compliance mapping** (CWE, OWASP Top 10, PCI) | Regulatory vocabulary — note `ZapAlert.cwe_id`/`wasc_id` already exist | Duplicated per tool |

`domain/findings/` would become a dumping ground holding all four — precisely ADR-0007 §9's stated High risk. They should be *named now as future siblings* (`domain/policy/`, `domain/compliance/`) with `findings/` scoped to the finding model, its identity, and aggregation only. Naming them costs nothing today and prevents accretion later.

---

## 4. `domain/lifecycle/` — holds up, with one additive pressure

Lifecycle is the capability that **improves** under growth. It is genuinely tool-agnostic: queued → running → completed/failed/cancelled describes a Semgrep run as accurately as a ZAP scan, and none of the nine tools introduce a new *shape* of lifecycle. The ADR's §2.2 duplication evidence gets stronger as more contexts need the vocabulary.

Two pressures, both manageable:

- **Partial success becomes real.** Trivy scanning 10 images where 8 succeed; a suite where 3 of 40 endpoints fail. The suite already models this informally (`completed`/`failed` counts). A `PARTIAL` phase is likely — an *additive* enum change, but it complicates `is_terminal` and any "did it succeed?" logic. Worth designing the terminal-state predicate to tolerate it from day one.
- **Execution duration spread widens enormously**: Semgrep ~30s, ZAP full scan ~hours, JMeter soak tests ~days. This does not change lifecycle *states*, but it does stress the notification throttle and the elapsed-refresh ticker — an application concern, not a domain one.

**Verdict: approve as specified.** No restructuring required.

---

## 5. Collateral finding — the pressure lands hardest *outside* the domain layer

The stress test surfaced a larger issue than either domain capability, worth recording because it will dominate the five-year effort:

**The execution layer's worker-pool model is ZAP-specific and does not generalize.** ZAP and Burp are long-lived daemons requiring a registered worker pool with heartbeats — the architecture that exists. Semgrep, Trivy, Checkov, and Nuclei are **ephemeral CLI processes**: no pool, no heartbeat, no registration; you exec them in a container and collect output. JMeter is different again (long-running, resource-heavy, its own distributed model).

`ExecutionStrategy` currently expresses `requires_worker` as its only routing dimension. Under nine tools the real dimensions become *execution substrate* (daemon pool / ephemeral process / distributed) × *orchestration shape* (single / fan-out). Additionally `ZapOperationHandler` imports `ZapWorkerInfo` — a ZAP schema — into what is meant to be the generic contract.

ADR-0007 correctly ruled execution out of scope, and this analysis does **not** reopen it. But the third-pass decision to defer promoting `execution/` to a generic layer "until a second tool arrives" should be understood as: **that trigger fires with the first non-ZAP tool, and the redesign is larger than a package move.** It deserves its own ADR before tool #2 lands, not after.

---

## 6. Recommended amendments to ADR-0007

The recommendation (Approve, narrowly) stands. Five design amendments, all pre-ratification and all cheap now:

1. **Introduce `Result` above `Findings`.** `domain/findings/` must not be the universal result abstraction — JMeter proves it isn't. Either scope `findings/` to security findings and add `domain/metrics/` when JMeter lands, or introduce a `Result` concept now. **Recommend the former** (scope honestly, defer the second capability), per the ADR's own anti-speculation stance.
2. **`SeverityBreakdown` becomes a severity-keyed mapping**, not five fixed fields (§3.1).
3. **Add `Location`, `confidence`, and optional `score` to the `Finding` model**; make deduplication identity polymorphic over `Location` rather than URL-shaped (§2.2, §3.2).
4. **Do not promote `_SEVERITY_ADVICE`**; remediation becomes per-finding data (§3.4).
5. **Name `domain/policy/` and `domain/compliance/` as anticipated siblings** — explicitly *not created now* — so `findings/` has a defensible boundary against accretion (§3.5).

Amendment 2 in particular converts a future breaking change into a future additive one, for roughly zero cost today.

**Unchanged:** the rejections. Scenario state (single consumer, HTTP-shaped), event payloads (a `core/` Contracts fix), and notification presentation remain out of domain under the growth scenario. Nine tools do not make any of them more shared or more business-meaningful. The abort condition in ADR-0007 §9 also stands — if `findings/` attracts only enums and no rules, stop.

---

## 7. Honest counter-argument

Everything above §4 is reasoning about tools that have **zero lines of code in this repository** — `schemas/tools/jmeter/` is an empty directory, and `intelligence/system-overview.md` records zero implementation for all nine. ADR-0007 explicitly rejected roadmap-based justification, and this analysis must not smuggle it back in.

The distinction I am drawing: the growth scenario is not being used to *justify* the domain layer — that rests on six verified present-day definitions and a live `total` conflict. It is being used to **shape** a layer already justified on current evidence. Designing a mapping instead of five fixed fields is not speculative generality; it is declining to hardcode an assumption we can already see is false.

Where this analysis *would* be over-building: creating `domain/metrics/`, `domain/policy/`, or `domain/compliance/` now. It recommends naming them and building none of them.

---

## 8. Summary answer

**Would become unstable:** `SeverityBreakdown`'s fixed five-field shape (breaking change on the first `UNKNOWN` severity); `is_terminal` if `PARTIAL` arrives unplanned.

**Would become misplaced:** DAST-shaped deduplication identity promoted as universal; `_SEVERITY_ADVICE` freezing AppSec prose across nine tools; severity-as-only-dimension discarding confidence and CVSS.

**Would require restructuring:** the findings abstraction itself, once JMeter (a non-security tool) enters — findings cannot be the universal result type; and, outside domain, the ZAP-specific worker-pool execution model, which does not generalize to ephemeral-process scanners and warrants its own ADR before tool #2.

**Would hold:** `domain/lifecycle/` entirely, and the core justification for a domain layer — which the growth scenario strengthens rather than weakens, chiefly because severity *normalization* across nine native scales is exactly the kind of shared business rule that needs one canonical owner.
