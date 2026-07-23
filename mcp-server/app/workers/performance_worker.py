"""Composition root + entrypoint for a Performance (JMeter) warm worker container.

This is the worker analogue of the server's ``app/main.py`` + ``app/bootstrap.py``:
a standalone process's composition root. It is the **only** place the worker's
concrete collaborators are constructed, and it assembles them into the frozen
subsystem objects by injection (ADR-0010 §4.2/§4.4):

    HttpServerClient ─┐
                      ├─► PerformanceWorker(server, runtime, …)
    HttpReportSender ─► ReportChannelPersistence ─┐
    JmxPlanValidator ─────────────────────────────┤
    JMeterRunner ──────────────────────────────────┼─► PerformanceRuntime
    WorkspaceManager ──────────────────────────────┘

No subsystem object builds its own infrastructure: the Runtime, the Worker, the
Runner, the persistence adapter, and the HTTP clients all receive their
collaborators here. The worker only ever makes outbound calls (register /
heartbeat / pull / report) — there is no inbound channel — and runs one short
``jmeter -n`` subprocess per assignment inside a workspace the Runtime owns and
destroys.

Configuration is read from the process environment (the worker's own config
surface — deliberately not the server's ``Settings``), so a container is
configured entirely through env vars, and ``docker compose up --scale
jmeter-worker=N`` grows the pool with no server change: each replica reads its
own ``HOSTNAME`` and self-registers.
"""

from __future__ import annotations

import os
import signal
import socket
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Optional

from app.core.mcp_logger import MCPLogger
from app.integrations.jmeter.jmeter_runner import JMeterRunner
from app.integrations.jmeter.plan_validator import JmxPlanValidator
from app.integrations.performance.report_sender import HttpReportSender
from app.integrations.performance.server_client import HttpServerClient
from app.services.performance.persistence import ReportChannelPersistence
from app.services.performance.runtime import PerformanceRuntime, WorkspaceManager
from app.services.performance.worker.performance_worker import PerformanceWorker

# Worker-router paths (the server side these clients talk to). The register /
# heartbeat / pull paths are baked into HttpServerClient; only the report path is
# passed as a full URL, so it is spelled once here.
_REPORT_PATH = "/performance/operations/report"


@dataclass(frozen=True)
class WorkerConfig:
    """Everything a worker container needs, read once from the environment."""

    server_base_url: str
    auth_token: Optional[str]
    worker_id: str
    hostname: str
    version: Optional[str]
    workspace_dir: str
    jmeter_binary: str
    heartbeat_interval_seconds: float
    http_timeout_seconds: float

    @staticmethod
    def from_env(environ: Optional[dict] = None) -> "WorkerConfig":
        env = os.environ if environ is None else environ
        hostname = env.get("HOSTNAME") or socket.gethostname()
        return WorkerConfig(
            server_base_url=env.get("MCP_SERVER_INTERNAL_URL", "http://mcp-server:8787"),
            auth_token=env.get("PERFORMANCE_WORKER_TOKEN") or None,
            worker_id=env.get("PERFORMANCE_WORKER_ID") or hostname,
            hostname=hostname,
            version=env.get("PERFORMANCE_WORKER_VERSION") or None,
            workspace_dir=env.get("PERFORMANCE_WORKER_WORKSPACE_DIR", "/jmeter/workspaces"),
            jmeter_binary=env.get("JMETER_BINARY", "jmeter"),
            heartbeat_interval_seconds=float(
                env.get("PERFORMANCE_WORKER_HEARTBEAT_INTERVAL_SECONDS", "5")
            ),
            http_timeout_seconds=float(env.get("PERFORMANCE_WORKER_HTTP_TIMEOUT_SECONDS", "30")),
        )


def build_performance_worker(config: WorkerConfig) -> PerformanceWorker:
    """Assemble the full worker graph from *config* and return the worker.

    The single construction site for the worker process: it builds the HTTP
    clients, the JMeter runner/validator, the workspace manager, the persistence
    adapter, and the Runtime, then injects them into the Worker. Every subsystem
    object receives its collaborators here (Gates C/D/E for the worker process).
    """
    base = config.server_base_url.rstrip("/")

    server = HttpServerClient(
        base,
        auth_token=config.auth_token,
        timeout_seconds=config.http_timeout_seconds,
    )
    report_sender = HttpReportSender(
        base + _REPORT_PATH,
        auth_token=config.auth_token,
        timeout_seconds=config.http_timeout_seconds,
    )
    persistence = ReportChannelPersistence(report_sender)

    runtime = PerformanceRuntime(
        workspaces=WorkspaceManager(Path(config.workspace_dir)),
        validator=JmxPlanValidator(),
        runner=JMeterRunner(config.jmeter_binary),
        persistence=persistence,
    )

    return PerformanceWorker(
        server=server,
        runtime=runtime,
        worker_id=config.worker_id,
        hostname=config.hostname,
        version=config.version,
        heartbeat_interval_seconds=config.heartbeat_interval_seconds,
    )


def main() -> None:
    """Container entrypoint: build the worker and run its loop until signalled."""
    logger = MCPLogger("performance-worker")
    config = WorkerConfig.from_env()
    worker = build_performance_worker(config)

    stop = Event()

    def _handle_signal(_signum, _frame):
        logger.info("Received termination signal — stopping worker loop")
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        "Starting Performance worker '%s' -> %s (heartbeat=%ss)",
        config.worker_id,
        config.server_base_url,
        config.heartbeat_interval_seconds,
    )
    worker.run(stop)
    logger.info("Performance worker '%s' loop exited", config.worker_id)


if __name__ == "__main__":
    main()
