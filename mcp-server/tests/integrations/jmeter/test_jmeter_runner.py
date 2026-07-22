"""JMeter Runner tests — status mapping, artifact collection, resilience.

A **fake ``jmeter`` binary** (a bash script) stands in for the real engine so the
Runner's behaviour is tested without installing JMeter: the fake parses the
``-l`` / ``-j`` / ``-o`` flags the Runner builds, produces the corresponding
output files, and exits with a chosen code (or sleeps, to force timeout).
"""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from threading import Event

from app.integrations.jmeter.jmeter_runner import JMeterRunner
from app.services.performance.engine import (
    ArtifactKind,
    ExecutionRequest,
    ExecutionStatus,
    PerformanceRunner,
)

# Fake engine: reads the flags the Runner passes, writes the outputs JMeter would,
# then exits EXIT (default 0). SLEEP>0 makes it hang so timeout/cancel can fire.
_FAKE_JMETER = """#!/usr/bin/env bash
L=""; J=""; O=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -l) shift; L="$1" ;;
    -j) shift; J="$1" ;;
    -o) shift; O="$1" ;;
  esac
  shift
done
if [[ "${SLEEP:-0}" != "0" ]]; then sleep "${SLEEP}"; fi
[[ -n "$L" ]] && echo "sample results" > "$L"
[[ -n "$J" ]] && echo "engine log" > "$J"
[[ -n "$O" ]] && mkdir -p "$O" && echo "<html></html>" > "$O/index.html"
exit "${EXIT:-0}"
"""


class JMeterRunnerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.output = self.dir / "output"
        self.output.mkdir()
        self.plan = self.dir / "plan"
        self.plan.write_text("<jmeterTestPlan/>")
        self._orig_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)
        self._tmp.cleanup()

    def _fake_binary(self) -> str:
        path = self.dir / "fake-jmeter"
        path.write_text(_FAKE_JMETER)
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return str(path)

    def _request(self, timeout=None) -> ExecutionRequest:
        return ExecutionRequest(
            operation_id="op-1",
            plan_path=self.plan,
            output_dir=self.output,
            timeout_seconds=timeout,
        )

    def test_runner_satisfies_protocol(self):
        self.assertIsInstance(JMeterRunner(), PerformanceRunner)

    def test_successful_run_completes_and_collects_artifacts(self):
        os.environ["EXIT"] = "0"
        runner = JMeterRunner(binary=self._fake_binary())
        result = runner.run(self._request(), Event())

        self.assertEqual(result.status, ExecutionStatus.COMPLETED)
        self.assertEqual(result.exit_code, 0)
        kinds = {a.kind for a in result.artifacts.artifacts}
        self.assertIn(ArtifactKind.RESULTS, kinds)
        self.assertIn(ArtifactKind.REPORT, kinds)
        self.assertIn(ArtifactKind.LOG, kinds)
        # REPORT points at the generated dashboard index.
        report = result.artifacts.of_kind(ArtifactKind.REPORT)[0]
        self.assertEqual(report.path.name, "index.html")

    def test_nonzero_exit_is_failed_not_raised(self):
        os.environ["EXIT"] = "2"
        runner = JMeterRunner(binary=self._fake_binary())
        result = runner.run(self._request(), Event())
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertEqual(result.exit_code, 2)
        self.assertIn("2", result.error)

    def test_timeout_maps_to_timed_out(self):
        os.environ["SLEEP"] = "30"
        runner = JMeterRunner(binary=self._fake_binary(), grace_seconds=1.0, poll_seconds=0.02)
        result = runner.run(self._request(timeout=0.5), Event())
        self.assertEqual(result.status, ExecutionStatus.TIMED_OUT)

    def test_cancellation_maps_to_cancelled(self):
        os.environ["SLEEP"] = "30"
        runner = JMeterRunner(binary=self._fake_binary(), grace_seconds=1.0, poll_seconds=0.02)
        cancel = Event()
        cancel.set()  # already-requested cancel: killed on the first poll
        result = runner.run(self._request(), cancel)
        self.assertEqual(result.status, ExecutionStatus.CANCELLED)

    def test_missing_binary_is_failed_result_not_crash(self):
        runner = JMeterRunner(binary="definitely-not-a-real-binary-xyz")
        result = runner.run(self._request(), Event())
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIsNone(result.exit_code)
        self.assertIn("not found", result.error)

    def test_build_command_shape(self):
        runner = JMeterRunner(binary="jmeter")
        cmd = runner._build_command(
            Path("/w/plan"), Path("/w/out/results.jtl"), Path("/w/out/report"), Path("/w/out/jmeter.log")
        )
        self.assertEqual(cmd[0], "jmeter")
        self.assertIn("-n", cmd)
        self.assertEqual(cmd[cmd.index("-t") + 1], "/w/plan")
        self.assertEqual(cmd[cmd.index("-l") + 1], "/w/out/results.jtl")
        self.assertEqual(cmd[cmd.index("-o") + 1], "/w/out/report")


if __name__ == "__main__":
    unittest.main()
