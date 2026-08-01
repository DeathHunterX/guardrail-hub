"""Entry point for a JMeter worker container.

**Why this file exists at all.** ZAP and JMeter differ in the tools themselves,
not in how we chose to build them: ZAP *is* a daemon, so its worker container
runs the vendor's own image and this repository contains no ZAP worker code
whatsoever. JMeter is a *command-line tool* — there is nothing to talk to — so
something on the worker host has to accept an assignment and own the `jmeter`
process. That something is this app.

**Why it lives here.** This is a **Runtime Boundary** — an independently
deployed execution process, governed by
[runtime-boundary](../../../../.ai/standards/architecture/runtime-boundary.md)
and justified by [Decision 0012](../../../../.ai/decisions/0012-runtime-boundary.md).
`app/runtime/` is deliberately *not* a backend layer: it sits outside
backend-layering R1's role set rather than being admitted to it, so R1's closed
whitelist is unchanged. A `workers/` role was rejected — "worker" already names
server-side things (`integrations/owasp_zap/` has a worker registry, pool and
scheduler), and the property that actually distinguishes this component is that
it is *separately deployed*, not that it is a worker.

The three assignment endpoints are defined inline rather than in `routers/`,
because `routers/` means "HTTP surface of the mcp-server" and these are served
by a different process entirely. They belong to this app and nowhere else.

**What this app deliberately cannot do.** No database, no dispatcher, no MCP
mount, no notification pipeline. It never writes operation state: the worker
reports what happened locally and `JMeterRuntime` — on the server — decides what
that means for the Operation
(`architecture/jmeter-engine/runtime-responsibility.md` §3). That holds at three
levels: RB3 forbids the imports and `aios arch` fails the build on them;
`docker/jmeter/Dockerfile` copies only the four trees this module imports, so
`app/dao/` and `app/services/` are not present in the worker image at all; and
`tests/integrations/jmeter/test_jmeter_worker_isolation.py` measures the real
transitive closure so the Dockerfile's copy list cannot silently drift.

Run by ``docker/jmeter/Dockerfile``::

    uvicorn app.runtime.jmeter.main:app --host 0.0.0.0 --port 8090

Registration and heartbeats are a sidecar script, mirroring how a ZAP worker
announces itself — see ``docker/jmeter/register-worker.sh``.
"""

import os

from fastapi import FastAPI, HTTPException

from app.core.config import settings
from app.core.mcp_logger import MCPLogger
from app.integrations.jmeter.process import JMeterProcessRunner
from app.integrations.jmeter.worker import JMeterWorker
from app.schemas.tools.jmeter.worker_assignment import (
    JMeterAssignmentAck,
    JMeterAssignmentRequest,
    JMeterExecutionStateReport,
)

logger = MCPLogger("JMeterWorkerAgent")


def build_worker() -> JMeterWorker:
    """Assemble this process's single worker from settings and the environment.

    ``worker_id`` comes from HOSTNAME — the same value the registration sidecar
    reports — so the id the server assigns work to and the id this process
    answers as cannot drift apart.
    """
    return JMeterWorker(
        worker_id=os.getenv("HOSTNAME", "jmeter-worker"),
        workspace_root=settings.jmeter_workspace_dir,
        runner=JMeterProcessRunner(
            binary=settings.jmeter_binary,
            terminate_grace_seconds=settings.jmeter_terminate_grace_seconds,
        ),
        max_run_seconds=settings.jmeter_max_run_seconds,
    )


app = FastAPI(
    title="Guardrail Hub — JMeter Worker Agent",
    description="Executes JMeter test plans assigned by the mcp-server.",
    version=settings.app_version,
)

worker = build_worker()


@app.get("/health/live")
def liveness() -> dict:
    """Liveness probe for the container healthcheck and the registration sidecar."""
    return {"status": "ok"}


@app.post("/assignments", response_model=JMeterAssignmentAck, tags=["Assignments"])
def accept_assignment(assignment: JMeterAssignmentRequest) -> JMeterAssignmentAck:
    """Take an assignment and start running it in the background.

    Returns as soon as the run has started, never when it finishes: a load test
    runs for minutes and the server's request must not be held open for it.
    A busy worker answers ``accepted=False``, which is a normal reply — the
    operation simply goes back on the queue.
    """
    return worker.accept(assignment)


@app.get(
    "/assignments/{operation_id}",
    response_model=JMeterExecutionStateReport,
    tags=["Assignments"],
)
def get_assignment_state(operation_id: str) -> JMeterExecutionStateReport:
    """Report where *operation_id*'s run is.

    404 when this worker has no record of it — it restarted, or never had it.
    The Runtime reads that as a state to handle, not a transport error.
    """
    report = worker.report_for(operation_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"This worker has no record of operation '{operation_id}'.",
        )
    return report


@app.delete("/assignments/{operation_id}", tags=["Assignments"])
def cancel_assignment(operation_id: str) -> dict:
    """Stop the run for *operation_id*.

    Cancelling something that already finished is not an error — that race is
    normal — so this reports what it found rather than failing.
    """
    return {"operation_id": operation_id, "cancelled": worker.cancel(operation_id)}
