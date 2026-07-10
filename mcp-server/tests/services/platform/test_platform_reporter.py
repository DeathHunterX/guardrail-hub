"""Unit tests for PlatformReporter — aggregated summary, format, best-effort notify."""

import unittest

from app.services.platform.platform_reporter import PlatformReporter


class FakeLogger:
    def __init__(self):
        self.records = []

    def info(self, message, extra=None):
        self.records.append(("info", message, extra or {}))

    def warning(self, message, extra=None):
        self.records.append(("warning", message, extra or {}))

    def error(self, message, extra=None):
        self.records.append(("error", message, extra or {}))


class FakeNotifications:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def notify(self, notification):
        if self.fail:
            raise RuntimeError("slack down")
        self.sent.append(notification)


class PlatformReporterTests(unittest.TestCase):
    def _reporter(self, notifications=None, destination="C1"):
        self.logger = FakeLogger()
        return PlatformReporter(self.logger, notification_service=notifications, destination=destination)

    def _events(self):
        return [extra.get("event") for (_lvl, _msg, extra) in self.logger.records]

    def _only_message(self, notifications):
        self.assertEqual(len(notifications.sent), 1)
        return notifications.sent[0].message

    def test_layout_has_header_and_no_time(self):
        n = FakeNotifications()
        self._reporter(n).ready("development", "0.1.0")
        msg = self._only_message(n)
        self.assertTrue(msg.startswith("🛡️ Guardrail Hub"))
        self.assertIn("━", msg)
        self.assertNotIn("Time", msg)  # Slack timestamps the message itself

    def test_ready_summary_aggregates_integrations(self):
        n = FakeNotifications()
        self._reporter(n).ready(
            "development", "0.1.0", integrations=[("🤖 Slack", "Connected (#guardrail-hub)")]
        )
        msg = self._only_message(n)
        self.assertIn("✅ Platform Ready", msg)
        self.assertIn("Environment : Development", msg)
        self.assertIn("v0.1.0", msg)
        self.assertIn("Server", msg)
        self.assertIn("mcp-server", msg)
        self.assertIn("Integrations:", msg)
        self.assertIn("🤖 Slack : Connected (#guardrail-hub)", msg)
        self.assertIn("Status : Healthy", msg)

    def test_ready_status_can_be_degraded(self):
        n = FakeNotifications()
        self._reporter(n).ready(
            "development", "0.1.0", integrations=[("🤖 Slack", "Disconnected")], status="Degraded"
        )
        self.assertIn("Status : Degraded", self._only_message(n))

    def test_shutdown_wording_is_platform_stopping(self):
        n = FakeNotifications()
        self._reporter(n).shutting_down("Manual shutdown")
        msg = self._only_message(n)
        self.assertIn("🛑 Platform Stopping", msg)
        self.assertNotIn("Shutting Down", msg)
        self.assertIn("Reason : Manual shutdown", msg)

    def test_stopped_is_fatal(self):
        n = FakeNotifications()
        self._reporter(n).stopped("Unhandled exception")
        msg = self._only_message(n)
        self.assertIn("❌ Guardrail Hub Stopped", msg)
        self.assertIn("Status : Unavailable", msg)

    def test_configuration_error(self):
        n = FakeNotifications()
        self._reporter(n).configuration_error(["SLACK_BOT_TOKEN"])
        self.assertIn("❌ Configuration Error", self._only_message(n))

    def test_log_only_events_never_notify(self):
        n = FakeNotifications()
        r = self._reporter(n)
        r.configuration_loaded("development", "PostgreSQL", "Slack", "INFO")
        r.mcp_tools_registered(["OWASP ZAP"])
        r.platform_summary(version="0.1.0")
        self.assertEqual(n.sent, [])
        for event in ("configuration_loaded", "mcp_tools_registered", "platform_summary"):
            self.assertIn(event, self._events())

    def test_no_service_or_destination_logs_only(self):
        self._reporter(notifications=None).ready("dev", "0.1.0")
        self.assertIn("ready", self._events())
        n = FakeNotifications()
        PlatformReporter(FakeLogger(), notification_service=n, destination=None).ready("dev", "0.1.0")
        self.assertEqual(n.sent, [])

    def test_notification_failure_never_raises_and_is_logged(self):
        n = FakeNotifications(fail=True)
        self._reporter(n).shutting_down()
        events = self._events()
        self.assertIn("shutting_down", events)
        self.assertIn("notification_failed", events)


if __name__ == "__main__":
    unittest.main()
