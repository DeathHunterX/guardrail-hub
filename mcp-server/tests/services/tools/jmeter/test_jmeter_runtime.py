"""JMeterRuntime: the full pipeline, end to end, with a stubbed worker.

Covers both plan paths (generated and supplied), validation refusal, execution
success, the failure and timeout paths the worker reports, the parse of the
results file the run wrote, and what actually lands in ``operation.result``.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.integrations.jmeter.process import JMeterProcessRunner
from app.schemas.tools.jmeter.run_jmeter_test import JMeterTestRequest
from app.schemas.tools.jmeter.worker import JMeterWorkerInfo
from app.schemas.tools.jmeter.worker_assignment import (
    JMeterAssignmentAck,
    JMeterExecutionState,
    JMeterExecutionStateReport,
)
from app.services.tools.jmeter.execution.runtime import JMeterRuntime

_WORKER = JMeterWorkerInfo(
    worker_id="jmeter-1",
    hostname="jmeter-1",
    endpoint="http://jmeter-1:8090",
    port=8090,
)

_SUPPLIED_PLAN = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2">
  <hashTree>
    <HTTPSamplerProxy testname="mine">
      <stringProp name="HTTPSampler.domain">api.example.com</stringProp>
    </HTTPSamplerProxy>
  </hashTree>
</jmeterTestPlan>
"""


def _request(**overrides) -> JMeterTestRequest:
    fields = {
        "target_url": "https://api.example.com/v1/orders",
        "thread_count": 5,
        "ramp_up_seconds": 1,
        "hold_seconds": 1,
    }
    fields.update(overrides)
    return JMeterTestRequest(**fields)


