"""C3.7 — Performance worker composition-root smoke test (ADR-0010 §4.2).

Asserts the worker process's composition root assembles the full graph from env
config and injects every collaborator into the frozen subsystem objects — no
subsystem object builds its own infrastructure, and no network is touched at
build time.
"""

import ast
import unittest
from pathlib import Path

from app.integrations.jmeter.jmeter_runner import JMeterRunner
from app.integrations.jmeter.plan_validator import JmxPlanValidator
from app.integrations.performance.report_sender import HttpReportSender
from app.integrations.performance.server_client import HttpServerClient
from app.services.performance.persistence import ReportChannelPersistence
from app.services.performance.runtime import PerformanceRuntime, WorkspaceManager
from app.services.performance.worker.performance_worker import PerformanceWorker
from app.workers.performance_worker import WorkerConfig, build_performance_worker

_ENV = {
    "HOSTNAME": "perf-worker-7",
    "MCP_SERVER_INTERNAL_URL": "http://mcp-server:8787/",  # trailing slash on purpose
    "PERFORMANCE_WORKER_TOKEN": "s3cret",
    "PERFORMANCE_WORKER_WORKSPACE_DIR": "/jmeter/workspaces",
    "PERFORMANCE_WORKER_HEARTBEAT_INTERVAL_SECONDS": "3",
}


class WorkerConfigTests(unittest.TestCase):
    def test_reads_config_from_env_with_defaults(self):
        cfg = WorkerConfig.from_env(_ENV)
        self.assertEqual(cfg.server_base_url, "http://mcp-server:8787/")
        self.assertEqual(cfg.auth_token, "s3cret")
        self.assertEqual(cfg.worker_id, "perf-worker-7")  # defaults to HOSTNAME
        self.assertEqual(cfg.hostname, "perf-worker-7")
        self.assertEqual(cfg.heartbeat_interval_seconds, 3.0)
        self.assertEqual(cfg.workspace_dir, "/jmeter/workspaces")

    def test_worker_id_override_beats_hostname(self):
        cfg = WorkerConfig.from_env({**_ENV, "PERFORMANCE_WORKER_ID": "fixed-id"})
        self.assertEqual(cfg.worker_id, "fixed-id")


class WorkerCompositionTests(unittest.TestCase):
    def setUp(self):
        self.worker = build_performance_worker(WorkerConfig.from_env(_ENV))

    def test_full_graph_is_assembled_with_injected_collaborators(self):
        w = self.worker
        self.assertIsInstance(w, PerformanceWorker)
        # Outbound server client (register/heartbeat/pull), base normalized.
        self.assertIsInstance(w._server, HttpServerClient)
        self.assertEqual(w._server._base, "http://mcp-server:8787")
        # Runtime and its injected collaborators.
        self.assertIsInstance(w._runtime, PerformanceRuntime)
        self.assertIsInstance(w._runtime._runner, JMeterRunner)
        self.assertIsInstance(w._runtime._validator, JmxPlanValidator)
        self.assertIsInstance(w._runtime._workspaces, WorkspaceManager)
        self.assertIsInstance(w._runtime._persistence, ReportChannelPersistence)
        self.assertIsInstance(w._runtime._persistence._sender, HttpReportSender)

    def test_token_and_report_url_propagate(self):
        w = self.worker
        self.assertEqual(w._server._auth_token, "s3cret")
        sender = w._runtime._persistence._sender
        self.assertEqual(sender._auth_token, "s3cret")
        self.assertEqual(sender._url, "http://mcp-server:8787/performance/operations/report")

    def test_worker_identity_and_cadence(self):
        self.assertEqual(self.worker._worker_id, "perf-worker-7")
        self.assertEqual(self.worker._interval, 3.0)


class CompositionRootPurityTests(unittest.TestCase):
    """The worker composition is a composition root: subsystem worker objects
    must not construct infrastructure themselves."""

    def test_performance_worker_object_constructs_no_http_client(self):
        # The subsystem PerformanceWorker receives its server/runtime; it must not
        # build an HttpServerClient / HttpReportSender itself.
        src = Path("app/services/performance/worker/performance_worker.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        constructed = {
            n.func.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        for infra in ("HttpServerClient", "HttpReportSender", "JMeterRunner", "WorkspaceManager"):
            self.assertNotIn(infra, constructed)


if __name__ == "__main__":
    unittest.main()
