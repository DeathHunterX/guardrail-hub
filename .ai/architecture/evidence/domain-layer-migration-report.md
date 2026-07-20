# Domain Layer Migration Report

**Date:** 2026-07-20
**Implements:** [ADR-0007](../../decisions/0007-domain-layer-justification.md) (layer justification) and [ADR-0008](../../decisions/0008-domain-ubiquitous-language.md) (canonical vocabulary).
**Result:** all five phases complete. **194 passing / 2 failing — identical to the pre-migration baseline.** The 2 failures are pre-existing and unrelated (renderer wording assertions in `test_scan_lifecycle_notification_flow`, failing before this work began). `aios check: PASS`.

---

## 1. Files created

| File | Contains |
|---|---|
| `app/domain/__init__.py` | Layer docstring + dependency rule |
| `app/domain/findings/__init__.py` | Capability façade + allowed/not-allowed contract |
| `app/domain/findings/severity.py` | `Severity` (5 members, totally ordered), `SEVERITY_ORDER`, `parse` |
| `app/domain/findings/finding.py` | `Finding`, `Confidence`, `FindingIdentity` |
| `app/domain/findings/summary.py` | `FindingSummary` (severity-keyed mapping), `finding_count`, `vulnerability_count`, `overall_risk` |
| `app/domain/findings/aggregation.py` | `AggregatedFinding`, `deduplicate` |
| `app/domain/lifecycle/__init__.py` | Capability façade |
| `app/domain/lifecycle/phase.py` | `OperationPhase`, `is_terminal` |

## 2. Ownership changes

| Concept | Was (owner) | Now (canonical owner) |
|---|---|---|
| Severity | 6 definitions across notification, suite×2, helpers, Slack, schemas | `domain/findings/severity.py` |
| Operation lifecycle | `schemas/tools/owasp_zap/common.OperationStatus` **and** `notification/…/LifecyclePhase` | `domain/lifecycle/phase.OperationPhase` |
| Severity breakdown | `notification/…/ScanFindings` | `domain/findings/summary.FindingSummary` |
| Finding identity / dedup | `suite/findings.collect_findings` (inline) | `domain/findings/aggregation.deduplicate` |
| Risk ordering | `suite/findings.RISK_ORDER` + `_RISK_RANK` | `Severity.rank` / `SEVERITY_ORDER` |
| Overall risk | `suite/findings.overall_risk` (inline) | `FindingSummary.overall_risk` |

## 3. Duplications removed

1. **`ScanFindings`** (notification) → deleted; consumers use `FindingSummary`.
2. **`LifecyclePhase`** (notification) → deleted; was a verbatim copy of the lifecycle.
3. **`OperationStatus`** (ZAP schema) → deleted; operation status was never a ZAP concept.
4. **`suite/aggregator._SEVERITIES`** — hardcoded 4-tuple that **could not represent CRITICAL** → now derived from `SEVERITY_ORDER`. *This was a live defect: any critical finding was silently dropped from suite aggregation.*
5. **`suite/findings.RISK_ORDER` / `_RISK_RANK` / `risk_rank`** → delegate to domain ordering.
6. **`helpers.findings_from_summary`** — hand-rolled severity dict → builds a `FindingSummary` at the ZAP boundary.
7. **`SlackNotificationChannel._SEVERITIES`** — hardcoded severity list → iterates `SEVERITY_ORDER`; only emoji/labels (genuine Slack presentation) remain local.

**The `total` conflict is resolved by naming, not by changing numbers.** Previously `ZapScanSummary.total` counted all alerts while `ScanFindings.total` excluded informational — the same scan reported different figures on different surfaces. Both behaviours were correct under different names, so the vocabulary now distinguishes `finding_count` (all) from `vulnerability_count` (excludes informational), and no domain term named `total` exists. Verified: a scan with 0 vulnerabilities and 5 informational alerts now reports `finding_count = 5`, `vulnerability_count = 0`, `overall_risk = None` — consistently, everywhere.

## 4. Code deleted

- `OperationStatus` enum body (14 lines), `LifecyclePhase` enum body (24 lines), `ScanFindings` dataclass body (41 lines).
- `_SEVERITIES` tuple (aggregator), `_RISK_RANK` map + `RISK_ORDER` literal list (suite findings), `_SEVERITIES` tuple (Slack adapter).
- 6 unused `OperationPhase` imports introduced during the mechanical rewrite, removed on verification.

## 5. Compatibility shims — introduced and removed within the migration

| Shim | Fate |
|---|---|
| `OperationStatus = OperationPhase` (ZAP schema) | Introduced Phase 2, **removed Phase 5** after all 22 consumers migrated |
| `LifecyclePhase = OperationPhase` (notification) | Introduced Phase 2, **removed Phase 5** |
| `ScanFindings = FindingSummary` | **Attempted and rejected** — see §7 deviation 1 |

