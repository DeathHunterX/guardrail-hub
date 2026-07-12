"""Unit tests for the Slack adapter's capabilities and chat.update support.

Complements test_channel_adapter.py (which covers chat.postMessage). The HTTP
transport is faked, so these tests never touch the network.
"""

import json
import unittest

from app.integrations.chat.slack.channel_adapter import (
    HttpResponse,
    SlackNotificationChannel,
)


class RecordingTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[tuple] = []

    def __call__(self, url, headers, body) -> HttpResponse:
        self.calls.append((url, dict(headers), body))
        return self.response


class SlackCapabilitiesTests(unittest.TestCase):
    def test_declares_full_capabilities(self):
        channel = SlackNotificationChannel(
            token="t", transport=RecordingTransport(HttpResponse(200, '{"ok": true}'))
        )
        caps = channel.capabilities
        self.assertTrue(caps.supports_message_update)
        self.assertTrue(caps.supports_threads)
        self.assertTrue(caps.supports_buttons)
        self.assertTrue(caps.supports_progress)


class SlackSendReturnsRefTests(unittest.TestCase):
    def test_send_returns_message_ts(self):
        transport = RecordingTransport(HttpResponse(200, '{"ok": true, "ts": "17.42"}'))
        channel = SlackNotificationChannel(token="t", transport=transport)

        ref = channel.send("C1", "hi")
        self.assertEqual(ref, "17.42")


class SlackUpdateTests(unittest.TestCase):
    def test_update_posts_to_update_url_with_ts(self):
        transport = RecordingTransport(HttpResponse(200, '{"ok": true, "ts": "17.42"}'))
        channel = SlackNotificationChannel(token="t", transport=transport)

        ref = channel.update("C1", "17.42", "edited")

        url, _headers, body = transport.calls[0]
        self.assertEqual(url, SlackNotificationChannel.UPDATE_URL)
        payload = json.loads(body.decode())
        self.assertEqual(payload["ts"], "17.42")
        self.assertEqual(payload["channel"], "C1")
        self.assertEqual(payload["text"], "edited")
        self.assertEqual(ref, "17.42")

    def test_update_without_ref_falls_back_to_post(self):
        transport = RecordingTransport(HttpResponse(200, '{"ok": true, "ts": "1.0"}'))
        channel = SlackNotificationChannel(token="t", transport=transport)

        channel.update("C1", None, "new")

        url, _headers, _body = transport.calls[0]
        self.assertEqual(url, SlackNotificationChannel.API_URL)


if __name__ == "__main__":
    unittest.main()
