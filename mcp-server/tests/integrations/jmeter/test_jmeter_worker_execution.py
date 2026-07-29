"""Worker execution: assignment reception, run lifecycle, timeout, cancellation.

The subprocess layer is exercised against real short-lived processes (``sleep``,
``true``, ``false``) rather than a mock, because the things worth testing here —
timeout escalation, process-group cleanup, exit codes — are precisely the parts
a mock would define away.
"""

import os
import shutil
import tempfile
import threading
import time
import unittest

from app.integrations.jmeter.process import JMeterProcessError, JMeterProcessRunner
from app.integrations.jmeter.worker import JMeterWorker
from app.schemas.tools.jmeter.run_jmeter_test import JMeterTestRequest
from app.schemas.tools.jmeter.worker_assignment import (
    JMeterAssignmentRequest,
    JMeterExecutionState,
)

_PLAN = "<jmeterTestPlan><hashTree/></jmeterTestPlan>"


def _assignment(operation_id="op-1", plan=_PLAN, **overrides):
    fields = {
        "target_url": "https://api.example.com/v1/orders",
        "thread_count": 5,
        "ramp_up_seconds": 1,
        "hold_seconds": 1,
    }
    fields.update(overrides)
    return JMeterAssignmentRequest(
        operation_id=operation_id,
        request=JMeterTestRequest(**fields),
        jmx_plan=plan,
    )


