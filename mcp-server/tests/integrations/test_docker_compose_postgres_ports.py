import json
import os
import subprocess
import unittest
from pathlib import Path


MCP_SERVER_ROOT = Path(__file__).resolve().parents[2]


class DockerComposePostgresPortTests(unittest.TestCase):
    def test_postgres_port_defaults_to_5432_everywhere(self) -> None:
        env = os.environ.copy()
        env["POSTGRES_PORT"] = ""

        result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=MCP_SERVER_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        config = json.loads(result.stdout)

        postgres_port = config["services"]["postgres"]["ports"][0]
        self.assertEqual(str(postgres_port["published"]), "5432")
        self.assertEqual(str(postgres_port["target"]), "5432")
        self.assertEqual(
            config["services"]["postgres"]["command"],
            ["postgres", "-p", "5432"],
        )

        mcp_environment = config["services"]["mcp-server"]["environment"]
        self.assertEqual(str(mcp_environment["POSTGRES_PORT"]), "5432")

    def test_postgres_port_is_shared_by_host_and_compose_services(self) -> None:
        env = os.environ.copy()
        env["POSTGRES_PORT"] = "6543"
        env.pop("POSTGRES_HOST_PORT", None)

        result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=MCP_SERVER_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        config = json.loads(result.stdout)

        postgres_port = config["services"]["postgres"]["ports"][0]
        self.assertEqual(str(postgres_port["published"]), "6543")
        self.assertEqual(str(postgres_port["target"]), "6543")
        self.assertEqual(
            config["services"]["postgres"]["command"],
            ["postgres", "-p", "6543"],
        )

        mcp_environment = config["services"]["mcp-server"]["environment"]
        self.assertEqual(mcp_environment["POSTGRES_HOST"], "postgres")
        self.assertEqual(str(mcp_environment["POSTGRES_PORT"]), "6543")
        self.assertEqual(mcp_environment["DATABASE_URL"], "")


if __name__ == "__main__":
    unittest.main()
