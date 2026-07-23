"""Process-group execution tests — the INV8 guarantee (no orphaned children).

These use synthetic ``bash`` commands (no JMeter) to prove the hard property:
when a run is timed out or cancelled, the *entire* process group dies, including
grandchildren the engine spawned — never just the parent.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event, Timer

from app.integrations.jmeter.process_group import (
    ProcessTermination,
    run_in_process_group,
)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - exists but not ours
        return True


class ProcessGroupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.out = self.dir / "out.log"
        self.err = self.dir / "err.log"

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, command, *, timeout=None, cancel=None):
        return run_in_process_group(
            command,
            timeout_seconds=timeout,
            cancel=cancel or Event(),
            stdout_path=self.out,
            stderr_path=self.err,
            grace_seconds=1.0,
            poll_seconds=0.02,
        )

    def test_finished_reports_exit_code(self):
        outcome = self._run(["bash", "-c", "exit 3"])
        self.assertEqual(outcome.termination, ProcessTermination.FINISHED)
        self.assertEqual(outcome.exit_code, 3)

    def test_timeout_kills_entire_group_including_child(self):
        pidfile = self.dir / "child.pid"
        # Background a long sleep (the "grandchild"), record its pid, then wait.
        cmd = ["bash", "-c", f"sleep 30 & echo $! > {pidfile}; wait"]
        outcome = self._run(cmd, timeout=0.5)
        self.assertEqual(outcome.termination, ProcessTermination.TIMED_OUT)

        child_pid = int(pidfile.read_text().strip())
        # The backgrounded child must have been group-killed — no orphan.
        deadline = time.monotonic() + 3.0
        while _pid_alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(_pid_alive(child_pid), "orphaned child survived group kill")

    def test_cancellation_kills_entire_group(self):
        pidfile = self.dir / "child.pid"
        cmd = ["bash", "-c", f"sleep 30 & echo $! > {pidfile}; wait"]
        cancel = Event()
        Timer(0.4, cancel.set).start()  # cancel shortly after start
        outcome = self._run(cmd, cancel=cancel)
        self.assertEqual(outcome.termination, ProcessTermination.CANCELLED)

        child_pid = int(pidfile.read_text().strip())
        deadline = time.monotonic() + 3.0
        while _pid_alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(_pid_alive(child_pid), "orphaned child survived cancellation")

    def test_missing_binary_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self._run(["definitely-not-a-real-binary-xyz"])


if __name__ == "__main__":
    unittest.main()
