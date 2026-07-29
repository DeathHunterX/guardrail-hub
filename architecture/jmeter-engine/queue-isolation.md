# JMeter Engine — Queue Isolation (Final Design)

Status: **Final** — decided 2026-07-28. Governed by [ADR-0011](../../.ai/decisions/0011-tool-scoped-queue-consumption.md).
Resolves: conflict **C1** and adjustment **A1** of the [architecture validation report](../../jmeter-engine-architecture-review.md).

---

## 1. The problem being closed

The Operations table *is* the queue. `BaseOperationDAO.get_queued_operations()` returns **every** `QUEUED` row with no tool filter, and `OwaspZapDispatcher._dispatch_one` resolves each row's `metadata["operation_type"]` against the **ZAP** operation registry. An unresolvable type is not skipped — it is failed:

```python
# app/services/tools/owasp_zap/execution/dispatcher.py
queued = self._operation_dao.get_queued_operations()      # every QUEUED row
...
zap_operation = self._registry.resolve_from_metadata(operation.metadata)
except Exception:
    self._operation_service.fail(operation.operation_id, ...)   # ← JMeter row dies here
```

So a JMeter operation submitted today would be marked `FAILED` by the ZAP dispatcher within one poll tick, before a JMeter dispatcher ever saw it. Symmetrically, a JMeter dispatcher polling the same unfiltered query would fight over ZAP rows.

## 2. The decision

**Each dispatcher declares the `batch_type` lane it owns, and the queue read is filtered by that lane. `batch_types` is a required parameter — there is no "poll everything" default.**

The row's existing `batch_type` column is the lane discriminator. Nothing new is persisted, no schema migration, no new table, no new queue.

### 2.1 Lane constants — `app/constants/batch.py` (additive)

```python
class BatchType:
    API_SCAN = "api_scan"
    WEB_SCAN = "web_scan"
    INTERACTIVE_SCAN = "interactive_scan"
    BATCH_SCAN = "batch_scan"
    SUITE_SCAN = "suite_scan"
    JMETER_TEST = "jmeter_test"          # NEW
    UNKNOWN = "unknown"

    ALL_SCAN_TYPES: frozenset[str] = frozenset(       # unchanged — the ZAP lane
        {API_SCAN, WEB_SCAN, INTERACTIVE_SCAN, BATCH_SCAN, SUITE_SCAN}
    )
    ALL_JMETER_TYPES: frozenset[str] = frozenset({JMETER_TEST})   # NEW — the JMeter lane
```

`ALL_SCAN_TYPES` already exists and already contains exactly the five ZAP types. The ZAP lane is therefore *pre-defined by the current code* — this design does not redraw it.

### 2.2 DAO contract — `app/dao/base.py`

```python
def get_queued_operations(self, batch_types: Collection[str]) -> list[OperationRecord]:
    """Return QUEUED operations whose batch_type is in *batch_types*, oldest first."""
    records = [
        r for r in self.get_by_status(OperationPhase.QUEUED)
        if r.batch_type in batch_types
    ]
    return sorted(records, key=lambda r: r.created_at)
```

The parameter is **required, not defaulted**. A default of "all rows" would silently reintroduce C1 the first time a third engine's dispatcher was written by someone who did not read this document. This is a data-loss boundary; it gets an explicit argument.

### 2.3 PostgreSQL — `app/dao/postgres/operation_dao.py`

Keep the native ordered query; add one predicate:

```sql
SELECT {_LIST_COLUMNS} FROM operations
WHERE status = %(status)s AND batch_type = ANY(%(batch_types)s)
ORDER BY created_at ASC
```

with `{"status": OperationPhase.QUEUED, "batch_types": list(batch_types)}`. The existing `idx_operations_status_created_at` index still serves the `status` predicate and the ordering; `batch_type` is a cheap residual filter over an already-small `QUEUED` set. **No new index and no migration** — add one only if queue depth ever makes it measurable.