def _config(**overrides):
    fields = {
        "jmeter_allow_supplied_plan": False,
        "jmeter_execution_poll_interval_seconds": 0.0,
        "jmeter_max_run_seconds": 7800,
        # Artifact links are absolute URLs, so the runtime needs the host the
        # server is reachable at — the same setting ZAP's report links use.
        "mcp_server_public_url": "http://localhost:8787",
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class _RecordingOperationService:
    def __init__(self):
        self.started, self.completed, self.failed, self.progress = [], [], [], []

    def start(self, operation_id):
        self.started.append(operation_id)

    def complete(self, operation_id, result=None, **_kwargs):
        self.completed.append((operation_id, result))

    def fail(self, operation_id, error):
        self.failed.append((operation_id, error))

    def report_progress(self, operation_id, **kwargs):
        self.progress.append((operation_id, kwargs))


class _StubClient:
    """Stands in for a worker agent over the wire."""

    def __init__(self, states, accepted=True, ack_message=None):
        self._states = list(states)
        self._accepted = accepted
        self._ack_message = ack_message
        self.assignments = []

    def send_assignment(self, assignment):
        self.assignments.append(assignment)
        return JMeterAssignmentAck(
            operation_id=assignment.operation_id,
            worker_id=_WORKER.worker_id,
            accepted=self._accepted,
            message=self._ack_message,
        )

    def fetch_execution_state(self, operation_id):
        state, message, workspace = self._states.pop(0)
        return JMeterExecutionStateReport(
            operation_id=operation_id,
            worker_id=_WORKER.worker_id,
            state=state,
            message=message,
            workspace=workspace,
        )


class _StubPool:
    def __init__(self, client):
        self._client = client
        self.released = []

    def get_client(self, _worker):
        return self._client

    def release_worker(self, worker_id, operation_id):
        self.released.append((worker_id, operation_id))


def _runtime(client, operations=None, config=None):
    return JMeterRuntime(
        operation_service=operations or _RecordingOperationService(),
        pool_manager=_StubPool(client),
        config=config or _config(),
    )


_SUCCESS = [
    (
        JMeterExecutionState.SUCCEEDED,
        "JMeter completed.",
        "/app/public/report/jmeter/detail-report/op-1",
    )
]


class PipelineTests(unittest.TestCase):
    def test_successful_run_starts_then_completes_the_operation(self):
        operations = _RecordingOperationService()
        runtime = _runtime(_StubClient(_SUCCESS), operations)

        runtime.run("op-1", _request(), _WORKER)

        self.assertEqual(["op-1"], operations.started)
        self.assertEqual(1, len(operations.completed))
        self.assertEqual([], operations.failed)

    def test_the_worker_is_released_on_every_path(self):
        for states in (_SUCCESS, [(JMeterExecutionState.FAILED, "boom", None)]):
            client = _StubClient(states)
            pool = _StubPool(client)
            runtime = JMeterRuntime(
                operation_service=_RecordingOperationService(),
                pool_manager=pool,
                config=_config(),
            )
            runtime.run("op-1", _request(), _WORKER)
            self.assertEqual([("jmeter-1", "op-1")], pool.released)

    def test_generation_path_sends_a_generated_plan(self):
        client = _StubClient(_SUCCESS)
        _runtime(client).run("op-1", _request(), _WORKER)

        plan = client.assignments[0].jmx_plan
        self.assertIn("jmeterTestPlan", plan)
        self.assertIn("api.example.com", plan)
        self.assertIn("ThreadGroup", plan)

    def test_supplied_plan_is_used_verbatim_when_allowed(self):
        client = _StubClient(_SUCCESS)
        runtime = _runtime(client, config=_config(jmeter_allow_supplied_plan=True))

        runtime.run("op-1", _request(jmx_plan=_SUPPLIED_PLAN), _WORKER)

        # Passed through unedited: silently rewriting someone's plan would make
        # what runs differ from what they wrote.
        self.assertEqual(_SUPPLIED_PLAN, client.assignments[0].jmx_plan)

    def test_supplied_plan_is_refused_when_the_server_disallows_it(self):
        operations = _RecordingOperationService()
        client = _StubClient(_SUCCESS)
        _runtime(client, operations).run("op-1", _request(jmx_plan=_SUPPLIED_PLAN), _WORKER)

        self.assertEqual([], client.assignments)  # nothing was ever dispatched
        self.assertEqual(1, len(operations.failed))
        self.assertIn("does not accept", operations.failed[0][1])

    def test_a_supplied_plan_for_a_foreign_host_is_rejected_before_execution(self):
        foreign = _SUPPLIED_PLAN.replace("api.example.com", "victim.example.net")
        operations = _RecordingOperationService()
        client = _StubClient(_SUCCESS)
        runtime = _runtime(
            client, operations, config=_config(jmeter_allow_supplied_plan=True)
        )

        runtime.run("op-1", _request(jmx_plan=foreign), _WORKER)

        # G4: no worker was engaged, so no traffic was ever generated.
        self.assertEqual([], client.assignments)
        self.assertIn("victim.example.net", operations.failed[0][1])


class ExecutionOutcomeTests(unittest.TestCase):
    def test_a_declined_assignment_fails_the_operation(self):
        operations = _RecordingOperationService()
        client = _StubClient(_SUCCESS, accepted=False, ack_message="already busy")
        _runtime(client, operations).run("op-1", _request(), _WORKER)

        self.assertIn("already busy", operations.failed[0][1])

    def test_a_failed_run_fails_the_operation_with_the_workers_reason(self):
        operations = _RecordingOperationService()
        client = _StubClient([(JMeterExecutionState.FAILED, "target unreachable", None)])
        _runtime(client, operations).run("op-1", _request(), _WORKER)

        self.assertIn("target unreachable", operations.failed[0][1])

    def test_a_timed_out_run_surfaces_as_a_failure(self):
        # The worker reports a timeout as a terminal FAILED state with its own
        # message; the Runtime records that verbatim rather than reinterpreting.
        operations = _RecordingOperationService()
        client = _StubClient(
            [(JMeterExecutionState.FAILED, "The run exceeded its 400s limit", None)]
        )
        _runtime(client, operations).run("op-1", _request(), _WORKER)

        self.assertIn("exceeded its", operations.failed[0][1])

    def test_a_worker_that_lost_the_run_fails_the_operation(self):
        operations = _RecordingOperationService()
        client = _StubClient([(JMeterExecutionState.UNKNOWN, None, None)])
        _runtime(client, operations).run("op-1", _request(), _WORKER)

        self.assertIn("no record", operations.failed[0][1])

    def test_running_states_are_polled_until_a_terminal_one_arrives(self):
        operations = _RecordingOperationService()
        client = _StubClient(
            [
                (JMeterExecutionState.RUNNING, "ramping", None),
                (JMeterExecutionState.RUNNING, "holding", None),
                _SUCCESS[0],
            ]
        )
        _runtime(client, operations).run("op-1", _request(), _WORKER)

        self.assertEqual(1, len(operations.completed))

    def test_success_without_a_workspace_is_treated_as_failure(self):
        operations = _RecordingOperationService()
        client = _StubClient([(JMeterExecutionState.SUCCEEDED, "done", None)])
        _runtime(client, operations).run("op-1", _request(), _WORKER)

        self.assertIn("named no workspace", operations.failed[0][1])


class PersistenceTests(unittest.TestCase):
    def _persisted(self):
        operations = _RecordingOperationService()
        _runtime(_StubClient(_SUCCESS), operations).run("op-1", _request(), _WORKER)
        return operations.completed[0][1]

    def test_result_records_metadata_and_artifacts(self):
        result = self._persisted()

        self.assertEqual("op-1", result["operation_id"])
        self.assertEqual("jmeter-1", result["metadata"]["worker_id"])
        self.assertEqual(5, result["metadata"]["thread_count"])
        # Exact filenames, not substrings: "test-results.jtl" contains
        # "results.jtl", so a loose assertion would pass either way and prove
        # nothing about the rename.
        self.assertTrue(
            result["artifacts"]["view_report"].endswith("/html-report/index.html")
        )
        self.assertTrue(result["artifacts"]["results_data"].endswith("/test-results.jtl"))
        self.assertTrue(result["artifacts"]["test_plan"].endswith("/test-plan.jmx"))
        self.assertTrue(result["artifacts"]["engine_log"].endswith("/engine.log"))

    def test_artifact_links_are_absolute_urls_a_client_can_open(self):
        """Regression: these were server-relative paths, so nothing could open them.

        A result is consumed detached from the request that produced it — by an
        MCP client, a Slack card, a browser — none of which have a host to
        resolve a leading "/" against. Asserting only ``startswith("/public/")``
        is what let bare paths ship: it passes for a value no consumer can use.
        """
        artifacts = self._persisted()["artifacts"]

        for name, link in artifacts.items():
            self.assertIsNotNone(link, f"{name} link is missing")
            self.assertTrue(
                link.startswith("http://") or link.startswith("https://"),
                f"{name} is not an absolute URL: {link!r}",
            )
            self.assertIn("/public/report/jmeter/detail-report/", link)

    def test_the_summary_page_is_returned_as_an_artifact(self):
        # The entry point of the package: the one link worth opening first.
        result = self._persisted()
        self.assertTrue(result["artifacts"]["summary_page"].endswith("/summary.html"))

    def test_the_link_field_is_not_called_summary(self):
        """``summary`` on this object would collide, in prose, with
        ``result.summary`` — which is measurements, not a link. Nesting kept the
        payload unambiguous; the ``_page`` suffix keeps the conversation so."""
        artifacts = self._persisted()["artifacts"]
        self.assertNotIn("summary", artifacts)
        self.assertIn("summary_page", artifacts)

    def test_the_artifact_link_set_is_otherwise_unchanged(self):
        artifacts = self._persisted()["artifacts"]
        self.assertEqual(
            {"summary_page", "view_report", "results_data", "test_plan", "engine_log"},
            set(artifacts),
        )

    def test_the_sibling_result_summary_still_holds_measurements(self):
        # Proof the rename moved a link and left the statistics alone.
        result = self._persisted()
        self.assertIn("summary_page", result["artifacts"])
        self.assertIn("summary", result)

    def test_artifact_links_use_the_configured_public_host(self):
        operations = _RecordingOperationService()
        JMeterRuntime(
            operation_service=operations,
            pool_manager=_StubPool(_StubClient(_SUCCESS)),
            config=_config(mcp_server_public_url="https://guardrail.example.com/"),
        ).run("op-1", _request(), _WORKER)

        link = operations.completed[0][1]["artifacts"]["view_report"]
        # Trailing slash on the setting must not produce a doubled slash.
        self.assertTrue(link.startswith("https://guardrail.example.com/public/"), link)

    def test_an_unreadable_results_file_degrades_rather_than_fails_the_run(self):
        # This stub's workspace holds no JTL. The test really ran and its
        # artifacts are real, so the operation still completes — with both
        # derived sections absent, which is truthful. Zero-filled would not be.
        # (Populated-parse coverage is in ParsedResultTests below.)
        result = self._persisted()
        self.assertIsNone(result["summary"])
        self.assertIsNone(result["metrics"])

    def test_a_run_whose_results_cannot_be_read_is_still_completed_not_failed(self):
        operations = _RecordingOperationService()
        _runtime(_StubClient(_SUCCESS), operations).run("op-1", _request(), _WORKER)

        self.assertEqual(1, len(operations.completed))
        self.assertEqual([], operations.failed)

    def test_no_findings_are_reported_for_a_load_test(self):
        operations = _RecordingOperationService()
        _runtime(_StubClient(_SUCCESS), operations).run("op-1", _request(), _WORKER)
        # complete() was called without a findings= breakdown (ADR-0010).
        self.assertEqual(2, len(operations.completed[0]))


class ParsedResultTests(unittest.TestCase):
    """The Parse phase, wired: a real JTL on disk lands as real numbers.

    The worker and the server share the report volume, so the Runtime reads the
    results file the worker wrote straight off the path the worker reported —
    which is what this exercises, using a temp directory as that shared volume.
    """

    _JTL_HEADER = (
        "timeStamp,elapsed,label,responseCode,responseMessage,threadName,"
        "dataType,success,failureMessage,bytes,sentBytes"
    )

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.workspace = str(Path(self._dir.name) / "public" / "op-1")
        Path(self.workspace).mkdir(parents=True)

    def _write_results(self, *rows: str):
        Path(self.workspace, JMeterProcessRunner.RESULTS_FILE).write_text(
            "\n".join([self._JTL_HEADER, *rows]) + "\n", encoding="utf-8"
        )

    def _run_and_persist(self):
        operations = _RecordingOperationService()
        states = [(JMeterExecutionState.SUCCEEDED, "JMeter completed.", self.workspace)]
        _runtime(_StubClient(states), operations).run("op-1", _request(), _WORKER)
        return operations, operations.completed[0][1]

    def test_metrics_from_the_results_file_reach_the_persisted_result(self):
        self._write_results(
            "1700000000000,100,orders,200,OK,tg 1-1,text,true,,1024,512",
            "1700000001000,300,orders,200,OK,tg 1-1,text,true,,1024,512",
            "1700000002000,200,orders,500,KO,tg 1-1,text,false,,1024,512",
        )
        _, result = self._run_and_persist()

        self.assertEqual(3, result["summary"]["total_samples"])
        self.assertEqual(1, result["summary"]["error_count"])
        self.assertEqual(100.0, result["metrics"]["latency"]["min_ms"])
        self.assertEqual(300.0, result["metrics"]["latency"]["max_ms"])

    def test_the_summary_target_matches_the_request_that_authorized_the_run(self):
        self._write_results("1700000000000,100,orders,200,OK,tg 1-1,text,true,,10,5")
        _, result = self._run_and_persist()
        self.assertEqual(_request().target_url, result["summary"]["target_url"])

    def test_the_per_label_breakdown_is_persisted(self):
        self._write_results(
            "1700000000000,100,orders,200,OK,tg 1-1,text,true,,1024,512",
            "1700000001000,200,checkout,200,OK,tg 1-1,text,true,,1024,512",
        )
        _, result = self._run_and_persist()

        labels = [entry["label"] for entry in result["metrics"]["labels"]]
        self.assertEqual(["orders", "checkout"], labels)

    def test_parsing_does_not_disturb_the_lifecycle_or_the_worker_release(self):
        self._write_results("1700000000000,100,orders,200,OK,tg 1-1,text,true,,10,5")
        operations, _ = self._run_and_persist()

        self.assertEqual(["op-1"], operations.started)
        self.assertEqual([], operations.failed)
        self.assertEqual(1, len(operations.completed))

    def test_a_run_that_produced_no_samples_persists_zeros_not_absence(self):
        # Header-only: the file is readable and says "nothing completed". That
        # is a measurement, so it is recorded as one.
        self._write_results()
        _, result = self._run_and_persist()

        self.assertEqual(0, result["summary"]["total_samples"])
        self.assertEqual(0.0, result["metrics"]["throughput_rps"])

    def test_the_run_package_is_written_into_the_workspace(self):
        # The Runtime is the only point where the request, the worker and both
        # timestamps are all in hand, so it is where the package is produced.
        self._write_results("1700000000000,100,orders,200,OK,tg 1-1,text,true,,10,5")
        self._run_and_persist()

        self.assertTrue(Path(self.workspace, "execution.json").exists())
        self.assertTrue(Path(self.workspace, "summary.html").exists())

    def test_the_package_describes_the_operation_that_produced_it(self):
        self._write_results("1700000000000,100,orders,200,OK,tg 1-1,text,true,,10,5")
        self._run_and_persist()

        metadata = json.loads(
            Path(self.workspace, "execution.json").read_text(encoding="utf-8")
        )
        self.assertEqual("op-1", metadata["operation_id"])
        self.assertEqual(_request().target_url, metadata["target"]["url"])
        self.assertEqual(_WORKER.worker_id, metadata["worker"]["worker_id"])

    def test_a_package_writer_failure_does_not_fail_the_operation(self):
        """Best-effort, and it has to stay that way.

        The package is a convenience layered on a run that already succeeded and
        whose measurements are already safe in the artifacts and in
        ``operation.result``. Letting it fail the operation would discard a real
        load test because a nice-to-have HTML file could not be written.
        """
        class _ExplodingWriter:
            def write(self, **_kwargs):
                raise OSError("disk full")

        self._write_results("1700000000000,100,orders,200,OK,tg 1-1,text,true,,10,5")
        operations = _RecordingOperationService()
        states = [(JMeterExecutionState.SUCCEEDED, "done", self.workspace)]
        JMeterRuntime(
            operation_service=operations,
            pool_manager=_StubPool(_StubClient(states)),
            package_writer=_ExplodingWriter(),
            config=_config(),
        ).run("op-1", _request(), _WORKER)

        self.assertEqual([], operations.failed)
        self.assertEqual(1, len(operations.completed))
        self.assertIsNotNone(operations.completed[0][1]["summary"])

    def test_the_package_window_matches_the_persisted_result(self):
        # Two clock reads would let the JSON and the result disagree about when
        # the run finished; they share one value.
        self._write_results("1700000000000,100,orders,200,OK,tg 1-1,text,true,,10,5")
        _, result = self._run_and_persist()

        metadata = json.loads(
            Path(self.workspace, "execution.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            result["metadata"]["finished_at"], metadata["worker"]["finished_at"]
        )

    def test_the_artifacts_still_point_at_the_same_run(self):
        self._write_results("1700000000000,100,orders,200,OK,tg 1-1,text,true,,10,5")
        _, result = self._run_and_persist()

        self.assertTrue(result["artifacts"]["results_data"].endswith("/test-results.jtl"))
        self.assertIsNotNone(result["summary"])


if __name__ == "__main__":
    unittest.main()
