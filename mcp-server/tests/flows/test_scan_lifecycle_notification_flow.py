"""Integration tests for the scan lifecycle -> notification pipeline.

Proves the wiring the ZAP scanner now relies on, without importing the scanner
itself (which pulls FastAPI/zaproxy). It drives the *shared* OperationService
returned by the production builder exactly as the scanner does — create / start /
report_progress milestones / complete / fail — and asserts the single
capability-aware pipeline turns those into one updated Slack message.

Only the outer boundaries are faked: persistence and the Slack HTTP transport.
No database, no network.
"""

import json
import unittest
from dataclasses import dataclass
from typing import Optional

from app.bootstrap import build_operation_notification_flow_from_settings
from app.dao.base import BaseOperationDAO
from app.integrations.chat.slack.channel_adapter import HttpResponse
from app.schemas.internal.operation import OperationRecord
from app.schemas.tools.owasp_zap.common import OperationStatus

POST_MESSAGE = "https://slack.com/api/chat.postMessage"
CHAT_UPDATE = "https://slack.com/api/chat.update"


@dataclass
class FakeConfig:
    slack_enabled: bool
    slack_bot_token: Optional[str] = None
    slack_default_channel: Optional[str] = None


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


class RecordingSlackTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body):
        self.calls.append((url, json.loads(body.decode())))
        return HttpResponse(200, '{"ok": true, "ts": "111.222"}')

    @property
    def urls(self):
        return [u for (u, _p) in self.calls]

    @property
    def texts(self):
        return [p["text"] for (_u, p) in self.calls]


def _simulate_quick_scan(operation_service, op_id, worker_id="worker-1"):
    """Replay the exact OperationService call sequence a QUICK scan performs."""
    operation_service.create(
        batch_type="api_scan", operation_id=op_id, metadata={"target_url": "https://t"}
    )
    operation_service.start(op_id)
    operation_service.report_progress(op_id, stage="initializing", progress=5, worker_id=worker_id)
    operation_service.report_progress(op_id, stage="spider", progress=25, worker_id=worker_id)
    operation_service.report_progress(op_id, stage="active scan", progress=55, worker_id=worker_id)
    operation_service.report_progress(op_id, stage="report generation", progress=90, worker_id=worker_id)
    operation_service.complete(op_id, result={"status": "completed"})


class ScanLifecycleEnabledTests(unittest.TestCase):
    def setUp(self):
        self.transport = RecordingSlackTransport()
        self.dao = FakeOperationDAO()
        self.flow = build_operation_notification_flow_from_settings(
            dao=self.dao,
            config=FakeConfig(True, "xoxb-x", "C-OPS"),
            slack_transport=self.transport,
        )

    def test_single_channel_registered(self):
        self.assertEqual(self.flow.notification_service.channels, ("slack",))

    def test_lifecycle_becomes_one_updated_message(self):
        _simulate_quick_scan(self.flow.operation_service, "uuid-1")

        # Exactly one new message (QUEUED); everything after edits it in place.
        # A second (duplicate) subscription would double this count.
        self.assertEqual(self.transport.urls.count(POST_MESSAGE), 1)
        self.assertEqual(self.transport.urls[0], POST_MESSAGE)
        self.assertTrue(all(u == CHAT_UPDATE for u in self.transport.urls[1:]))
        # QUEUED + RUNNING + 4 progress milestones + COMPLETED = 7 deliveries.
        self.assertEqual(len(self.transport.calls), 7)

    def test_messages_reflect_phases_and_stages(self):
        _simulate_quick_scan(self.flow.operation_service, "uuid-1")
        joined = "\n---\n".join(self.transport.texts)
        # Friendly title (from batch_type) + user-oriented queued status.
        self.assertIn("API Security Scan", self.transport.texts[0])
        self.assertIn("Waiting for available worker", self.transport.texts[0])
        # Short reference instead of the raw operation id.
        self.assertIn("Operation #UUID-1".replace("UUID-1", "UUID1"), self.transport.texts[0])
        # Technical stages are humanized; infra (worker id) never appears.
        self.assertIn("Discovering attack surface", joined)   # spider
        self.assertIn("Security testing", joined)             # active scan
        self.assertNotIn("worker-1", joined)
        self.assertIn("Scan completed", self.transport.texts[-1])

    def test_operation_persisted_as_completed(self):
        _simulate_quick_scan(self.flow.operation_service, "uuid-1")
        self.assertEqual(self.dao.get_operation("uuid-1").status, OperationStatus.COMPLETED)

    def test_failure_transition_notifies(self):
        op = "uuid-2"
        self.flow.operation_service.create(batch_type="api_scan", operation_id=op, metadata={})
        self.flow.operation_service.fail(op, "worker lost heartbeat")

        self.assertEqual(self.transport.urls[0], POST_MESSAGE)   # QUEUED
        self.assertEqual(self.transport.urls[-1], CHAT_UPDATE)   # FAILED edits it
        self.assertIn("Scan failed", self.transport.texts[-1])
        self.assertIn("worker lost heartbeat", self.transport.texts[-1])


class ScanLifecycleDisabledTests(unittest.TestCase):
    def test_no_channel_no_notifications_but_still_runs(self):
        transport = RecordingSlackTransport()
        dao = FakeOperationDAO()
        flow = build_operation_notification_flow_from_settings(
            dao=dao, config=FakeConfig(False), slack_transport=transport
        )
        self.assertEqual(flow.notification_service.channels, ())

        _simulate_quick_scan(flow.operation_service, "uuid-3")

        self.assertEqual(transport.calls, [])  # nothing delivered
        self.assertEqual(dao.get_operation("uuid-3").status, OperationStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
