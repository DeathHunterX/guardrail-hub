# Worker Lifecycle

## Identity

A worker's `worker_id` is whatever it reports at registration — in practice its container `HOSTNAME` (`docker/owasp_zap/register-worker.sh` uses `${HOSTNAME}` directly). There is no prefix, no index, no naming scheme the server imposes. If a worker registers without an explicit `worker_id`, the server falls back to `hostname`, and if that's also absent, generates a UUID (`generate_worker_id()` in `app/schemas/tools/owasp_zap/worker.py`) — but in normal operation a worker always has a hostname.

## Registration

```
Worker Start -> Read HOSTNAME -> Build Endpoint -> POST /workers/register
```

`POST /workers/register` (`app/routers/public/zap_worker_router.py`) accepts `worker_id` (optional), `hostname`, `endpoint`, `port`, `version` (optional), and upserts into the Worker Registry (`app/integrations/owasp_zap/registry.py`). Registering an already-known `worker_id` is a safe re-registration (e.g. the worker process restarted): `hostname`/`endpoint`/`port`/`version` refresh, `last_heartbeat` resets, and the worker returns to `ACTIVE`. Its `op_id`, if any, is left untouched by a bare register call — an operation in flight is only ever resolved by the heartbeat-timeout sweep or by the worker itself finishing/failing it, never silently erased by a registration.

## Heartbeat

```
... every ZAP_WORKER_HEARTBEAT_INTERVAL_SECONDS ... -> POST /workers/heartbeat
```

`POST /workers/heartbeat` refreshes `last_heartbeat`. If the worker was `OFFLINE` (reaped for a timeout, but actually still alive), a heartbeat self-heals it back to `ACTIVE`. If the `worker_id` is unknown to the registry at all (never registered, explicitly removed, or the mcp-server process itself restarted and lost registry state), the endpoint returns **404** — the worker-side script treats that as "call `/workers/register` again," not as a fatal error.

## Busy / Idle (derived, not tracked)

There is no separate status field for busy/idle. A worker is Idle exactly when `op_id is None`; it is Busy exactly when `op_id` holds an operation id. The Pool Manager sets `op_id` via `registry.assign()` when a queued operation is handed to a worker, and clears it via `registry.release()` when that operation finishes (success or failure) — see [pool-manager.md](pool-manager.md).

## Maintenance lifecycle

```
Active -> Draining -> (finish current operation) -> Offline
```

* **Active** — the default state. Schedulable when also idle (`ZapWorkerInfo.is_schedulable`).
* **Draining** — `POST /workers/{worker_id}/drain` sets this. A Draining worker receives no new assignments (the Scheduler skips it — see [pool-manager.md](pool-manager.md)) but is left alone if it's mid-operation.
* **Offline** — reached two ways:
  1. **Automatically**, the moment a Draining worker's current operation finishes and it's released (`registry.release()` transitions `DRAINING -> OFFLINE` on release, per the lifecycle diagram above) — no separate "confirm offline" call needed.
  2. **Via heartbeat timeout** (see below) or **explicit removal** (`DELETE /workers/{worker_id}`).

## Worker removal

Two paths, same guarantee — *a worker that's gone can never be assigned to again, and an operation it was running never sits `RUNNING` forever with nobody executing it*:

| Path | Trigger | What happens |
|---|---|---|
| Heartbeat timeout | No heartbeat for `ZAP_WORKER_HEARTBEAT_TIMEOUT_SECONDS` (checked every `ZAP_WORKER_HEARTBEAT_SWEEP_INTERVAL_SECONDS` by `OwaspZapDispatcher`'s sweep loop) | Worker marked `OFFLINE`. If it held an `op_id`, that operation is marked `FAILED` with an explanatory error. **No automatic retry** — resubmitting is a user decision. |
| Manual / graceful removal | `DELETE /workers/{worker_id}` (also called by `register-worker.sh`'s `SIGTERM` trap on a clean `docker compose down`/scale-down) | Worker removed from the registry immediately. If it held an `op_id`, that operation is marked `FAILED` the same way. |

## Worker addition

A new worker (e.g. `docker compose up --scale zap=5` adding two replicas to an existing three) needs **no server restart and no configuration reload**: it runs the same entrypoint, reads its own `HOSTNAME`, and calls `/workers/register`. The Pool Manager's next scheduling pass sees it via `registry.list_all()` automatically — there is no separate "recognize new workers" step to run.
