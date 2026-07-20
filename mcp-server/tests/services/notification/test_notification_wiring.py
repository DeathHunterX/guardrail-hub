"""Tests for settings-driven notification wiring (build_notification_flow_from_settings).

Verifies the Slack channel is registered and operation events are delivered only
when SLACK_ENABLED is true, and that operations still run + persist when it is
false. A fake config object and fake Slack transport keep this network- and
settings-free.
"""

import json
import unittest
from dataclasses import dataclass
from typing import Optional

from app.bootstrap import build_notification_flow_from_settings
from app.dao.base import BaseOperationDAO
from app.integrations.chat.slack.channel_adapter import HttpResponse
from app.dao.operation_record import OperationRecord


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


class RecordingTransport:
    def __init__(self):
        self.calls = []
        self.response = HttpResponse(200, '{"ok": true}')

    def __call__(self, url, headers, body):
        self.calls.append((url, dict(headers), body))
        return self.response


class NotificationWiringTests(unittest.TestCase):
    def _enabled_flow(self, transport):
        return build_notification_flow_from_settings(
            dao=FakeOperationDAO(),
            config=FakeConfig(
                slack_enabled=True, slack_bot_token="xoxb-x", slack_default_channel="C-OPS"
            ),
            slack_transport=transport,
        )

    def test_enabled_registers_slack_and_notifies_on_created(self):
        transport = RecordingTransport()
        flow = self._enabled_flow(transport)

        self.assertEqual(flow.notification_service.channels, ("slack",))
        op_id = flow.operation_service.create("api_scan")

        self.assertEqual(len(transport.calls), 1)
        _url, headers, body = transport.calls[0]
        payload = json.loads(body.decode())
        self.assertEqual(payload["channel"], "C-OPS")
        self.assertIn(op_id, payload["text"])
        self.assertIn("created", payload["text"])
        self.assertEqual(headers["Authorization"], "Bearer xoxb-x")

    def test_enabled_notifies_on_completed(self):
        transport = RecordingTransport()
        flow = self._enabled_flow(transport)
        op_id = flow.operation_service.create("api_scan")
        transport.calls.clear()

        flow.operation_service.complete(op_id)

        self.assertEqual(len(transport.calls), 1)
        self.assertIn("completed", json.loads(transport.calls[0][2].decode())["text"])

    def test_disabled_registers_no_channel_and_sends_nothing(self):
        transport = RecordingTransport()
        flow = build_notification_flow_from_settings(
            dao=FakeOperationDAO(),
            config=FakeConfig(slack_enabled=False),
            slack_transport=transport,
        )

        self.assertEqual(flow.notification_service.channels, ())
        op_id = flow.operation_service.create("api_scan")
        flow.operation_service.complete(op_id)

        self.assertEqual(transport.calls, [])

    def test_disabled_still_runs_and_persists_operations(self):
        dao = FakeOperationDAO()
        flow = build_notification_flow_from_settings(
            dao=dao, config=FakeConfig(slack_enabled=False)
        )

        op_id = flow.operation_service.create("api_scan")
        self.assertIsNotNone(dao.get_operation(op_id))


if __name__ == "__main__":
    unittest.main()
