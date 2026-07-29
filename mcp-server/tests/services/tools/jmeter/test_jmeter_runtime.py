"""JMeterRuntime: the full pipeline, end to end, with a stubbed worker.

Covers both plan paths (generated and supplied), validation refusal, execution
success, the failure and timeout paths the worker reports, and what actually
lands in ``operation.result``.
"""

import unittest
from types import SimpleNamespace

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
        self.assertIn("index.html", result["artifacts"]["view_report"])
        self.assertIn("results.jtl", result["artifacts"]["results_data"])
        self.assertIn("plan.jmx", result["artifacts"]["test_plan"])
        self.assertIn("jmeter.log", result["artifacts"]["engine_log"])

    def test_artifact_links_are_public_urls(self):
        result = self._persisted()
        self.assertTrue(result["artifacts"]["view_report"].startswith("/public/"))

    def test_summary_and_metrics_are_left_unset(self):
        # Every field in both is derived from the JTL, and parsing is the next
        # milestone. Absent is truthful; zero-filled would not be.
        result = self._persisted()
        self.assertIsNone(result["summary"])
        self.assertIsNone(result["metrics"])

    def test_no_findings_are_reported_for_a_load_test(self):
        operations = _RecordingOperationService()
        _runtime(_StubClient(_SUCCESS), operations).run("op-1", _request(), _WORKER)
        # complete() was called without a findings= breakdown (ADR-0010).
        self.assertEqual(2, len(operations.completed[0]))


if __name__ == "__main__":
    unittest.main()
