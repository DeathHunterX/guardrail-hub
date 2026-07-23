"""C3.7 — static deployment validation for the JMeter warm worker.

The sandbox cannot run a Docker daemon (no build; Apache mirrors blocked), so the
image build is a documented gate for a Docker host. These tests validate the
worker Dockerfile and compose service *statically*: structure, non-root user,
entrypoint, pinned+verified engine, and that the Phase-0 CLI service is untouched.
"""

import unittest
from pathlib import Path

import yaml

_COMPOSE = Path("docker-compose.yml")
_WORKER_DOCKERFILE = Path("docker/jmeter/worker.Dockerfile")
_CLI_DOCKERFILE = Path("docker/jmeter/Dockerfile")


class ComposeServiceTests(unittest.TestCase):
    def setUp(self):
        self.compose = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
        self.services = self.compose["services"]

    def test_jmeter_worker_service_is_defined_under_its_own_profile(self):
        self.assertIn("jmeter-worker", self.services)
        svc = self.services["jmeter-worker"]
        self.assertEqual(svc["profiles"], ["jmeter-worker"])
        self.assertEqual(svc["build"]["dockerfile"], "docker/jmeter/worker.Dockerfile")

    def test_worker_is_scalable_and_warm(self):
        svc = self.services["jmeter-worker"]
        # No fixed container_name -> `--scale jmeter-worker=N` works.
        self.assertNotIn("container_name", svc)
        # Warm/long-lived, like the zap worker.
        self.assertEqual(svc["restart"], "unless-stopped")

    def test_worker_env_and_networks(self):
        svc = self.services["jmeter-worker"]
        env = svc["environment"]
        for key in (
            "MCP_SERVER_INTERNAL_URL",
            "PERFORMANCE_WORKER_TOKEN",
            "PERFORMANCE_WORKER_HEARTBEAT_INTERVAL_SECONDS",
        ):
            self.assertIn(key, env)
        self.assertIn("app-network", svc["networks"])  # reach the server

    def test_phase0_cli_jmeter_service_is_untouched(self):
        cli = self.services["jmeter"]
        self.assertEqual(cli["build"]["dockerfile"], "docker/jmeter/Dockerfile")
        self.assertEqual(cli["command"][:2], ["-n", "-t"])  # still a CLI one-shot
        self.assertEqual(cli["profiles"], ["jmeter"])


class WorkerDockerfileTests(unittest.TestCase):
    def setUp(self):
        self.text = _WORKER_DOCKERFILE.read_text(encoding="utf-8")
        self.lines = [ln.strip() for ln in self.text.splitlines()]

    def test_runs_the_worker_composition_entrypoint(self):
        self.assertIn(
            'ENTRYPOINT ["python3", "-m", "app.workers.performance_worker"]', self.text
        )

    def test_runs_as_non_root_before_entrypoint(self):
        user_idx = next(i for i, ln in enumerate(self.lines) if ln == "USER jmeter")
        entry_idx = next(i for i, ln in enumerate(self.lines) if ln.startswith("ENTRYPOINT"))
        self.assertLess(user_idx, entry_idx, "must drop to non-root before the entrypoint")

    def test_jmeter_is_pinned_and_checksum_verified(self):
        self.assertIn("JMETER_VERSION=5.6.3", self.text)
        self.assertIn("sha512sum -c -", self.text)  # tarball verified before extract

    def test_bundles_python_app_for_the_loop(self):
        # The warm worker needs the app (worker loop) alongside the JMeter CLI.
        self.assertIn("COPY app ./app", self.text)
        self.assertIn("uv sync --frozen --no-dev", self.text)


if __name__ == "__main__":
    unittest.main()
