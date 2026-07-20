"""Integration test for the full Evaluation -> Notification chain.

Proves end to end:

    EvaluationService.run_api_scan
        -> OperationService lifecycle (create/start/complete|fail)
        -> EventPublisher (in-process dispatcher)
        -> NotificationService
        -> Slack channel

Only the outer boundaries are faked: persistence (DAO), the scan itself
(scan runner), and the Slack HTTP transport. No DB, no network, no ZAP.
"""

import json
import unittest
from dataclasses import dataclass
from typing import Optional

from app.bootstrap import (
    build_notification_flow_from_settings,
    build_zap_evaluation_service,
)
from app.dao.base import BaseOperationDAO
from app.integrations.chat.slack.channel_adapter import HttpResponse
from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase


@dataclass
class FakeConfig:
    slack_enabled: bool = True
    slack_bot_token: Optional[str] = "xoxb-test"
    slack_default_channel: Optional[str] = "C-OPS"


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


class RecordingTransport:
    def __init__(self):
        self.calls = []
        self.response = HttpResponse(200, '{"ok": true}')

    def __call__(self, url, headers, body):
        self.calls.append((url, dict(headers), body))
        return self.response


class EvaluationNotificationChainTests(unittest.TestCase):
    def _wire(self, scan_runner):
        self.dao = FakeOperationDAO()
        self.transport = RecordingTransport()
        flow = build_notification_flow_from_settings(
            dao=self.dao, config=FakeConfig(), slack_transport=self.transport
        )
        return build_zap_evaluation_service(flow.operation_service, scan_runner=scan_runner)

    def _texts(self):
        return [json.loads(body.decode())["text"] for (_u, _h, body) in self.transport.calls]

    def test_successful_scan_notifies_created_and_completed(self):
        evaluation = self._wire(scan_runner=lambda req: {"alert_count": 1})

        op_id = evaluation.run_api_scan(FakeRequest())

        self.assertEqual(self.dao.get_operation(op_id).status, OperationPhase.COMPLETED)
        texts = self._texts()
        self.assertEqual(len(texts), 2)
        self.assertIn("created", texts[0])
        self.assertIn(op_id, texts[0])
        self.assertIn("completed", texts[1])

    def test_failed_scan_marks_failed_and_notifies_created_only(self):
        def boom(_req):
            raise RuntimeError("zap unreachable")

        evaluation = self._wire(scan_runner=boom)

        with self.assertRaises(RuntimeError):
            evaluation.run_api_scan(FakeRequest())

        # created was notified; failed is not wired to Slack in the current pipeline
        texts = self._texts()
        self.assertEqual(len(texts), 1)
        self.assertIn("created", texts[0])

        record = self.dao.get_all()[0]
        self.assertEqual(record.status, OperationPhase.FAILED)
        self.assertEqual(record.error, "zap unreachable")


if __name__ == "__main__":
    unittest.main()
