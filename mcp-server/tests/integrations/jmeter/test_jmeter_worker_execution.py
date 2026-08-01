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

    def test_a_clean_exit_with_a_missing_artifact_reports_failure(self):
        # JMeter can exit 0 having written no dashboard. Reporting that as
        # success hands the Runtime a workspace whose files it will not find.
        worker = self._worker_with(missing_artifacts=("html-report/index.html",))
        worker.accept(_assignment())
        report = _await_state(worker, "op-1", JMeterExecutionState.FAILED)
        self.assertIn("html-report/index.html", report.message)

    def test_a_missing_artifact_is_named_rather_than_counted(self):
        worker = self._worker_with(
            missing_artifacts=("test-results.jtl", "html-report/index.html")
        )
        worker.accept(_assignment())
        report = _await_state(worker, "op-1", JMeterExecutionState.FAILED)
        self.assertIn("test-results.jtl", report.message)
        self.assertIn("html-report/index.html", report.message)

    def test_an_unexpected_worker_failure_is_still_reported(self):
        # A background thread dying silently would leave the Runtime polling a
        # state that never advances.
        worker = JMeterWorker(
            "jmeter-1", "/tmp/ws", runner=_FakeRunner(raises=ValueError("boom"))
        )
        worker.accept(_assignment())
        report = _await_state(worker, "op-1", JMeterExecutionState.FAILED)
        self.assertIn("boom", report.message)


