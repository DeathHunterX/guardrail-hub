"""Installation smoke test for the Guardrail Hub console entrypoint."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


class ConsoleEntrypointTests(unittest.TestCase):
    """The installed project exposes a runnable ``guardrail-hub`` command."""

    def test_installed_console_entrypoint_resolves_and_shows_help(self):
        executable_name = "guardrail-hub.exe" if os.name == "nt" else "guardrail-hub"
        executable = Path(sys.executable).resolve().parent / executable_name

        completed = subprocess.run(
            [str(executable), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Guardrail Hub operator CLI.", completed.stdout)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
