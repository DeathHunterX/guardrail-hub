# Sequence Diagrams

## Worker registration + heartbeat

```mermaid
sequenceDiagram
    participant Worker as ZAP worker container
    participant Entrypoint as entrypoint.sh
    participant Register as register-worker.sh
    participant Router as zap_worker_router
    participant Registry as OwaspZapWorkerRegistry

    Entrypoint->>Worker: start zap.sh (background)
    Entrypoint->>Register: start register-worker.sh (background)
    Register->>Register: poll local ZAP API until stably healthy<br/>(ZAP_READY_STABLE_SUCCESS_COUNT consecutive checks)
    Register->>Router: POST /workers/register<br/>{worker_id: HOSTNAME, hostname, endpoint, port}
    Router->>Registry: register(...)
    Registry-->>Router: ZapWorkerInfo (state=ACTIVE)
    Router-->>Register: 200 OK

    loop every ZAP_WORKER_HEARTBEAT_INTERVAL_SECONDS
        Register->>Router: POST /workers/heartbeat {worker_id}
        Router->>Registry: heartbeat(worker_id)
        alt worker_id known
            Registry-->>Router: 200 OK (last_heartbeat refreshed)
        else worker_id unknown (server restarted / reaped)
            Router-->>Register: 404
            Register->>Router: POST /workers/register (again)
        end
    end
```

## Scan request -> persisted queue -> dispatch -> execution

```mermaid
sequenceDiagram
    participant Client
    participant Router as owasp_zap_router
    participant Service as ZapApiScanService
    participant DAO as Operation DAO
    participant Dispatcher as OwaspZapDispatcher
    participant Pool as OwaspZapPoolManager
    participant Registry as OwaspZapWorkerRegistry
    participant Scheduler as RoundRobinScheduler
    participant ZapClient
    participant Zap as ZAP worker

    Client->>Router: POST /tools/zap/scan_api
    Router->>Service: init_api_scan(request)
    Service->>DAO: create_operation(status=QUEUED, metadata.request=full payload)
    Service-->>Router: {operation_id, status: queued}
    Router-->>Client: response (returns immediately — no worker wait)

    loop every ZAP_QUEUE_POLL_INTERVAL_SECONDS
        Dispatcher->>DAO: get_queued_operations() (oldest created_at first)
        alt a QUEUED row exists
            Dispatcher->>Pool: try_assign(operation_id)
            Pool->>Registry: list_all()
            Pool->>Scheduler: select(workers)
            alt an eligible (idle, Active) worker exists
                Scheduler-->>Pool: chosen worker
                Pool->>Registry: assign(worker_id, operation_id)
                Pool-->>Dispatcher: ZapWorkerInfo
                Dispatcher->>Service: run_assigned_scan(operation_id, request, worker)
                Service->>Pool: get_client(worker)
                Service->>ZapClient: drive scan
                ZapClient->>Zap: ZAP REST API calls
                Service->>DAO: update_operation_status(RUNNING -> COMPLETED/FAILED)
                Service->>Pool: release_worker(worker_id, operation_id)
            else no eligible worker
                Scheduler-->>Pool: None
                Note over Dispatcher,DAO: operation stays QUEUED, retried next tick
            end
        end
    end
```

## Heartbeat timeout -> worker offline -> operation failed

```mermaid
sequenceDiagram
    participant Dispatcher as OwaspZapDispatcher (sweep loop)
    participant Registry as OwaspZapWorkerRegistry
    participant DAO as Operation DAO

    loop every ZAP_WORKER_HEARTBEAT_SWEEP_INTERVAL_SECONDS
        Dispatcher->>Registry: sweep_expired(ZAP_WORKER_HEARTBEAT_TIMEOUT_SECONDS)
        Registry->>Registry: mark stale workers OFFLINE, clear op_id
        Registry-->>Dispatcher: [(worker_id, operation_id), ...] just-orphaned
        loop for each orphaned (worker_id, operation_id)
            Dispatcher->>DAO: update_operation_status(operation_id, status=FAILED, error=...)
        end
    end
    Note over Dispatcher,DAO: No automatic retry — resubmitting is a user decision.
```

## Server restart (why a QUEUED request is never lost)

```mermaid
sequenceDiagram
    participant OS as Docker / orchestrator
    participant Server as mcp-server process
    participant DB as Postgres / DynamoDB
    participant Worker as ZAP worker

    OS->>Server: restart
    Note over Server: In-memory Worker Registry is empty again
    Server->>Server: run_startup_sequence()<br/>Database Ready -> Run Migrations -> Verify tables -> Init services
    Note over DB: QUEUED rows from before the restart still exist
    Server->>DB: dispatcher polls get_queued_operations() as usual
    Worker->>Server: next heartbeat (or fresh registration if it also restarted)
    Server->>Server: worker reappears in Registry, resumes taking assignments
    Note over Server,DB: A row still QUEUED before the restart is simply picked up<br/>once a worker is registered again — that request was never lost.
```

**Known gap:** this covers `QUEUED` rows, not a row that was `RUNNING` at the exact moment the *mcp-server process itself* crashed (as opposed to the worker crashing, which the heartbeat-timeout sweep above does catch). In that specific case the in-memory Registry — including which worker held that `op_id` — is gone, the worker re-registers as freshly idle, and the operation is left `RUNNING` with nothing pointing at it, because the Dispatcher only re-polls `QUEUED` rows. It is not silently retried or duplicated, but it also isn't automatically marked `FAILED` — it would need to be surfaced and resolved manually (e.g. via `/tools/history/*`) until a "reconcile stale RUNNING rows on startup" step is added. This is a deliberate scope boundary for this refactor, not an oversight: closing it fully means deciding what "stale" means for a `RUNNING` row across a restart, which is a policy question, not just a mechanical one.
