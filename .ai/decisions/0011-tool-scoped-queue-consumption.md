# 0011 — Tool-Scoped Queue Consumption

Status: **Accepted** — ratified 2026-07-29 by the backend owner, ahead of JMeter Phase 1. Not yet implemented; §5 makes it Phase 1 step 0, and no `jmeter_test` operation may be creatable before it lands.
Owner: Loi Phan
Date: 2026-07-28
Relates to: [Decision 0005](0005-architecture-hardening-refactor.md) (restored `get_queued_operations()` and preserved the queue/dispatch model — the code this ADR extends), [Decision 0009](0009-execution-capability.md) (execution stays tool-specific; no execution capability).
Implemented by: [architecture/jmeter-engine/queue-isolation.md](../../architecture/jmeter-engine/queue-isolation.md).

---

## 1. Context

The Operations table *is* the queue — there is no in-memory queue, which is what lets pending work survive a restart. Today exactly one dispatcher reads it, so the read needs no filter:

`BaseOperationDAO.get_queued_operations()` returns every `QUEUED` row. `OwaspZapDispatcher` then resolves each row's `metadata["operation_type"]` against the **ZAP** operation registry, and an unresolvable type is not skipped — it is failed via `operation_service.fail(...)`.

A second engine therefore cannot simply be added. The first JMeter operation submitted would be marked `FAILED` by the ZAP dispatcher within one poll tick, before the JMeter dispatcher ever saw it. This is silent data loss from the user's point of view: they submitted a load test and got back a failure that no JMeter code produced. It is the single hard conflict identified in the JMeter architecture validation.

## 2. Options considered

**(a) Filter the queue read by `batch_type`; each dispatcher declares its lane.** The discriminator already exists as a column on every row.

**(b) A separate queue (table, or a JMeter-specific store) per engine.** Removes contention by removing sharing.

**(c) A generic dispatch/routing layer that owns the single queue and routes rows to registered engines.** One reader, many handlers.

## 3. Decision

**Option (a). `get_queued_operations(batch_types)` takes a required collection of `batch_type` values, and each dispatcher passes the lane it owns.**

- `BatchType` gains `JMETER_TEST` and `ALL_JMETER_TYPES`. `ALL_SCAN_TYPES` — which already exists and already contains exactly the five ZAP types — becomes the ZAP lane unchanged.
- `OwaspZapDispatcher` passes `ALL_SCAN_TYPES`; `JMeterDispatcher` passes `ALL_JMETER_TYPES`.
- The parameter is **required**, with no "everything" default.

### 3.1 Why (b) is rejected

A second queue means a second durability story, a second restart-recovery path, and a second thing to back up and reason about — to solve a problem that is one `WHERE` clause. It would also fork `HistoryService` and the notification pipeline, both of which read operations uniformly today. ADR-0005 chose one durable operations store deliberately; splitting it for the second tool would undo that on the second tool.

### 3.2 Why (c) is rejected

Option (c) is an execution abstraction wearing a different hat, and [ADR-0009](0009-execution-capability.md) reached the same conclusion on the same evidence base: you cannot usefully abstract over a set of one — and a routing layer built for two engines, where the second does not exist yet, is a set of one plus a guess. ADR-0009 §2.2 records that the last speculative execution abstraction in this codebase (`ExecutionStrategy`) shipped five members of which three were never used. A routing layer is also strictly more code than a filter, and would touch the ZAP path, which this change must not do.

> **Citation note.** ADR-0009 is itself still **Proposed**. This ADR cites its *verified evidence* (the dead `ExecutionStrategy` members, checkable in source today), not its authority, and does not depend on its ratification. Were ADR-0009 rejected outright, §3.2 would stand unchanged.

### 3.3 Why the parameter is required rather than defaulted

A default of "return everything" preserves the current call sites at the cost of preserving the bug: the next engine's dispatcher, written by someone who has not read this ADR, gets the destructive behavior by omission. Queue consumption is a data-loss boundary — it takes an explicit argument. There is one call site today; making it explicit costs one line.

## 4. Consequences

**Gained:**

- Each dispatcher provably consumes only its own rows; the lanes are disjoint at the query.
- ZAP behavior is bit-for-bit unchanged: its lane is the pre-existing `ALL_SCAN_TYPES`, every legacy row carries one of those five types, and FIFO order is preserved.
- The change is additive — one constant, one frozenset, one parameter, one SQL predicate, one deleted DynamoDB override. No schema migration, no new component, no new abstraction.
- Fairness between engines falls out: a deep queue in one lane cannot starve the other.
- `analyze_jmeter_result`'s "does this operation belong to JMeter?" check reuses the same field.

**Accepted:**

- A `batch_type` belonging to no lane becomes invisible to every dispatcher and stays `QUEUED` silently, instead of being loudly failed. This trades a loud wrong outcome for a quiet stall. It is guarded by a single unit test asserting every dispatchable `BatchType` member belongs to exactly one lane — adding a member without a lane fails the build.
- Every future engine must claim a lane. That is the intended obligation, and it is enforced by the required parameter plus that test.

**Explicitly not decided here:** multi-process dispatcher deployment and row-level claim locking. The single-dispatcher-per-engine-per-process assumption is pre-existing and unchanged; this ADR neither improves nor worsens it.

## 5. Ordering

This change must land **before** any code path can create a `jmeter_test` operation — Phase 1 step 0. Until the ZAP dispatcher's read is filtered, the first JMeter row submitted is destroyed by it.
