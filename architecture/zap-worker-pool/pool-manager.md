# Pool Manager & Scheduling

## Split of responsibilities

`OwaspZapPoolManager` (`app/integrations/owasp_zap/pool.py`) does not itself decide who is registered or which worker is "best" — it composes two smaller, independently-testable pieces:

* **`OwaspZapWorkerRegistry`** (`registry.py`) — the source of truth for *who* is registered, their `endpoint`, and busy/idle (see [worker-lifecycle.md](worker-lifecycle.md)).
* **`WorkerScheduler`** (`scheduler.py`) — a small `Protocol` with one method, `select(workers) -> Optional[ZapWorkerInfo]`, deciding *which* eligible worker runs next.

This split exists specifically so the scheduling algorithm is isolated and replaceable — swapping Round Robin for, say, least-recently-used or weighted-by-capacity later means implementing `WorkerScheduler` and passing the new instance into `OwaspZapPoolManager`; nothing else changes.

## Round Robin (the default strategy)

`RoundRobinScheduler` does **not** simply take "the first idle worker" — that would starve whichever worker sorts last. Instead it keeps a persistent cursor over the full, stably-ordered (`sorted by worker_id`) list of *every* registered worker — idle, busy, draining, offline, all of them — and on each call scans forward from the cursor for the first one that is both idle and `ACTIVE`, wrapping around once, then advances the cursor to just past whichever one it picked. Rotating over the *full* set (not just whoever happens to be idle at this instant) is what makes it fair over time: a worker that was busy last time doesn't get skipped forever just because the cursor moved past its position while it was unavailable.

## Assignment flow

```
Dispatcher.try_assign(operation_id)
  -> PoolManager.try_assign(operation_id)
       -> candidates = Registry.list_all()
       -> chosen = Scheduler.select(candidates)
       -> if chosen: Registry.assign(chosen.worker_id, operation_id)
       -> return chosen (or None)
```

`try_assign` returning `None` means "no eligible worker right now" — the operation simply stays `QUEUED`; there is nothing to undo, because nothing was assigned. The Dispatcher retries it on the next poll tick (see [sequence-diagrams.md](sequence-diagrams.md)).

## ZapClient caching

`get_client(worker)` caches one `ZapClient` per `worker_id`, keyed and validated against the worker's current `endpoint` — if a worker re-registers with a different endpoint (e.g. it restarted and picked up a new address), the cached client is rebuilt rather than silently pointed at a stale URL. This replaces the old pool's fixed `{prefix}-{i}: ZapClient` dict built once at startup.

## Why this isn't in the Registry itself

Keeping scheduling out of the Registry means the Registry's job stays purely "what do I know, and is it current" — no scheduling policy leaks into it, and the Registry can be tested, read, and reasoned about (e.g. by the worker router's `GET /workers` observability endpoint) with zero awareness of *how* work gets assigned.
