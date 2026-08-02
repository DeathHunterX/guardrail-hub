# JMeter Engine — Governance Finalization Report

Date: 2026-07-29 · Scope: governance review only — no dispatcher, runtime, worker, parser, analyzer, or MCP tool code was written.
Reviewed: [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md), [ADR-0011](../../.ai/decisions/0011-tool-scoped-queue-consumption.md), and the four design documents in this folder.
Outcome: **both ADRs Accepted. Repository is ready for Phase 1 — JMeter Skeleton.**

---

## 1. ADR review summary

Both ADRs were re-read against their cited sources rather than against memory. Every citation was opened and checked. Five defects were found and corrected; none were substantive enough to change either decision, and all are now closed.

### 1.1 ADR-0010 — JMeter Result Contract

| Dimension | Finding |
|---|---|
| **Consistency** | ✅ The four-section contract (`summary` / `metrics` / `artifacts` / `metadata`) matches [result-contract.md](result-contract.md) field for field. The §3.3 numbered decisions each have a corresponding section in the design doc |
| **Rationale** | ✅ Sound, and it does something better than agreeing with itself: it re-tests ADR-0008 §2.4's *reason* for deferral rather than mechanically obeying the §6 trigger. The load-bearing claim — that ZAP and JMeter results share no field but `operation_id` — is verifiable against `ZapScanResult` and holds |
| **Consequences** | ✅ States what is accepted (an unpaid refactor, two unrelated shapes in one column) as well as what is gained, and bounds the risk correctly: the refactor is a wrapper, not a data migration |
| **References** | ⚠️ **One defect, fixed.** The note *"One per tool; never shared"* was attributed to ADR-0008 §5; it is in §7's ownership matrix. Corrected to cite both |
| **AIOS alignment** | ✅ Respects the source-priority order (Guardrails → Standards → Decisions). Applies backend-layering R3 and backend-naming R4. Touches no Standard and no Guardrail, so no version bump or impact analysis is owed |
| **Scope statement** | ⚠️ **One defect, fixed.** The "Not authorized" clause omitted `ReportPaths.JMETER_DETAIL_DIR`, which [result-contract.md](result-contract.md) §7 requires — an ADR forbidding something its own design mandates. Replaced with a positive, complete authorization list of three items |

**Verdict: no blocking issues. Accept.**

### 1.2 ADR-0011 — Tool-Scoped Queue Consumption

| Dimension | Finding |
|---|---|
| **Consistency** | ✅ Matches [queue-isolation.md](queue-isolation.md): required `batch_types` parameter, `ALL_SCAN_TYPES` unchanged as the ZAP lane, `ALL_JMETER_TYPES` added, DynamoDB override deleted |
| **Rationale** | ✅ The problem is verified in source, not asserted: `get_queued_operations()` is unfiltered and `OwaspZapDispatcher._dispatch_one` *fails* (not skips) an unresolvable type. Options (b) and (c) are rejected on stated grounds rather than dismissed |
| **Consequences** | ✅ Names the failure mode it introduces — a laneless `batch_type` stalls silently instead of failing loudly — and pairs it with a single unit test rather than a mechanism. Correctly scopes out multi-process claim locking as pre-existing |
| **Implementation ordering** | ✅ Unambiguous and stated twice (§5 and the design doc): the lane filter is **Phase 1 step 0**, before anything can create a `jmeter_test` row. This is the one ordering constraint that causes data loss if ignored |
| **AIOS alignment** | ✅ Additive change to `dao/` and `constants/`; no layering violation, no new top-level role, no Standard amended |
| **References** | ⚠️ **Two defects, fixed.** (1) ADR-0005 was described as establishing the Operations table as the durable queue; it restored `get_queued_operations()` and preserved the queue/dispatch model — the citation was overstated and is now precise. (2) ADR-0009 was cited as having *"rejected exactly that"*, which leans on an unratified ADR's authority. Reworded to cite its **verified evidence** (the three never-used `ExecutionStrategy` members, checkable in source today), with an explicit note that §3.2 stands even if ADR-0009 is rejected |

**Verdict: no blocking issues. Accept.**

### 1.3 One thing deliberately left alone

ADR-0009 remains **Proposed**. It is not a prerequisite: neither new ADR depends on its authority (§1.2), and JMeter reuses no part of the ZAP execution contract. It stays on the owner's desk as a standing item, and its revisit trigger fires *after* JMeter is built and observable — not now. Precedent exists for this state: ADR-0004 has been Proposed since 2026-07-07 with ChatOps shipped.

## 2. Status changes applied

| ADR | Before | After |
|---|---|---|
| [0010 — The JMeter Result Contract](../../.ai/decisions/0010-jmeter-result-contract.md) | Proposed | **Accepted** — ratified 2026-07-29 |
| [0011 — Tool-Scoped Queue Consumption](../../.ai/decisions/0011-tool-scoped-queue-consumption.md) | Proposed | **Accepted** — ratified 2026-07-29 |

Wording follows the repository's convention for a ratified-but-unimplemented decision (`Status: **Accepted** — ratified <date>`, per ADR-0007/0008), and each status line states plainly that no code realizes it yet. [`.ai/decisions/README.md`](../../.ai/decisions/README.md) index updated to match.

Both were ratified **before** implementation, deliberately — the same sequencing ADR-0008 §10 argued for and got: settle the contract first, so the implementation cannot quietly encode a different one.