### 2.4 DynamoDB — `app/dao/dynamodb/operation_dao.py`

**Delete the override.** Its only job today is sorting, which the base implementation in §2.2 now does along with the filtering. DynamoDB inherits the base method and behaves identically to today (a `status`-filtered scan, then client-side work) — one method less to keep in sync between the two backends.

> Design note, deliberately not built: the `batch_type` filter could be pushed into the scan's `FilterExpression`. It would reduce transferred items, not scanned capacity, and `batch_type` is already in `_LIST_PROJECTION`. Add it if queue volume ever makes the transfer cost visible.

### 2.5 Call sites

| Dispatcher | Passes | Sees |
|---|---|---|
| `OwaspZapDispatcher` | `BatchType.ALL_SCAN_TYPES` | only the five ZAP types |
| `JMeterDispatcher` (Phase 1) | `BatchType.ALL_JMETER_TYPES` | only `jmeter_test` |

The lane constant is referenced directly at the call site inside each tool-specific dispatcher — it is not injected. A dispatcher class named `OwaspZapDispatcher` already knows which tool it is; a constructor parameter would only create the opportunity to configure it wrong.

## 3. Why this satisfies the constraints

| Requirement | How |
|---|---|
| Each dispatcher consumes only its own operations | Disjoint `batch_type` lanes, enforced at the query |
| Existing ZAP behavior unchanged | ZAP's lane is the pre-existing `ALL_SCAN_TYPES`; every legacy row carries one of those five types, so the ZAP dispatcher sees exactly the rows it sees today, in the same FIFO order |
| Additive | One constant, one frozenset, one parameter, one SQL predicate, one deleted override. No schema change, no data migration, no new component |
| No speculative abstraction | No engine registry, no dispatch-routing layer, no capability negotiation. Two engines, two constants |

Two further properties fall out for free:

- **Fairness.** A deep JMeter queue can no longer starve ZAP (or vice versa) — the lanes are polled independently, FIFO preserved within each.
- **`analyze_jmeter_result`'s ownership check.** "Does this operation belong to JMeter?" is `record.batch_type in BatchType.ALL_JMETER_TYPES`. No second mechanism needed.

Also closed: the legacy path where a row *missing* `operation_type` is defaulted to `API_SCAN`. That code is untouched, but a JMeter row can no longer reach it.

## 4. Failure mode this introduces, and its check

A row created with a `batch_type` that belongs to **no** lane is now invisible to every dispatcher and stays `QUEUED` forever — silent instead of loudly `FAILED`.

Mitigation is one assertion, not a mechanism:

```python
# tests/dao/test_batch_lanes.py
def test_every_dispatchable_batch_type_belongs_to_exactly_one_lane():
    lanes = [BatchType.ALL_SCAN_TYPES, BatchType.ALL_JMETER_TYPES]
    dispatchable = {
        v for k, v in vars(BatchType).items()
        if isinstance(v, str) and not k.startswith("_") and v != BatchType.UNKNOWN
    }
    owned = [t for t in dispatchable if sum(t in lane for lane in lanes) == 1]
    assert sorted(owned) == sorted(dispatchable)
```

Adding a `BatchType` member without assigning it a lane fails this test. That is the whole guard.

## 5. Ordering constraint for Phase 1

§2.1–§2.5 must land **before** any code path can create a `jmeter_test` operation. Until the ZAP dispatcher is filtered, the first JMeter row submitted is destroyed by it. Treat this as Phase 1 step 0, ahead of the JMeter skeleton itself.

## 6. Out of scope (explicitly not decided here)

- Multi-process dispatcher deployment / row-level claim locking. The current single-dispatcher-per-engine-per-process assumption is pre-existing, unchanged by this design, and is not a JMeter problem.
- Priority, weighting, or cross-lane scheduling. FIFO within a lane is what exists today and all that is required.