**No compatibility shims remain in the codebase.**

## 6. Consumers updated (Phase 4)

36 files rewritten: `dao/` (base, operation_dao, postgres, dynamodb), `schemas/` (internal/operation, ZAP common), `services/` (operations, notification ×4, all three ZAP scan services, suite orchestrator, worker_service), `core/startup.py`, `integrations/chat/slack/channel_adapter.py`, `helpers/`, `bootstrap.py`, and 11 test modules. Routers required no change — they never referenced these types directly.

## 7. Deviations from the ADRs — declared, not improvised

**1. `ScanFindings` was migrated directly rather than through a compatibility shim.**
ADR-0007 Phase 2 calls for shims "where appropriate". A shim was attempted (`ScanFindings = FindingSummary`) and **failed**: ADR-0008 §4.2 mandates a severity-keyed *mapping*, so the constructor signature necessarily differs from the old fixed-field dataclass (`ScanFindings(critical=0, high=1)`). A shim honouring the old signature would have re-created the fixed-field shape the ADR rejects. Since `ScanFindings` had only three consumers and was never publicly exported, they were migrated directly. **This is a deviation in mechanism, not in outcome**, and it is the reason the phrase "where appropriate" mattered.

**2. `ZapScanSummary` was retained.**
ADR-0008 §5 classifies it as a **ZAP wire format**, not a competing domain definition, and ADR-0007 §6.3 flagged it as "requires further review — it is persisted, so stored-result compatibility must be checked". It is persisted inside `ZapScanResult` and would break stored results if removed. It now maps into `FindingSummary` at the helper boundary. **Deleting or reshaping it is a separate decision** involving stored-data migration, and was not taken here.

**3. Report payload keys retain the string `"total"`.**
`severity_summary["total"]` and `application_summary["total"]` remain in the suite's JSON/Markdown output. These are **persisted wire-format keys**, not domain vocabulary — renaming them would break stored reports and the tests pinning the report contract. The ADR's ban on `total` applies to domain signatures, which contain none.

Nothing else diverges. No unapproved concept was introduced: there is no `Result`, `Assessment`, `Metrics`, `Compliance`, `Policy`, `Score`, or `Severity.UNKNOWN` in the codebase.

## 8. Verification performed

| Check | Result |
|---|---|
| Full test suite | 194 passed, 2 pre-existing failures (baseline unchanged) |
| `compileall` on `app` + `tests` | Clean |
| Every `app.domain` + `app.services` module imported, plus composition root | 30 modules, **no circular imports** |
| Rule D4 — domain imports nothing from `app` outside itself | **Clean** (grep-verified) |
| Domain free of FastAPI / Pydantic / Slack / psycopg2 / boto3 / httpx / logging | **Clean** |
| Exactly one definition of `Severity`, `OperationPhase`, `Finding`, `FindingSummary` | **Confirmed** |
| No `OperationStatus` / `LifecyclePhase` / `ScanFindings` symbols remain | **Confirmed** |
| Domain invariants I6, I11, I13, I15, I16, I17 asserted | **Pass** |
| `aios check` (validate + links + lint) | **PASS** |
| `total`-conflict behavioural probe | Consistent across surfaces |

## 9. Remaining technical debt

Recorded, **not** addressed here (each needs its own decision or is out of the approved scope):

1. **`ZapScanSummary` reshaping** — deferred per §7.2; requires a stored-data migration decision.
2. **CRITICAL-2 (fourth-pass review): the Slack adapter still regex-parses rendered text.** The domain model now *exists* to pass instead, but changing `NotificationChannel.send(message: str)` to carry a model is a **port contract change** beyond the approved scope. This is now unblocked and is the highest-value next step.
3. **Untyped event payloads** (HIGH-1) — ADR-0007 §3.4 routed this to `core/` as a Contracts fix; not part of the domain scope.
4. **`OperationProgress` still mixes domain snapshot with presentation fields** — the split is an application-layer refactor, explicitly rejected from domain scope by ADR-0008 §3.5.
5. **`api_scanner.py` remains 442 lines with three responsibilities** — the top hotspot from the responsibility review, untouched here by design.
6. **`BatchType` vs `ZapOperationType`** overlapping taxonomies (HIGH-2) — execution mechanics, out of domain scope.
7. **Two pre-existing test failures** in `test_scan_lifecycle_notification_flow` — assert renderer wording ("Scan completed") that the renderer has not produced since before this work. Fixing them is a behaviour decision about card copy, deliberately not bundled into an architecture migration.
8. **AIOS governance for the domain layer is not yet written** — ADR-0007 §7 proposes amending `backend-layering` to 1.1.0 and adding a `domain-layer` standard with rules D1–D4. The user's instruction for this task excluded AIOS updates; that governance work remains outstanding, and until it lands the D1–D4 rules are documented in ADRs but not mechanically enforced.