## 3. Cross-reference validation

| Check | Result |
|---|---|
| `python .ai/tools/aios.py check` (validate + links + lint + arch) | ✅ **PASS** — 14 units, 0 errors; **734 links checked, 0 broken**; 6 routing files under ceiling; 0 domain boundary violations |
| Links in `architecture/` (outside `aios links`' `.ai/` scope, so checked separately) | ✅ 44 checked, 0 broken |
| ADRs → architecture documents | ✅ Both ADRs link to their implementing design doc |
| Architecture documents → ADRs | ✅ All four design docs and the folder README cite the now-Accepted ADRs |
| ADR citations → cited source sections | ✅ Verified by opening each; 3 defects found and fixed (§1.1, §1.2) |
| Stale references to the removed directories | ✅ Cleared where live, preserved where historical (below) |

### 3.1 Stale references — what was changed and what was deliberately not

**Updated** (made stale by this milestone's cleanup, and these documents describe what exists *today*):

- `.ai/intelligence/module-map.md` — `app/integrations/jmeter/` and `app/services/tools/jmeter/` were listed as *Empty*; both now record removal and point here. The second row was split so `app/services/internal/` keeps its own accurate entry.
- `.ai/intelligence/security-map.md` — the JMeter row said "Empty directories only"; it now records the finalized architecture and carries forward the G4 note that a load engine's misdirected traffic is a denial-of-service.

**Deliberately left unchanged:**

- **ADR-0005 §"Removed empty scaffold directories" and ADR-0007 §2.4** mention these paths as they were. Decision records are append-only — [`.ai/decisions/README.md`](../../.ai/decisions/README.md) states a later decision supersedes rather than edits. Editing them would falsify the record.
- **`.ai/architecture/evidence/*` and `architecture/chatops/MVP-FOUNDATION-RECONCILIATION.md`** are dated snapshots of a past review. Same reasoning.
- **`backend-layering.md` anti-pattern example** ("a JMeter client dropped in `helpers/` instead of `integrations/jmeter/`") is prescriptive, not descriptive — it is now more accurate, not less.

### 3.2 Two pre-existing issues found, not fixed (out of scope, raised for the record)

1. **`.ai/intelligence/` drift baseline is self-declared stale.** `scripts/sources.json` records `verified_commit: "10bd79b-SUPERSEDED-see-ADR-0005"` and *"re-verification pending after 2026-07-10 hardening refactor"*. The drift checker was therefore not re-baselined — running `check_drift.py --update` would have recorded a full re-verification that did not happen, converting a known-stale baseline into a falsely-fresh one. This is an ADR-0005 follow-up item, not a JMeter one.
2. **`module-map.md` still lists `app/client/`, `app/policies/`, `app/prompts/`, `app/runner/`, `app/security/` as Empty.** None exist — ADR-0005 deleted them in July. Unrelated to JMeter and left untouched per this task's scope, but it is the same class of staleness and worth one pass when item 1 is addressed.

Neither blocks Phase 1. Both are recorded so they are not rediscovered as surprises.

## 4. Implementation readiness checklist

| # | Prerequisite | State | Evidence |
|---|---|---|---|
| 1 | **Governance complete** | ✅ | ADR-0010 and ADR-0011 Accepted; decisions index consistent; no ADR in this chain awaiting a decision that blocks Phase 1 |
| 2 | **Queue decision accepted** | ✅ | [ADR-0011](../../.ai/decisions/0011-tool-scoped-queue-consumption.md) Accepted; design in [queue-isolation.md](queue-isolation.md) specifies the exact DAO signature, both backend implementations, both call sites, and the lane test |
| 3 | **Result contract accepted** | ✅ | [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md) Accepted; `JMeterTestResult` fully specified in [result-contract.md](result-contract.md), including artifact paths and the two `bootstrap.py` presentation rows |
| 4 | **Architecture ready** | ✅ | Runtime / Worker / Parser / Analyzer boundaries fixed with no overlap; `runtime.py` ambiguity resolved by layer; package layout, async `run_jmeter` contract, and G4 enforcement point all settled — [runtime-responsibility.md](runtime-responsibility.md) |
| 5 | **Repository ready** | ✅ | Seven revert-remnant directories removed and verified unreferenced; no orphaned `__pycache__`; 113 app files parse; `aios check` PASS — [cleanup.md](cleanup.md) |
| 6 | **No unresolved architecture decisions** | ✅ | The validation report's C1–C4 are closed by ADR-0011, this folder's §5 pattern-reuse table, the `ReportPaths` decision, and ADR-0010 respectively. A1–A9 are all dispositioned |

**Standing items that do not gate Phase 1:** ratify or reject ADR-0009 (§1.3); the two intelligence-maintenance items (§3.2); the three cleanup recommendations in [cleanup.md](cleanup.md) §2.

## 5. Conclusion

Governance is complete. Both required decisions are Accepted with their reasoning, their rejected alternatives, and their accepted costs on the record; every cross-reference resolves; the repository contains no remnant that Phase 1 could collide with.

**Phase 1 — JMeter Skeleton may begin, with one hard ordering constraint:** the queue lane change lands first. Until `OwaspZapDispatcher` polls a filtered queue, the first `jmeter_test` row created is destroyed by it within one poll tick.
