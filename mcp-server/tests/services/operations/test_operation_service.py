"""Unit tests for the Operation lifecycle service.

Uses in-memory fakes for persistence (BaseOperationDAO) and event publishing
(EventPublisher), so the tests need no database and touch no network.
"""

import unittest
from typing import Any, Optional

from app.core.ports.event_publisher import DomainEvent, EventPublisher
from app.dao.base import BaseOperationDAO
from app.schemas.internal.operation import OperationRecord
from app.schemas.tools.owasp_zap.common import OperationStatus
from app.services.operations.operation_service import (
    EVENT_OPERATION_CANCELLED,
    EVENT_OPERATION_COMPLETED,
    EVENT_OPERATION_CREATED,
    EVENT_OPERATION_FAILED,
    EVENT_OPERATION_STARTED,
    OperationService,
)


class FakeOperationDAO(BaseOperationDAO):
    """In-memory BaseOperationDAO implementation for tests."""

    def __init__(self) -> None:
        self.store: dict[str, OperationRecord] = {}

    def create_operation(self, op_id, status, metadata, batch_type, log_path=None):
        self.store[op_id] = OperationRecord(
            operation_id=op_id,
            status=status,
            batch_type=batch_type,
            metadata=metadata,
            log_path=log_path,
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
    """Captures every published DomainEvent."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


class OperationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dao = FakeOperationDAO()
        self.publisher = RecordingPublisher()
        self.service = OperationService(
            self.dao, self.publisher, id_suffix=lambda: "fixed123"
        )

    # --- creation + event publication (the end-to-end goal of this slice) ---

    def test_create_persists_queued_operation(self):
        op_id = self.service.create("api_scan", metadata={"target_url": "https://x"})

        self.assertEqual(op_id, "api_scan:fixed123")
        record = self.dao.get_operation(op_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, OperationStatus.QUEUED)
        self.assertEqual(record.batch_type, "api_scan")
        self.assertEqual(record.metadata, {"target_url": "https://x"})

    def test_create_publishes_operation_created_event(self):
        op_id = self.service.create("web_scan")

        self.assertEqual(len(self.publisher.events), 1)
        event = self.publisher.events[0]
        self.assertEqual(event.name, EVENT_OPERATION_CREATED)
        self.assertEqual(event.payload["operation_id"], op_id)
        self.assertEqual(event.payload["batch_type"], "web_scan")

    def test_create_defaults_metadata_to_empty_dict(self):
        op_id = self.service.create("batch_scan")
        self.assertEqual(self.dao.get_operation(op_id).metadata, {})

    # --- lifecycle transitions ---

    def test_start_sets_running_and_publishes(self):
        op_id = self.service.create("api_scan")
        self.publisher.events.clear()

        self.service.start(op_id)

        self.assertEqual(self.dao.get_operation(op_id).status, OperationStatus.RUNNING)
        self.assertEqual(self.publisher.events[-1].name, EVENT_OPERATION_STARTED)

    def test_complete_sets_completed_with_result_and_publishes(self):
        op_id = self.service.create("api_scan")
        self.publisher.events.clear()

        self.service.complete(op_id, result={"findings": 3})

        record = self.dao.get_operation(op_id)
        self.assertEqual(record.status, OperationStatus.COMPLETED)
        self.assertEqual(record.result, {"findings": 3})
        self.assertEqual(self.publisher.events[-1].name, EVENT_OPERATION_COMPLETED)

    def test_complete_forwards_findings_into_the_event(self):
        # The severity summary must ride the completed event so the notification
        # can render it without loading/parsing the persisted result.
        op_id = self.service.create("api_scan")
        self.publisher.events.clear()

        breakdown = {"critical": 0, "high": 1, "medium": 3, "low": 8, "informational": 12}
        self.service.complete(op_id, result={"summary": breakdown}, findings=breakdown)

        event = self.publisher.events[-1]
        self.assertEqual(event.name, EVENT_OPERATION_COMPLETED)
        self.assertEqual(event.payload["findings"], breakdown)

    def test_complete_without_findings_omits_the_key(self):
        op_id = self.service.create("api_scan")
        self.publisher.events.clear()

        self.service.complete(op_id, result="ok")

        self.assertNotIn("findings", self.publisher.events[-1].payload)

    def test_fail_sets_failed_with_error_and_publishes(self):
        op_id = self.service.create("api_scan")
        self.publisher.events.clear()

        self.service.fail(op_id, error="boom")

        record = self.dao.get_operation(op_id)
        self.assertEqual(record.status, OperationStatus.FAILED)
        self.assertEqual(record.error, "boom")
        event = self.publisher.events[-1]
        self.assertEqual(event.name, EVENT_OPERATION_FAILED)
        self.assertEqual(event.payload["error"], "boom")

    def test_cancel_sets_cancelled_and_publishes(self):
        op_id = self.service.create("api_scan")
        self.publisher.events.clear()

        self.service.cancel(op_id)

        self.assertEqual(self.dao.get_operation(op_id).status, OperationStatus.CANCELLED)
        self.assertEqual(self.publisher.events[-1].name, EVENT_OPERATION_CANCELLED)

    def test_full_lifecycle_event_sequence(self):
        op_id = self.service.create("api_scan")
        self.service.start(op_id)
        self.service.complete(op_id, result="ok")

        names = [e.name for e in self.publisher.events]
        self.assertEqual(
            names,
            [EVENT_OPERATION_CREATED, EVENT_OPERATION_STARTED, EVENT_OPERATION_COMPLETED],
        )

    def test_get_delegates_to_dao(self):
        op_id = self.service.create("api_scan")
        self.assertIs(self.service.get(op_id), self.dao.get_operation(op_id))


if __name__ == "__main__":
    unittest.main()
