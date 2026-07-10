# Configuration

Full variable reference (defaults, types): [`mcp-server/docs/configuration.md`](../../mcp-server/docs/configuration.md#owasp-zap). This page is the architecture-level summary — what each setting *controls*, not just its default.

## What no longer exists

`ZAP_CONTAINER_NAME_PREFIX` and `ZAP_AMOUNT_OF_CONTAINERS` are gone. There is no worker name, prefix, hostname array, or count to configure anywhere — worker discovery happens entirely through registration (`POST /workers/register`). If you're looking for "how many ZAP workers are there," the answer is runtime state (`GET /workers`, or `zap_workers_registered` on `GET /`), not configuration.

## Server-side (`mcp-server`)

| Variable | Controls |
|---|---|
| `ZAP_API_KEY` | The shared API key the server uses to talk to every worker's ZAP REST API. |
| `ZAP_SCAN_TIMEOUT_SECONDS` / `ZAP_SPIDER_TIMEOUT_SECONDS` / `ZAP_PASSIVE_SCAN_TIMEOUT_SECONDS` / `ZAP_REQUEST_TIMEOUT_SECONDS` | Per-scan-phase timeouts, unchanged from before this refactor. |
| `ZAP_WORKER_HEARTBEAT_TIMEOUT_SECONDS` | How long a worker can go silent before the Registry marks it Offline and its in-flight operation (if any) is marked `FAILED`. |
| `ZAP_WORKER_HEARTBEAT_SWEEP_INTERVAL_SECONDS` | How often `OwaspZapDispatcher`'s sweep loop checks every worker's `last_heartbeat` against the timeout above. |
| `ZAP_QUEUE_POLL_INTERVAL_SECONDS` | How often the dispatcher polls the Operations table for `QUEUED` rows and tries to assign them. |

Tuning guidance: `ZAP_WORKER_HEARTBEAT_TIMEOUT_SECONDS` should be comfortably larger than the worker-side `ZAP_WORKER_HEARTBEAT_INTERVAL_SECONDS` (below) — at least 2-3x — so a couple of missed heartbeats from transient network jitter don't falsely reap a healthy worker mid-scan.

## Worker-side (`zap` service / container only)

Read by `docker/owasp_zap/register-worker.sh`, **not** by the mcp-server app — these have no effect if set on the `mcp-server` service.

| Variable | Controls |
|---|---|
| `MCP_SERVER_INTERNAL_URL` | Where the worker sends `/workers/register` and `/workers/heartbeat`. |
| `ZAP_API_PORT` | The port ZAP itself listens on; also used to build the worker's own `endpoint`. |
| `ZAP_WORKER_HEARTBEAT_INTERVAL_SECONDS` | How often the worker sends a heartbeat. |
| `ZAP_READY_STABLE_SUCCESS_COUNT` | Consecutive local health-check successes required before the worker registers at all — avoids registering a ZAP process that's still booting. |

## Scaling

```bash
docker compose --profile zap up --scale zap=5
```

No `.env` change required. Each of the 5 replicas runs the same image, reads its own `HOSTNAME`, and registers independently. Scaling back down (`--scale zap=2`) leaves the removed replicas' registrations to be cleaned up either gracefully (the container's `SIGTERM` triggers a `DELETE /workers/{id}` call) or, failing that, via the heartbeat-timeout sweep.
