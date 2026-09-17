"""Deployment checks for shell scripts copied into Linux containers."""

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class ContainerShellScriptTests(unittest.TestCase):
    def test_docker_shell_scripts_use_unix_line_endings(self):
        """A CRLF shebang makes Linux look for a non-existent ``bash\r``."""
        scripts = sorted((REPOSITORY_ROOT / "docker").rglob("*.sh"))

        self.assertTrue(scripts, "expected Docker shell scripts to be present")
        files_with_crlf = [
            str(script.relative_to(REPOSITORY_ROOT))
            for script in scripts
            if b"\r\n" in script.read_bytes()
        ]

        self.assertEqual([], files_with_crlf)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
