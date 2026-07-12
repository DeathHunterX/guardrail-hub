"""End-to-end tests for the capability-aware Operation -> Notification flow.

Exercises build_operation_notification_flow with the real dispatcher, notifier,
NotificationService and Slack adapter. Only the outer boundaries are faked:
persistence and the Slack HTTP transport. No database, no network.
"""

import json
import unittest

from app.bootstrap import build_operation_notification_flow
from app.core.ports.notification_channel import ChannelCapabilities, NotificationChannel
from app.dao.base import BaseOperationDAO
from app.integrations.chat.slack.channel_adapter import HttpResponse
from app.schemas.internal.operation import OperationRecord
from app.schemas.tools.owasp_zap.common import OperationStatus


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


class SlackTransport:
    """Fake Slack transport that returns a stable ts and records each call."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body):
        self.calls.append((url, dict(headers), json.loads(body.decode())))
        return HttpResponse(200, '{"ok": true, "ts": "111.222"}')


class FallbackChannel(NotificationChannel):
    """Append-only, lifecycle-only channel for the fallback flow."""

    def __init__(self):
        self.sends = []

    @property
    def name(self):
        return "webhook"

    @property
    def capabilities(self):
        return ChannelCapabilities()

    def send(self, destination, message):
        self.sends.append((destination, message))
        return None


class SlackUpdateFlowTests(unittest.TestCase):
    def setUp(self):
        self.transport = SlackTransport()
        self.dao = FakeOperationDAO()
        self.flow = build_operation_notification_flow(
            dao=self.dao,
            slack_token="xoxb-test",
            destination="C-OPS",
            slack_transport=self.transport,
        )

    def test_queued_posts_then_running_and_completed_edit_same_message(self):
        op_id = self.flow.operation_service.create("api_scan")
        self.flow.operation_service.start(op_id)
        self.flow.operation_service.complete(op_id, result="ok")

        urls = [c[0] for c in self.transport.calls]
        self.assertEqual(urls[0], "https://slack.com/api/chat.postMessage")
        self.assertEqual(urls[1], "https://slack.com/api/chat.update")
        self.assertEqual(urls[2], "https://slack.com/api/chat.update")
        # The edits carry the ts returned by the first post.
        self.assertEqual(self.transport.calls[1][2]["ts"], "111.222")

    def test_persistence_unchanged_alongside_notification(self):
        op_id = self.flow.operation_service.create("api_scan")
        self.assertEqual(self.dao.get_operation(op_id).status, OperationStatus.QUEUED)


class FallbackFlowTests(unittest.TestCase):
    def test_fallback_channel_gets_new_message_per_transition(self):
        channel = FallbackChannel()
        flow = build_operation_notification_flow(
            dao=FakeOperationDAO(),
            channels=[channel],
            destination="hook",
            channel_name="webhook",
        )
        op_id = flow.operation_service.create("api_scan")
        flow.operation_service.start(op_id)
        # Progress is skipped on a channel that does not support it.
        flow.operation_service.report_progress(op_id, stage="spider", progress=50)
        flow.operation_service.complete(op_id)

        # created + started + completed = 3 messages; the progress event added none.
        self.assertEqual(len(channel.sends), 3)


if __name__ == "__main__":
    unittest.main()