class ExecutionContextLoggingTests(unittest.TestCase):
    """The pre-launch context line, and the one thing it must never contain.

    Guardrail G1 is asserted at the point of use rather than only on the helper:
    what matters is that the value the worker actually puts in a log line has
    been through the redaction, not that a redaction function exists.
    """

    class _CapturingLogger:
        def __init__(self):
            self.records = []

        def _record(self, msg, *args, extra=None, **kwargs):
            self.records.append((msg, extra or {}))

        info = warning = error = debug = critical = _record

    def _context_for(self, target_url):
        logger = self._CapturingLogger()
        worker = JMeterWorker(
            "jmeter-1", "/tmp/ws", runner=_FakeRunner(), logger=logger
        )
        worker.accept(_assignment(target_url=target_url))
        _await_state(worker, "op-1", JMeterExecutionState.SUCCEEDED)
        return next(
            extra
            for _, extra in logger.records
            if extra.get("event") == "jmeter_execution_start"
        )

    def test_the_context_carries_every_field_needed_to_identify_the_run(self):
        context = self._context_for("https://api.example.com/v1/orders")

        self.assertEqual("op-1", context["operation_id"])
        self.assertEqual("jmeter-1", context["worker_id"])
        self.assertEqual("/tmp/ws/op-1", context["workspace"])
        self.assertEqual("generated_jmx", context["execution_mode"])
        self.assertEqual(5, context["thread_count"])
        self.assertEqual(1, context["ramp_up_seconds"])
        self.assertEqual(1, context["hold_seconds"])

    def test_a_credential_in_the_target_url_is_never_logged(self):
        context = self._context_for("https://svc:s3cr3t@api.example.com/v1/orders")

        self.assertNotIn("s3cr3t", context["target_url"])
        self.assertNotIn("svc", context["target_url"])
        # Redacted, not discarded: the endpoint must still be identifiable.
        self.assertEqual("https://api.example.com/v1/orders", context["target_url"])

    def test_a_supplied_plan_is_reported_as_an_uploaded_execution(self):
        logger = self._CapturingLogger()
        worker = JMeterWorker(
            "jmeter-1", "/tmp/ws", runner=_FakeRunner(), logger=logger
        )
        worker.accept(_assignment(jmx_plan=_PLAN))
        _await_state(worker, "op-1", JMeterExecutionState.SUCCEEDED)

        context = next(
            extra
            for _, extra in logger.records
            if extra.get("event") == "jmeter_execution_start"
        )
        self.assertEqual("uploaded_jmx", context["execution_mode"])

    def test_the_plan_xml_itself_is_never_logged(self):
        # A plan can carry headers and request bodies; the context line
        # describes the run, it does not reproduce its payload.
        logger = self._CapturingLogger()
        worker = JMeterWorker(
            "jmeter-1", "/tmp/ws", runner=_FakeRunner(), logger=logger
        )
        worker.accept(_assignment())
        _await_state(worker, "op-1", JMeterExecutionState.SUCCEEDED)

        logged = " ".join(
            f"{msg} {extra}" for msg, extra in logger.records
        )
        self.assertNotIn("jmeterTestPlan", logged)


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

    def test_a_relative_workspace_still_produces_paths_jmeter_can_open(self):
        """Regression: a relative workspace made JMeter exit 1 before sampling.

        ``run()`` launches JMeter with ``cwd`` set to the workspace *and* names
        the same workspace in argv. When the workspace is relative — which is
        exactly what the real ``jmeter_workspace_dir``
        ("./public/report/jmeter/detail-report") is — JMeter resolved those argv
        paths a second time against that cwd and looked for
        ``<workspace>/<workspace>/plan.jmx``.

        Every other test here builds its workspace with ``tempfile.mkdtemp()``,
        which is absolute, so the whole suite passed while no real run could
        ever work. This one reproduces the production shape deliberately.
        """
        recorder = os.path.join(self.workspace_root, "record-argv")
        argv_dump = os.path.join(self.workspace_root, "argv.txt")
        with open(recorder, "w", encoding="utf-8") as handle:
            handle.write(f'#!/bin/sh\nprintf "%s\\n" "$@" > {argv_dump}\n')
        os.chmod(recorder, 0o755)

        relative_workspace = "./public/report/jmeter/detail-report/op-1"
        previous_cwd = os.getcwd()
        os.chdir(self.workspace_root)
        try:
            outcome = JMeterProcessRunner(binary=recorder).run(
                "op-1", relative_workspace, _PLAN, timeout_seconds=10
            )
        finally:
            os.chdir(previous_cwd)

        with open(argv_dump, encoding="utf-8") as handle:
            argv = [line.strip() for line in handle if line.strip()]

        # Every path handed to JMeter must be absolute; a relative one is what
        # gets resolved twice.
        path_args = [arg for arg in argv if "/" in arg]
        self.assertTrue(path_args, f"no path arguments were recorded: {argv}")
        for arg in path_args:
            self.assertTrue(
                os.path.isabs(arg), f"JMeter was given a relative path: {arg!r}"
            )

        # The plan JMeter was told to open must actually be there.
        plan_arg = argv[argv.index("-t") + 1]
        self.assertTrue(
            os.path.exists(plan_arg), f"plan does not exist at {plan_arg!r}"
        )

        # And no duplicated tree may appear inside the workspace.
        self.assertFalse(
            os.path.exists(os.path.join(outcome.workspace, "public")),
            "the workspace path was resolved twice and nested itself",
        )

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

    def test_a_clean_exit_that_wrote_nothing_names_every_missing_artifact(self):
        # `true` exits 0 and writes no files at all, which is the shape of a
        # JMeter that dies after argument parsing. Only the plan — written by
        # the runner itself before launch — should be found.
        outcome = JMeterProcessRunner(binary="true").run(
            "op-1", self._workspace(), _PLAN, timeout_seconds=10
        )

        self.assertEqual(
            (
                JMeterProcessRunner.RESULTS_FILE,
                JMeterProcessRunner.ENGINE_LOG,
                f"{JMeterProcessRunner.REPORT_DIR}/index.html",
            ),
            outcome.missing_artifacts,
        )

    def test_a_complete_workspace_reports_nothing_missing(self):
        """A stand-in that writes exactly the files a real run leaves behind."""
        producer = os.path.join(self.workspace_root, "artifact-producer")
        with open(producer, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\n"
                f"touch {JMeterProcessRunner.RESULTS_FILE} "
                f"{JMeterProcessRunner.ENGINE_LOG}\n"
                f"mkdir -p {JMeterProcessRunner.REPORT_DIR}\n"
                f"touch {JMeterProcessRunner.REPORT_DIR}/index.html\n"
            )
        os.chmod(producer, 0o755)

        outcome = JMeterProcessRunner(binary=producer).run(
            "op-1", self._workspace(), _PLAN, timeout_seconds=10
        )

        self.assertEqual((), outcome.missing_artifacts)
        self.assertTrue(outcome.succeeded)

    def test_a_terminated_run_is_not_reported_as_missing_artifacts(self):
        # A timed-out run legitimately has no dashboard; naming those files
        # would report a second, misleading failure alongside the real one.
        runner = JMeterProcessRunner(
            binary=self._long_running_binary(), terminate_grace_seconds=1.0
        )
        outcome = runner.run("op-1", self._workspace(), _PLAN, timeout_seconds=0.3)

        self.assertTrue(outcome.timed_out)
        self.assertEqual((), outcome.missing_artifacts)

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
