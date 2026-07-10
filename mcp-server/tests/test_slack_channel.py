"""Unit tests for the Slack NotificationChannel adapter.

The HTTP transport is faked, so these tests never touch the network.
"""

import unittest

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
