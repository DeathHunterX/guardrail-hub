# JMeter — Performance Engine images

Two distinct images live here. They are **not** interchangeable.

| Image | Dockerfile | Nature | Entrypoint |
|-------|-----------|--------|------------|
| JMeter CLI | `Dockerfile` | One-shot: runs one plan to completion and exits | `jmeter` |
| Warm worker | `worker.Dockerfile` | Long-lived pull-model worker (ADR-0010 §4.2) | `python3 -m app.workers.performance_worker` |

The **CLI image** is infrastructure for ad-hoc runs; it has no knowledge of the
mcp-server. The **warm worker** is the deployment target for the Performance
capability: a Python process that registers, heartbeats, pulls one assignment at
a time, runs a short-lived `jmeter -n` subprocess per job, and reports the
result back over HTTP.

## Warm worker

### What it is

`worker.Dockerfile` bundles the pinned JMeter CLI (the engine the runner invokes)
and the mcp-server Python app (the worker loop + its composition root). The
container entrypoint is `app/workers/performance_worker.py`, which reads its
configuration from the environment, assembles the worker graph
(`HttpServerClient` + `HttpReportSender` → `ReportChannelPersistence` +
`JmxPlanValidator` + `JMeterRunner` + `WorkspaceManager` → `PerformanceRuntime` →
`PerformanceWorker`), and runs the loop until it receives `SIGTERM`. It runs as
the non-root `jmeter` user (uid/gid 1000) and writes only under its workspace
root, which the Runtime creates and destroys per operation (INV2/INV5).

### Configuration (environment)

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_SERVER_INTERNAL_URL` | `http://mcp-server:8787` | Base URL of the server the worker calls |
| `PERFORMANCE_WORKER_TOKEN` | *(unset)* | Bearer token sent on every worker call (must match the server's `PERFORMANCE_WORKER_TOKEN`) |
| `PERFORMANCE_WORKER_ID` | `HOSTNAME` | Stable worker id; defaults to the container hostname |
| `PERFORMANCE_WORKER_VERSION` | *(unset)* | Worker version, for the server's compatibility gate |
| `PERFORMANCE_WORKER_WORKSPACE_DIR` | `/jmeter/workspaces` | Root under which per-operation workspaces are created |
| `PERFORMANCE_WORKER_HEARTBEAT_INTERVAL_SECONDS` | `5` | Heartbeat cadence |
| `JMETER_BINARY` | `jmeter` | JMeter executable the runner invokes |

No worker name, prefix, or index is configured anywhere: each replica reads its
own `HOSTNAME` and self-registers, so the pool grows and shrinks at runtime with
no server change.

### Build & run

```bash
# From mcp-server/ — build the worker image
docker build -f docker/jmeter/worker.Dockerfile -t guardrail-jmeter-worker:local .

# Or via compose (the jmeter-worker profile), scaled to N warm workers
docker compose --profile jmeter-worker up --build --scale jmeter-worker=3
```

The `jmeter-worker` compose service is warm (`restart: unless-stopped`), has no
fixed `container_name` (so `--scale` works), and joins both `app-network` (to
reach the server) and `shared-network` (to reach load-test targets).

### Verify

1. Bring up the server (with a database profile) and one worker:
   ```bash
   docker compose --profile local-db --profile jmeter-worker up --build
   ```
2. The worker logs `Worker '<hostname>' registered; entering heartbeat loop`.
3. Generate a plan, then execute it:
   - call the `generate_performance_plan` MCP tool with a `.jmx` plan → returns `plan_id`;
   - call `execute_performance_test` with that `plan_id` → returns `operation_id`.
4. The dispatcher assigns the operation; the worker pulls it, runs `jmeter -n`,
   and reports. Poll the operation for the completed report.

### Note on building in CI/sandbox

The build downloads JMeter from Apache mirrors and provisions Python
dependencies, so it requires a Docker daemon and network egress. The project's
automated gates therefore **statically** validate this Dockerfile and the compose
service (structure, non-root user, entrypoint, pinned version) rather than
performing a live `docker build`; the image build itself is a documented step for
a Docker host, as with the Phase-0 infrastructure.
