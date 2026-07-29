# 0010 — The JMeter Result Contract (and why the `Result` root is still deferred)

Status: **Accepted** — ratified 2026-07-29 by the backend owner, ahead of JMeter Phase 1 and before any implementation, following the ADR-0008-before-ADR-0007 precedent (settle the contract first, then build against it). Not yet implemented: Phase 1 (JMeter Skeleton) is the first code that realizes it.
Owner: Loi Phan
Date: 2026-07-28
Fires the trigger recorded in: [Decision 0008](0008-domain-ubiquitous-language.md) §6 — *"`Result` (root; `Findings` | `Metrics` as kinds) — Trigger: First non-security tool (**JMeter**)"*.
Relates to: [Decision 0007](0007-domain-layer-justification.md) (the evidentiary standard), [Decision 0009](0009-execution-capability.md) (the same refusal-to-generalize applied to execution).
Implemented by: [architecture/jmeter-engine/result-contract.md](../../architecture/jmeter-engine/result-contract.md).

---

## 1. Context

ADR-0008 defined the canonical domain language and deliberately left one door open. It ruled that `Finding` is a root **today**, and recorded `Result` (with `Findings` and `Metrics` as kinds) as a *future* root whose trigger is the arrival of the first non-security tool — naming JMeter explicitly. It also recorded the cost honestly: *"promoting `Finding` under a `Result` root later is a refactor, and this ADR accepts that cost."*

JMeter is now being implemented. The trigger has fired. ADR-0008 §9.3 makes the future table a contract, so this decision must be **written down, not defaulted** — either direction is a governance-visible choice.

The concrete question: when a JMeter operation completes, what shape goes into `operation.result`?

## 2. Options considered

**(a) Tool-specific wire format now, domain root deferred.** A `JMeterTestResult` Pydantic model in `app/schemas/tools/jmeter/`, persisted into `operation.result` and consumed by `analyze_jmeter_result`. `Finding` stays a root. No `Result`, no `Metrics` in `domain/`.

**(b) Introduce the `Result` root now.** Add `Result` to `domain/` with `Findings` and `Metrics` as kinds, move `Finding` underneath it, and have both ZAP and JMeter produce `Result`s.

## 3. Decision

**Option (a). Ship the JMeter result as a tool-specific wire format. Do not introduce the `Result` root or a `Metrics` domain concept.**

### 3.1 Why (b) is rejected *for now*

The trigger in ADR-0008 §6 reads "first non-security tool." Taken literally it has fired. But the *reason* the concept was deferred — stated in §2.4 — was that `Result` "would have exactly one implementation today." Check whether that reason has actually gone away:

- A `Result` root introduced today would have two *tools* under it, but the two produce **no shared field**. ZAP produces alerts, severities, TLS posture. JMeter produces latency percentiles, throughput, error rate. There is no attribute, no invariant, and no operation that both kinds answer. The only thing they share is `operation_id` — which belongs to `Operation`, a root that already exists and already carries it.
- An abstraction whose common surface is empty is not an abstraction; it is a naming ceremony. It would be justified by symmetry, which ADR-0007 §2.4 and ADR-0008's own rules forbid as a justification.
- ADR-0008 §5 already classifies `ZapAlert`/`ZapScanResult` as **wire formats** owned by each tool's adapter, and its §7 ownership matrix records the rule for them explicitly: *"One per tool; never shared."* A `JMeterTestResult` wire format is the consistent application of an existing ruling, not a new position.

The honest reading: §6's trigger identified *when to re-examine the question*, not a commitment to build on sight. This ADR re-examines it, on the evidence, and finds the original reason intact.

### 3.2 What would change the answer

`Result` earns its existence when something needs to consume both kinds **without knowing which it has**. Concretely, any one of:

- A `Policy` / gating capability that must evaluate "did this operation pass?" across security *and* performance operations.
- A cross-tool report or dashboard rendering both kinds through one code path.
- A third tool producing a *third* kind (e.g. coverage), making the per-tool wire format the thing being duplicated.

None exist. When one does, the refactor ADR-0008 §10 already priced is the correct move — and by then there will be two real shapes to generalize *from* rather than one to guess *at*. This is the same Implement → Observe → Extract discipline ADR-0009 applied to execution.

### 3.3 What is being decided, precisely

1. `operation.result` for a JMeter operation holds a serialized `JMeterTestResult`, defined in [architecture/jmeter-engine/result-contract.md](../../architecture/jmeter-engine/result-contract.md), living in `app/schemas/tools/jmeter/result.py`.
2. It has exactly four sections: `summary`, `metrics`, `artifacts`, `metadata` — plus `operation_id`.
3. It carries **no** lifecycle status and no error string; the `Operation` owns those (ADR-0008 §3.1, invariants I2/I3). Two sources of truth for status is the defect this avoids.
4. It carries **no** SLA verdict, threshold, or pass/fail judgment. That is `Policy` (ADR-0008 §6), whose trigger has *not* fired.
5. It produces no `Finding`s and passes no `findings=` to `OperationService.complete()`. ADR-0008 §2.4 already established a load test has none.
6. `Finding` remains a root. `domain/` is unchanged by this ADR.

## 4. Consequences

**Accepted:**

- The `Finding`-under-`Result` refactor stays on the books, unpaid. ADR-0008 §10 already accepted this trade explicitly; this ADR re-affirms it with a second data point rather than reversing it.
- Two tools now persist two unrelated shapes into the same `result` column. Consumers must know the tool before reading — which they already do, via `operation.batch_type` (see [Decision 0011](0011-tool-scoped-queue-consumption.md)).

**Gained:**

- Phase 1 is unblocked without a `domain/` change, so JMeter cannot destabilize the security vocabulary while it is being built.
- The `Result` decision will eventually be made against two implemented, observed shapes instead of one implemented and one imagined.

**Risk, and its bound:** if a gating requirement lands soon after JMeter, the refactor is paid shortly after it was deferred. Bounded by the fact that the refactor is a *rename plus a wrapper*, not a data migration — the persisted per-tool payloads keep their shape under either design.

## 5. Governance note

This ADR **does not** amend ADR-0008. The §6 entry for `Result` / `Metrics` stands as written; its trigger fired and was answered "defer, with reasons and new triggers" (§3.2). A future ADR that introduces `Result` should cite §3.2 of this document and show which of the three named conditions has occurred.

**Authorized by this ADR — the complete list:** the result models in `app/schemas/tools/jmeter/`; the two additive presentation rows in `app/bootstrap.py` (`OPERATION_TITLES` entry, widened report-link lookup); and `ReportPaths.JMETER_DETAIL_DIR` in `app/constants/paths.py`. All three are specified in the [result-contract design](../../architecture/jmeter-engine/result-contract.md) §5 and §7.

**Not authorized by this ADR:** any change to `domain/`, and any code outside the three items above.
