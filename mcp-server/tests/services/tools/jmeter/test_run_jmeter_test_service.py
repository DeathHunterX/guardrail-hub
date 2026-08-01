"""JMeter submission contract — the one path that is fully implemented in the
skeleton.

Covers what submission promises: the request is validated at the boundary
(Guardrail G4's explicit-target rule included), exactly one QUEUED row is
created, and it lands in the JMeter queue lane with the metadata the rest of the
system reads back.
"""

import unittest

from pydantic import ValidationError

from app.constants.batch import BatchType
from app.schemas.tools.jmeter.run_jmeter_test import JMeterTestRequest
from app.services.tools.jmeter import JMeterTestService


class _RecordingOperationService:
    """Captures create() calls instead of persisting them."""

    def __init__(self) -> None:
        self.created: list[dict] = []

    def create(self, batch_type, metadata=None, log_path=None, operation_id=None):
        self.created.append(
            {
                "batch_type": batch_type,
                "metadata": metadata or {},
                "operation_id": operation_id,
            }
        )
        return operation_id


def _request(**overrides) -> JMeterTestRequest:
    fields = {
        "target_url": "https://api.example.com/v1/orders",
        "thread_count": 50,
        "ramp_up_seconds": 30,
        "hold_seconds": 300,
    }
    fields.update(overrides)
    return JMeterTestRequest(**fields)


class JMeterSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.operations = _RecordingOperationService()
        self.service = JMeterTestService(operation_service=self.operations)

    def test_submit_creates_exactly_one_operation_in_the_jmeter_lane(self):
        response = self.service.init_run_jmeter_test(_request())

        self.assertEqual(1, len(self.operations.created))
        created = self.operations.created[0]
        self.assertEqual(BatchType.JMETER_TEST, created["batch_type"])
        self.assertEqual(created["operation_id"], response.operation_id)

    def test_submit_returns_a_receipt_not_a_result(self):
        response = self.service.init_run_jmeter_test(_request())

        self.assertTrue(response.operation_id)
        self.assertEqual("queued", response.status)
        self.assertIn(response.operation_id, response.message)

    def test_metadata_carries_the_request_and_the_flat_target_keys(self):
        self.service.init_run_jmeter_test(
            _request(target_url="https://api.example.com/checkout")
        )

        metadata = self.operations.created[0]["metadata"]
        # Flat keys: the notification layer resolves the user-facing target line
        # from these (app.bootstrap._format_scan_target).
        self.assertEqual("https://api.example.com/checkout", metadata["target_url"])
        self.assertEqual("GET", metadata["method"])
        # Full request: the Runtime reconstructs it from the row after a restart.
        self.assertEqual(50, metadata["request"]["thread_count"])

    def test_request_round_trips_through_persisted_metadata(self):
        original = _request(method="POST", thread_count=10)
        self.service.init_run_jmeter_test(original)

        metadata = self.operations.created[0]["metadata"]
        restored = JMeterTestService.request_from_metadata(metadata)
        self.assertEqual(original, restored)


class JMeterTargetValidationTests(unittest.TestCase):
    """Guardrail G4 at the boundary: the target is named, never inferred."""

    def test_relative_target_is_rejected(self):
        with self.assertRaises(ValidationError):
            _request(target_url="/v1/orders")

    def test_non_http_scheme_is_rejected(self):
        with self.assertRaises(ValidationError):
            _request(target_url="file:///etc/passwd")

    def test_thread_count_is_bounded(self):
        with self.assertRaises(ValidationError):
            _request(thread_count=0)
        with self.assertRaises(ValidationError):
            _request(thread_count=10_000)


if __name__ == "__main__":
    unittest.main()
