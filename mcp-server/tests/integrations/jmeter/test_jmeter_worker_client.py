"""Dispatcher <-> worker communication contract.

Exercised against a stub transport: the payload must arrive intact, an ack must
round-trip, a refusal must be readable as a refusal rather than an error, and a
transport failure must surface as one clear exception type.
"""

import unittest

import httpx

from app.integrations.jmeter.worker_client import (
    JMeterWorkerClient,
    JMeterWorkerCommunicationError,
)
from app.schemas.tools.jmeter.run_jmeter_test import JMeterTestRequest
from app.schemas.tools.jmeter.worker_assignment import (
    JMeterAssignmentRequest,
    JMeterExecutionState,
)


def _assignment(operation_id: str = "op-1") -> JMeterAssignmentRequest:
    return JMeterAssignmentRequest(
        operation_id=operation_id,
        request=JMeterTestRequest(
            target_url="https://api.example.com/v1/orders",
            thread_count=50,
            ramp_up_seconds=30,
            hold_seconds=300,
        ),
    )


def _client_with(handler) -> JMeterWorkerClient:
    """Build a client whose transport is served by *handler*."""
    return JMeterWorkerClient(
        endpoint="http://jmeter-1:8090",
        worker_id="jmeter-1",
        transport=httpx.Client(transport=httpx.MockTransport(handler)),
    )


class AssignmentTransportTests(unittest.TestCase):
    def test_assignment_payload_reaches_the_worker_intact(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = request.read().decode()
            return httpx.Response(
                200,
                json={"operation_id": "op-1", "worker_id": "jmeter-1", "accepted": True},
            )

        ack = _client_with(handler).send_assignment(_assignment())

        self.assertEqual("http://jmeter-1:8090/assignments", seen["url"])
        # The whole validated request travels with the assignment, so the worker
        # needs no database access of its own.
        self.assertIn("https://api.example.com/v1/orders", seen["body"])
        self.assertIn('"thread_count":50', seen["body"].replace(" ", ""))
        self.assertTrue(ack.accepted)

    def test_a_refusal_is_a_normal_answer_not_an_error(self):
        def handler(_request):
            return httpx.Response(
                200,
                json={
                    "operation_id": "op-1",
                    "worker_id": "jmeter-1",
                    "accepted": False,
                    "message": "already running an operation",
                },
            )

        ack = _client_with(handler).send_assignment(_assignment())
        self.assertFalse(ack.accepted)
        self.assertIn("already running", ack.message)

    def test_unreachable_worker_raises_a_communication_error(self):
        def handler(_request):
            raise httpx.ConnectError("connection refused")

        with self.assertRaises(JMeterWorkerCommunicationError):
            _client_with(handler).send_assignment(_assignment())

    def test_error_status_raises_a_communication_error(self):
        def handler(_request):
            return httpx.Response(500, json={"detail": "boom"})

        with self.assertRaises(JMeterWorkerCommunicationError):
            _client_with(handler).send_assignment(_assignment())

    def test_unreadable_ack_raises_a_communication_error(self):
        def handler(_request):
            return httpx.Response(200, json={"unexpected": "shape"})

        with self.assertRaises(JMeterWorkerCommunicationError):
            _client_with(handler).send_assignment(_assignment())


class ExecutionStateTransportTests(unittest.TestCase):
    def test_state_report_round_trips(self):
        def handler(_request):
            return httpx.Response(
                200,
                json={
                    "operation_id": "op-1",
                    "worker_id": "jmeter-1",
                    "state": "running",
                    "message": "ramping up",
                },
            )

        report = _client_with(handler).fetch_execution_state("op-1")
        self.assertEqual(JMeterExecutionState.RUNNING, report.state)

    def test_failure_is_reported_as_a_terminal_state_with_a_reason(self):
        def handler(_request):
            return httpx.Response(
                200,
                json={
                    "operation_id": "op-1",
                    "worker_id": "jmeter-1",
                    "state": "failed",
                    "message": "target unreachable",
                },
            )

        report = _client_with(handler).fetch_execution_state("op-1")
        self.assertEqual(JMeterExecutionState.FAILED, report.state)
        self.assertEqual("target unreachable", report.message)

    def test_unknown_operation_is_a_state_not_an_exception(self):
        # "The worker restarted and lost the run" is something the Runtime must
        # handle, so it must not arrive as a transport failure.
        def handler(_request):
            return httpx.Response(404)

        report = _client_with(handler).fetch_execution_state("op-1")
        self.assertEqual(JMeterExecutionState.UNKNOWN, report.state)


if __name__ == "__main__":
    unittest.main()
