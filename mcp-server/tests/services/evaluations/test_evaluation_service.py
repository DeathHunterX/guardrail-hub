"""Unit tests for the EvaluationService orchestration (fake scan runner)."""

import unittest
from dataclasses import dataclass

from app.core.ports.event_publisher import DomainEvent, EventPublisher
from app.dao.base import BaseOperationDAO
from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase
from app.services.evaluations.evaluation_service import EvaluationService
from app.services.operations.operation_service import (
    EVENT_OPERATION_COMPLETED,
    EVENT_OPERATION_CREATED,
    EVENT_OPERATION_FAILED,
    EVENT_OPERATION_STARTED,
    OperationService,
)


@dataclass
class FakeRequest:
    url: str = "https://api.example.com/login"
    method: str = "POST"
    report_group: str = "demo"


class FakeOperationDAO(BaseOperationDAO):
    def __init__(self):
        self.store: dict[str, OperationRecord] = {}

    def create_operation(self, op_id, status, metadata, batch_type, log_path=None):
        self.store[op_id] = OperationRecord(
            operation_id=op_id, status=status, batch_type=batch_type, metadata=metadata
        )

    def get_operation(self, operation_id):
        return self.store.get(operation_id)

    def update_operation_status(self, operation_id, status, result=None, error=None, clear_error=False):
        record = self.store[operation_id]
        self.store[operation_id] = record.model_copy(
            update={"status": status, "result": result, "error": error}
        )

    def get_all(self):
        return list(self.store.values())

    def get_by_type(self, batch_type):
        return [r for r in self.store.values() if r.batch_type == batch_type]

    def get_by_status(self, *statuses):
        return [r for r in self.store.values() if r.status in statuses]


class RecordingPublisher(EventPublisher):
    def __init__(self):
        self.events: list[DomainEvent] = []

    def publish(self, event):
        self.events.append(event)


class EvaluationServiceTests(unittest.TestCase):
    def setUp(self):
        self.dao = FakeOperationDAO()
        self.publisher = RecordingPublisher()
        self.operations = OperationService(self.dao, self.publisher, id_suffix=lambda: "fixed")

    def test_success_runs_full_lifecycle(self):
        service = EvaluationService(self.operations, lambda req: {"alert_count": 2})

        op_id = service.run_api_scan(FakeRequest())

        self.assertEqual(op_id, "api_scan:fixed")
        record = self.dao.get_operation(op_id)
        self.assertEqual(record.status, OperationPhase.COMPLETED)
        self.assertEqual(record.result, {"alert_count": 2})
        self.assertEqual(
            [e.name for e in self.publisher.events],
            [EVENT_OPERATION_CREATED, EVENT_OPERATION_STARTED, EVENT_OPERATION_COMPLETED],
        )

    def test_metadata_is_captured(self):
        service = EvaluationService(self.operations, lambda req: {})
        op_id = service.run_api_scan(FakeRequest(url="https://x", method="GET", report_group="p"))

        metadata = self.dao.get_operation(op_id).metadata
        self.assertEqual(metadata["target_url"], "https://x")
        self.assertEqual(metadata["method"], "GET")
        self.assertEqual(metadata["report_group"], "p")

    def test_scan_runner_receives_the_request(self):
        seen = []
        service = EvaluationService(self.operations, lambda req: seen.append(req) or {})
        request = FakeRequest()

        service.run_api_scan(request)

        self.assertIs(seen[0], request)

    def test_failure_marks_failed_publishes_and_reraises(self):
        def boom(_req):
            raise RuntimeError("zap down")

        service = EvaluationService(self.operations, boom)

        with self.assertRaises(RuntimeError):
            service.run_api_scan(FakeRequest())

        record = self.dao.get_all()[0]
        self.assertEqual(record.status, OperationPhase.FAILED)
        self.assertEqual(record.error, "zap down")
        self.assertEqual(
            [e.name for e in self.publisher.events],
            [EVENT_OPERATION_CREATED, EVENT_OPERATION_STARTED, EVENT_OPERATION_FAILED],
        )


if __name__ == "__main__":
    unittest.main()
