"""Unit tests for the Slack NotificationChannel adapter.

The HTTP transport is faked, so these tests never touch the network.
"""

import unittest

from app.core.ports.notification_channel import (
    NotificationContent,
    NotificationField,
)
from app.domain.findings import FindingSummary, Severity
from app.domain.lifecycle import OperationPhase
from app.integrations.chat.slack.channel_adapter import (
    HttpResponse,
    SlackDeliveryError,
    SlackNotificationChannel,
)


class RecordingTransport:
    """Fake transport: captures each call and returns a canned response."""

    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[tuple] = []

    def __call__(self, url, headers, body) -> HttpResponse:
        self.calls.append((url, dict(headers), body))
        return self.response


class SlackNotificationChannelTests(unittest.TestCase):
    def test_name_is_slack(self):
        channel = SlackNotificationChannel(
            token="xoxb-test",
            transport=RecordingTransport(HttpResponse(200, '{"ok": true}')),
        )
        self.assertEqual(channel.name, "slack")

    def test_send_posts_expected_request(self):
        transport = RecordingTransport(HttpResponse(200, '{"ok": true}'))
        channel = SlackNotificationChannel(token="xoxb-test", transport=transport)

        channel.send("C123", "hello world")

        self.assertEqual(len(transport.calls), 1)
        url, headers, body = transport.calls[0]
        self.assertEqual(url, SlackNotificationChannel.API_URL)
        self.assertEqual(headers["Authorization"], "Bearer xoxb-test")
        self.assertIn("application/json", headers["Content-Type"])
        self.assertIn(b'"channel": "C123"', body)
        self.assertIn(b'"text": "hello world"', body)

    def test_send_renders_structured_content_with_text_fallback(self):
        import json

        transport = RecordingTransport(HttpResponse(200, '{"ok": true, "ts": "1"}'))
        channel = SlackNotificationChannel(token="t", transport=transport)

        text = (
            "🔎 API Security Scan\n\n"
            "Target: POST /api/auth/login\n"
            "Status: Security Testing\n\n"
            "Operation #3D65F41B"
        )
        content = NotificationContent(
            title="🔎 API Security Scan",
            phase=OperationPhase.RUNNING,
            fields=(
                NotificationField("Target", "POST /api/auth/login"),
                NotificationField("Status", "Security Testing"),
            ),
            reference="3D65F41B",
        )
        channel.send("C1", text, content)

        body = json.loads(transport.calls[0][2].decode())
        # Plain-text fallback preserved for notifications / accessibility.
        self.assertEqual(body["text"], text)
        blocks = body["blocks"]
        # Bold title section, a divider, then the body section.
        self.assertEqual(blocks[0]["type"], "section")
        self.assertEqual(blocks[0]["text"]["text"], "*🔎 API Security Scan*")
        self.assertTrue(any(b["type"] == "divider" for b in blocks))
        body_text = blocks[-1]["text"]["text"]
        self.assertIn("Target: POST /api/auth/login", body_text)
        self.assertIn("Operation #3D65F41B", body_text)

    def test_send_without_content_delivers_text_verbatim(self):
        """No structured content: the text is delivered as-is, never parsed."""
        import json

        transport = RecordingTransport(HttpResponse(200, '{"ok": true, "ts": "1"}'))
        channel = SlackNotificationChannel(token="t", transport=transport)

        channel.send("C1", "Operation abc created.")

        body = json.loads(transport.calls[0][2].decode())
        self.assertEqual(body["text"], "Operation abc created.")
        self.assertEqual(body["blocks"][0]["text"]["text"], "Operation abc created.")

    def test_completed_scan_renders_product_card_blocks(self):
        import json

        transport = RecordingTransport(HttpResponse(200, '{"ok": true, "ts": "1"}'))
        channel = SlackNotificationChannel(token="t", transport=transport)

        content = NotificationContent(
            title="✅ API Security Scan",
            phase=OperationPhase.COMPLETED,
            target="GET /api/breeds/image/random",
            duration_text="1m 14s",
            findings=FindingSummary.from_counts(
                {Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFORMATIONAL: 13}
            ),
            identifier="e0c5b706-ccda-4c89-9e24-1d37afae6136",
            identifier_help=(
                "Use this Operation ID with get-result to retrieve the "
                "complete scan report."
            ),
        )
        channel.send("C1", "text fallback", content)

        blocks = json.loads(transport.calls[0][2].decode())["blocks"]
        types = [b["type"] for b in blocks]
        self.assertEqual(types[0], "context")   # brand line
        self.assertEqual(types[1], "header")    # completion stated in the header
        self.assertEqual(blocks[1]["text"]["text"], "✅ API Security Scan Completed")
        self.assertGreaterEqual(types.count("divider"), 3)   # sections separated

        sections = "\n".join(
            b["text"]["text"] for b in blocks if b["type"] == "section"
        )
        self.assertIn("🎯 *Target*", sections)
        self.assertIn("GET /api/breeds/image/random", sections)
        self.assertIn("📊 *Findings*", sections)
        for severity in ("🔴 Critical", "🟠 High", "🟡 Medium", "🟢 Low", "🔵 Informational"):
            self.assertIn(severity, sections)   # each severity on its own line
        self.assertIn("Total Findings", sections)
        self.assertIn("`16`", sections)         # 0+0+1+2+13
        self.assertIn("⏱ *Duration*", sections)
        self.assertIn("1m 14s", sections)
        self.assertIn("🆔 *Operation ID*", sections)
        self.assertIn("`e0c5b706-ccda-4c89-9e24-1d37afae6136`", sections)
        # None of the eliminated property-list rows survive in the card.
        self.assertNotIn("Target:", sections)
        self.assertNotIn("Results:", sections)
        self.assertNotIn("Duration:", sections)
        self.assertNotIn("Status:", sections)

        footer = "\n".join(
            e["text"] for b in blocks if b["type"] == "context" for e in b["elements"]
        )
        self.assertIn("get-result", footer)

    def test_completed_card_renders_view_report_link(self):
        import json

        transport = RecordingTransport(HttpResponse(200, '{"ok": true, "ts": "1"}'))
        channel = SlackNotificationChannel(token="t", transport=transport)
        content = NotificationContent(
            title="✅ API Security Scan",
            phase=OperationPhase.COMPLETED,
            target="GET /api/x",
            duration_text="42s",
            findings=FindingSummary.from_counts(
                {Severity.HIGH: 1, Severity.MEDIUM: 3, Severity.LOW: 8,
                 Severity.INFORMATIONAL: 13}
            ),
            report_link="https://example/report/op1",
            identifier="e0c5b706-ccda-4c89-9e24-1d37afae6136",
        )
        channel.send("C1", "text fallback", content)

        blocks = json.loads(transport.calls[0][2].decode())["blocks"]
        sections = "\n".join(
            b["text"]["text"] for b in blocks if b["type"] == "section"
        )
        self.assertIn("📄 *Report*", sections)
        # Native Slack link markup so it renders as a clickable "View Report".
        self.assertIn("<https://example/report/op1|View Report>", sections)

    def test_send_raises_on_slack_error(self):
        transport = RecordingTransport(
            HttpResponse(200, '{"ok": false, "error": "channel_not_found"}')
        )
        channel = SlackNotificationChannel(token="t", transport=transport)

        with self.assertRaises(SlackDeliveryError) as ctx:
            channel.send("C999", "hi")
        self.assertIn("channel_not_found", str(ctx.exception))

    def test_send_raises_on_http_error(self):
        transport = RecordingTransport(HttpResponse(500, ""))
        channel = SlackNotificationChannel(token="t", transport=transport)

        with self.assertRaises(SlackDeliveryError):
            channel.send("C1", "hi")


if __name__ == "__main__":
    unittest.main()
