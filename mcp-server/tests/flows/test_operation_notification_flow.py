"""Integration tests for the end-to-end Operation -> Notification -> Slack flow.

Exercises the real dispatcher, subscriber, NotificationService, and Slack
adapter wired by ``build_notification_flow``. Only the outer boundaries are
faked: persistence (BaseOperationDAO) and the Slack HTTP transport. No database,
no network.
"""

import json
import unittest

from app.bootstrap import build_notification_flow
from app.dao.base import BaseOperationDAO
from app.integrations.chat.slack.channel_adapter import HttpResponse
from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase


class FakeOperationDAO(BaseOperationDAO):
    def __init__(self):
        self.store: dict[str, OperationRecord] = {}

    def create_operation(self, op_id, status, metadata, batch_type, log_path=None):
        self.store[op_id] = OperationRecord(
            operation_id=op_id, status=status, batch_type=batch_type,
            metadata=metadata, log_path=log_path,
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


class RecordingTransport:
    """Fake Slack HTTP transport recording each POST."""

    def __init__(self):
        self.calls = []
        self.response = HttpResponse(200, '{"ok": true}')

    def __call__(self, url, headers, body):
        self.calls.append((url, dict(headers), body))
        return self.response


class OperationNotificationFlowTests(unittest.TestCase):
    def setUp(self):
        self.transport = RecordingTransport()
        self.dao = FakeOperationDAO()
        self.flow = build_notification_flow(
            dao=self.dao,
            slack_token="xoxb-test",
            destination="C-OPS",
            slack_transport=self.transport,
        )

    def _sent_texts(self):
        return [json.loads(body.decode())["text"] for (_u, _h, body) in self.transport.calls]

    def test_operation_created_sends_slack(self):
        op_id = self.flow.operation_service.create("api_scan")

        self.assertEqual(len(self.transport.calls), 1)
        _url, headers, body = self.transport.calls[0]
        payload = json.loads(body.decode())
        self.assertEqual(payload["channel"], "C-OPS")
        self.assertIn(op_id, payload["text"])
        self.assertIn("created", payload["text"])
        self.assertEqual(headers["Authorization"], "Bearer xoxb-test")

    def test_operation_completed_sends_slack(self):
        op_id = self.flow.operation_service.create("api_scan")
        self.transport.calls.clear()

        self.flow.operation_service.complete(op_id, result="ok")

        self.assertEqual(len(self.transport.calls), 1)
        text = self._sent_texts()[0]
        self.assertIn(op_id, text)
        self.assertIn("completed", text)

    def test_unwired_events_do_not_notify(self):
        op_id = self.flow.operation_service.create("api_scan")
        self.transport.calls.clear()

        self.flow.operation_service.start(op_id)       # started is not wired to Slack
        self.flow.operation_service.fail(op_id, "x")   # failed is not wired to Slack

        self.assertEqual(self.transport.calls, [])

    def test_end_to_end_created_then_completed(self):
        op_id = self.flow.operation_service.create("web_scan")
        self.flow.operation_service.complete(op_id)

        texts = self._sent_texts()
        self.assertEqual(len(texts), 2)
        self.assertIn("created", texts[0])
        self.assertIn("completed", texts[1])

    def test_persistence_still_happens_alongside_notification(self):
        op_id = self.flow.operation_service.create("api_scan")
        self.assertEqual(self.dao.get_operation(op_id).status, OperationPhase.QUEUED)


if __name__ == "__main__":
    unittest.main()
