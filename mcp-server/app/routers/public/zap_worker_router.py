"""
ZAP worker registration / heartbeat / maintenance endpoints.

Not an MCP tool — these are called by ZAP worker containers themselves (see
``docker/owasp_zap/register-worker.sh``), not by an LLM client, so they are
mounted directly on the app (like ``health_router``) rather than through
``tools_router`` / ``MCP_OPERATIONS``.

    Worker Start -> Read HOSTNAME -> Build Endpoint -> POST /workers/register
    ... every N seconds ...        -> POST /workers/heartbeat

This router is a thin HTTP adapter: all worker-lifecycle logic (including
failing an operation orphaned by a removed worker) lives in
:class:`app.services.tools.owasp_zap.worker_service.ZapWorkerService`, which
owns the Worker Registry and the Operations DAO. The router only maps
requests/responses and translates domain errors to HTTP status codes — it
never touches the registry or the DAO directly.
"""

from fastapi import APIRouter, HTTPException

from app.integrations.owasp_zap.registry import WorkerNotRegisteredError
from app.schemas.tools.owasp_zap.worker import (
    ZapWorkerHeartbeatRequest,
    ZapWorkerHeartbeatResponse,
    ZapWorkerInfo,
    ZapWorkerRegisterRequest,
    ZapWorkerRegisterResponse,
)
from app.services.tools.owasp_zap.worker_service import ZapWorkerService

zap_worker_router = APIRouter(prefix="/workers", tags=["OWASP ZAP Workers"])
_service = ZapWorkerService()


@zap_worker_router.post("/register", response_model=ZapWorkerRegisterResponse)
def register_worker(request: ZapWorkerRegisterRequest) -> ZapWorkerRegisterResponse:
    """Register a ZAP worker (called once by the worker at startup, safe to repeat)."""
    info = _service.register(
        worker_id=request.worker_id,
        hostname=request.hostname,
        endpoint=request.endpoint,
        port=request.port,
        version=request.version,
    )
    return ZapWorkerRegisterResponse(
        worker_id=info.worker_id,
        hostname=info.hostname,
        endpoint=info.endpoint,
        state=info.state,
        registered_at=info.registered_at,
    )


@zap_worker_router.post("/heartbeat", response_model=ZapWorkerHeartbeatResponse)
def worker_heartbeat(request: ZapWorkerHeartbeatRequest) -> ZapWorkerHeartbeatResponse:
    """Record a heartbeat for a previously-registered worker.

    Returns 404 when ``worker_id`` isn't known (never registered, was removed,
    or was reaped for a heartbeat timeout and hasn't self-healed yet) — the
    worker's heartbeat loop should treat that as a signal to call
    ``/workers/register`` again.
    """
    try:
        info = _service.heartbeat(request.worker_id)
    except WorkerNotRegisteredError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Worker '{request.worker_id}' is not registered — call /workers/register again.",
        ) from exc

    return ZapWorkerHeartbeatResponse(
        worker_id=info.worker_id, state=info.state, last_heartbeat=info.last_heartbeat
    )


@zap_worker_router.get("", response_model=list[ZapWorkerInfo])
def list_workers() -> list[ZapWorkerInfo]:
    """List every registered worker (observability / debugging only)."""
    return _service.list_workers()


@zap_worker_router.post("/{worker_id}/drain", response_model=ZapWorkerInfo)
def drain_worker(worker_id: str) -> ZapWorkerInfo:
    """Begin graceful maintenance: Active -> Draining.

    A Draining worker finishes its current operation (if any) but receives no
    new ones, then automatically becomes Offline once released.
    """
    try:
        return _service.drain(worker_id)
    except WorkerNotRegisteredError as exc:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not found") from exc


@zap_worker_router.delete("/{worker_id}")
def remove_worker(worker_id: str) -> dict:
    """Hard-remove a worker from the registry (manual / scale-down cleanup).

    Unlike the heartbeat-timeout path this is immediate — intended for a
    deliberate ``docker compose down``/scale-down rather than a crash. If the
    worker was executing an operation, that operation is marked FAILED (same
    "no automatic retry" rule as the heartbeat-timeout path) — a worker
    removed from the registry can never be assigned to again, so leaving the
    operation RUNNING would strand it forever.
    """
    orphaned_op_id = _service.remove(worker_id)
    return {"worker_id": worker_id, "removed": True, "orphaned_operation_id": orphaned_op_id}