class _FakeRunner:
    """Records runs without touching the filesystem or a process."""

    def __init__(self, outcome=None, raises=None, block: threading.Event = None):
        self.calls = []
        self._outcome = outcome
        self._raises = raises
        self._block = block

    def run(self, operation_id, workspace, jmx_xml, timeout_seconds):
        self.calls.append(
            {
                "operation_id": operation_id,
                "workspace": workspace,
                "jmx_xml": jmx_xml,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self._block is not None:
            self._block.wait(timeout=5)
        if self._raises is not None:
            raise self._raises
        from app.integrations.jmeter.process import JMeterRunOutcome  # noqa: PLC0415

        return self._outcome or JMeterRunOutcome(
            exit_code=0, timed_out=False, cancelled=False, workspace=workspace
        )

    def cancel(self, operation_id):
        return True


def _await_state(worker, operation_id, state, timeout=5.0):
    """Wait for the worker's background run to reach *state*."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        report = worker.report_for(operation_id)
        if report is not None and report.state == state:
            return report
        time.sleep(0.01)
    raise AssertionError(
        f"never reached {state}; last was {worker.report_for(operation_id)}"
    )


class AssignmentReceptionTests(unittest.TestCase):
    def test_an_assignment_is_accepted_and_run_in_the_background(self):
        runner = _FakeRunner()
        worker = JMeterWorker("jmeter-1", "/tmp/ws", runner=runner)

        ack = worker.accept(_assignment())

        self.assertTrue(ack.accepted)
        self.assertEqual("jmeter-1", ack.worker_id)
        _await_state(worker, "op-1", JMeterExecutionState.SUCCEEDED)
        self.assertEqual(_PLAN, runner.calls[0]["jmx_xml"])

    def test_the_workspace_is_scoped_to_the_operation(self):
        runner = _FakeRunner()
        worker = JMeterWorker("jmeter-1", "/tmp/ws", runner=runner)
        worker.accept(_assignment(operation_id="op-42"))
        _await_state(worker, "op-42", JMeterExecutionState.SUCCEEDED)

        self.assertEqual("/tmp/ws/op-42", runner.calls[0]["workspace"])

    def test_a_busy_worker_declines_rather_than_failing(self):
        gate = threading.Event()
        worker = JMeterWorker("jmeter-1", "/tmp/ws", runner=_FakeRunner(block=gate))
        try:
            self.assertTrue(worker.accept(_assignment("op-1")).accepted)
            _await_state(worker, "op-1", JMeterExecutionState.RUNNING)

            ack = worker.accept(_assignment("op-2"))
            # Declining is a normal answer: the operation goes back on the queue.
            self.assertFalse(ack.accepted)
            self.assertIn("already running", ack.message)
        finally:
            gate.set()

    def test_an_assignment_without_a_plan_is_declined(self):
        worker = JMeterWorker("jmeter-1", "/tmp/ws", runner=_FakeRunner())
        ack = worker.accept(_assignment(plan=None))
        self.assertFalse(ack.accepted)

    def test_the_worker_frees_itself_after_a_run(self):
        worker = JMeterWorker("jmeter-1", "/tmp/ws", runner=_FakeRunner())
        worker.accept(_assignment("op-1"))
        _await_state(worker, "op-1", JMeterExecutionState.SUCCEEDED)

        self.assertTrue(worker.accept(_assignment("op-2")).accepted)

    def test_an_unknown_operation_has_no_report(self):
        worker = JMeterWorker("jmeter-1", "/tmp/ws", runner=_FakeRunner())
        self.assertIsNone(worker.report_for("never-seen"))

    def test_timeout_is_derived_from_the_declared_load_profile(self):
        runner = _FakeRunner()
        worker = JMeterWorker("jmeter-1", "/tmp/ws", runner=runner)
        worker.accept(_assignment(ramp_up_seconds=30, hold_seconds=300))
        _await_state(worker, "op-1", JMeterExecutionState.SUCCEEDED)

        # ramp_up + hold + headroom for JVM start and report generation.
        self.assertEqual(630.0, runner.calls[0]["timeout_seconds"])

    def test_timeout_is_clamped_to_the_configured_ceiling(self):
        runner = _FakeRunner()
        worker = JMeterWorker("jmeter-1", "/tmp/ws", runner=runner, max_run_seconds=60)
        worker.accept(_assignment(ramp_up_seconds=600, hold_seconds=3000))
        _await_state(worker, "op-1", JMeterExecutionState.SUCCEEDED)

        self.assertEqual(60.0, runner.calls[0]["timeout_seconds"])


class ExecutionOutcomeTests(unittest.TestCase):
    def _worker_with(self, **outcome_fields):
        from app.integrations.jmeter.process import JMeterRunOutcome  # noqa: PLC0415

        fields = {
            "exit_code": 0,
            "timed_out": False,
            "cancelled": False,
            "workspace": "/tmp/ws/op-1",
        }
        fields.update(outcome_fields)
        return JMeterWorker(
            "jmeter-1", "/tmp/ws", runner=_FakeRunner(outcome=JMeterRunOutcome(**fields))
        )

    def test_a_clean_run_reports_success_with_its_workspace(self):
        worker = self._worker_with()
        worker.accept(_assignment())
        report = _await_state(worker, "op-1", JMeterExecutionState.SUCCEEDED)
        self.assertEqual("/tmp/ws/op-1", report.workspace)

    def test_a_nonzero_exit_code_reports_failure(self):
        worker = self._worker_with(exit_code=2)
        worker.accept(_assignment())
        report = _await_state(worker, "op-1", JMeterExecutionState.FAILED)
        self.assertIn("code 2", report.message)

    def test_a_timeout_reports_failure_and_keeps_partial_results(self):
        worker = self._worker_with(timed_out=True, exit_code=-1)
        worker.accept(_assignment())
        report = _await_state(worker, "op-1", JMeterExecutionState.FAILED)
        self.assertIn("partial results were kept", report.message)

    def test_a_cancellation_reports_failure_and_keeps_partial_results(self):
        worker = self._worker_with(cancelled=True, exit_code=-1)
        worker.accept(_assignment())
        report = _await_state(worker, "op-1", JMeterExecutionState.FAILED)
        self.assertIn("cancelled", report.message)

    def test_a_runner_that_cannot_start_reports_failure(self):
        worker = JMeterWorker(
            "jmeter-1",
            "/tmp/ws",
            runner=_FakeRunner(raises=JMeterProcessError("jmeter not found")),
        )
        worker.accept(_assignment())
        report = _await_state(worker, "op-1", JMeterExecutionState.FAILED)
        self.assertIn("jmeter not found", report.message)

    def test_an_unexpected_worker_failure_is_still_reported(self):
        # A background thread dying silently would leave the Runtime polling a
        # state that never advances.
        worker = JMeterWorker(
            "jmeter-1", "/tmp/ws", runner=_FakeRunner(raises=ValueError("boom"))
        )
        worker.accept(_assignment())
        report = _await_state(worker, "op-1", JMeterExecutionState.FAILED)
        self.assertIn("boom", report.message)


class ProcessRunnerTests(unittest.TestCase):
    """Real subprocesses: the parts a mock would define away."""

    def setUp(self):
        self.workspace_root = tempfile.mkdtemp(prefix="jmeter-test-")

    def tearDown(self):
        shutil.rmtree(self.workspace_root, ignore_errors=True)

    def _workspace(self, name="op-1"):
        return os.path.join(self.workspace_root, name)

    def _long_running_binary(self) -> str:
        """A stand-in that ignores JMeter's argv and simply keeps running.

        ``sleep`` itself cannot be used: the runner passes JMeter's real flags,
        which ``sleep`` rejects, so the process would exit instantly and never
        exercise the timeout or cancellation paths at all.
        """
        path = os.path.join(self.workspace_root, "long-running")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\nsleep 30\n")
        os.chmod(path, 0o755)
        return path

    def test_the_plan_is_written_into_the_workspace(self):
        runner = JMeterProcessRunner(binary="true")
        outcome = runner.run("op-1", self._workspace(), _PLAN, timeout_seconds=10)

        written = os.path.join(outcome.workspace, JMeterProcessRunner.PLAN_FILE)
        self.assertTrue(os.path.exists(written))
        with open(written, encoding="utf-8") as handle:
            self.assertEqual(_PLAN, handle.read())

    def test_a_clean_exit_is_reported_as_success(self):
        outcome = JMeterProcessRunner(binary="true").run(
            "op-1", self._workspace(), _PLAN, timeout_seconds=10
        )
        self.assertTrue(outcome.succeeded)
        self.assertEqual(0, outcome.exit_code)

    def test_a_failing_process_is_not_success(self):
        outcome = JMeterProcessRunner(binary="false").run(
            "op-1", self._workspace(), _PLAN, timeout_seconds=10
        )
        self.assertFalse(outcome.succeeded)
        self.assertNotEqual(0, outcome.exit_code)

    def test_a_missing_binary_raises_rather_than_reporting_a_run(self):
        with self.assertRaises(JMeterProcessError):
            JMeterProcessRunner(binary="definitely-not-a-real-binary").run(
                "op-1", self._workspace(), _PLAN, timeout_seconds=10
            )

    def test_an_overrunning_process_times_out_and_is_stopped(self):
        runner = JMeterProcessRunner(
            binary=self._long_running_binary(), terminate_grace_seconds=1.0
        )
        started = time.monotonic()
        outcome = runner.run("op-1", self._workspace(), _PLAN, timeout_seconds=0.3)

        self.assertTrue(outcome.timed_out)
        self.assertFalse(outcome.succeeded)
        # Terminated, not waited out: the process would have run for 30s.
        self.assertLess(time.monotonic() - started, 10)

    def test_a_running_process_can_be_cancelled(self):
        runner = JMeterProcessRunner(
            binary=self._long_running_binary(), terminate_grace_seconds=1.0
        )
        outcomes = []

        thread = threading.Thread(
            target=lambda: outcomes.append(
                runner.run("op-1", self._workspace(), _PLAN, timeout_seconds=30)
            )
        )
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not runner.cancel("op-1"):
                if time.monotonic() > deadline:
                    self.fail("the run never became cancellable")
                time.sleep(0.02)
        finally:
            thread.join(timeout=10)

        self.assertEqual(1, len(outcomes))
        self.assertTrue(outcomes[0].cancelled)

    def test_cancelling_an_unknown_run_is_not_an_error(self):
        # Cancellation racing with completion is normal, not exceptional.
        self.assertFalse(JMeterProcessRunner().cancel("never-started"))

    def test_a_rerun_starts_from_a_clean_workspace(self):
        runner = JMeterProcessRunner(binary="true")
        workspace = self._workspace()
        runner.run("op-1", workspace, _PLAN, timeout_seconds=10)
        stale = os.path.join(workspace, "stale.txt")
        with open(stale, "w", encoding="utf-8") as handle:
            handle.write("leftover")

        runner.run("op-1", workspace, _PLAN, timeout_seconds=10)

        # JMeter refuses to write its dashboard into a non-empty directory.
        self.assertFalse(os.path.exists(stale))


if __name__ == "__main__":
    unittest.main()
