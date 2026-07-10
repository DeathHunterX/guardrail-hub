"""Unit tests for Slack connection detection (auth.test), with a fake transport."""

import unittest

from app.integrations.chat.slack.connection import (
    AUTH_TEST_URL,
    check_connection,
    resolve_channel_name,
)


class SlackConnectionTests(unittest.TestCase):
    def test_ok_returns_workspace(self):
        def transport(url, headers):
            self.assertEqual(url, AUTH_TEST_URL)
            self.assertEqual(headers["Authorization"], "Bearer xoxb-x")
            return 200, '{"ok": true, "team": "GuardrailWS"}'

        conn = check_connection("xoxb-x", transport=transport)
        self.assertTrue(conn.ok)
        self.assertEqual(conn.workspace, "GuardrailWS")

    def test_invalid_auth_returns_reason(self):
        conn = check_connection("bad", transport=lambda u, h: (200, '{"ok": false, "error": "token_revoked"}'))
        self.assertFalse(conn.ok)
        self.assertEqual(conn.error, "token_revoked")

    def test_http_error_is_not_ok(self):
        conn = check_connection("x", transport=lambda u, h: (500, ""))
        self.assertFalse(conn.ok)
        self.assertIn("500", conn.error)

    def test_network_error_never_raises(self):
        def boom(url, headers):
            raise OSError("no route to host")

        conn = check_connection("x", transport=boom)
        self.assertFalse(conn.ok)
        self.assertIn("no route", conn.error)


class ResolveChannelNameTests(unittest.TestCase):
    def test_id_resolves_to_readable_name(self):
        name = resolve_channel_name(
            "xoxb-x",
            "C0BBRTB4RC2",
            transport=lambda u, h: (200, '{"ok": true, "channel": {"name": "guardrail-hub"}}'),
        )
        self.assertEqual(name, "#guardrail-hub")

    def test_already_readable_name_is_unchanged(self):
        # no transport call needed when it already starts with '#'
        self.assertEqual(resolve_channel_name("t", "#guardrail-hub"), "#guardrail-hub")

    def test_falls_back_to_id_when_not_resolvable(self):
        name = resolve_channel_name(
            "t", "C123", transport=lambda u, h: (200, '{"ok": false, "error": "missing_scope"}')
        )
        self.assertEqual(name, "C123")

    def test_falls_back_to_id_on_error(self):
        def boom(url, headers):
            raise OSError("down")

        self.assertEqual(resolve_channel_name("t", "C123", transport=boom), "C123")

    def test_none_channel_returns_none(self):
        self.assertIsNone(resolve_channel_name("t", None))


if __name__ == "__main__":
    unittest.main()
