"""Unit tests for platform lifecycle orchestration (aggregated startup)."""

import unittest

from app.services.platform.lifecycle import report_shutdown, report_startup


class SpyReporter:
    def __init__(self):
        self.calls = []

    def configuration_loaded(self, **kwargs):
        self.calls.append(("configuration_loaded", kwargs))

    def mcp_tools_registered(self, tools):
        self.calls.append(("mcp_tools_registered", list(tools)))

    def ready(self, environment, version, server="mcp-server", integrations=None, status="Healthy"):
        self.calls.append(("ready", {"integrations": integrations, "status": status}))

    def platform_summary(self, **kwargs):
        self.calls.append(("platform_summary", kwargs))

    def shutting_down(self, reason="Manual shutdown"):
        self.calls.append(("shutting_down", {"reason": reason}))


class Conn:
    def __init__(self, ok, workspace=None, error=None):
        self.ok = ok
        self.workspace = workspace
        self.error = error


def _startup(spy, **overrides):
    kwargs = dict(
        environment="development",
        version="0.1.0",
        database_provider="PostgreSQL",
        notification_provider="Slack",
        log_level="INFO",
        tools=["OWASP ZAP"],
    )
    kwargs.update(overrides)
    report_startup(spy, **kwargs)


class LifecycleTests(unittest.TestCase):
    def _names(self, spy):
        return [c[0] for c in spy.calls]

    def _ready(self, spy):
        return dict(spy.calls)["ready"]

    def test_startup_produces_single_bot_summary(self):
        spy = SpyReporter()
        _startup(spy)
        # exactly one bot-facing event (ready); the rest are log-only
        self.assertEqual(
            self._names(spy),
            ["configuration_loaded", "mcp_tools_registered", "ready", "platform_summary"],
        )
        # no separate starting / connected / disconnected messages exist anymore
        for gone in ("starting", "slack_connected", "slack_disconnected"):
            self.assertNotIn(gone, self._names(spy))

    def test_startup_folds_slack_connected_with_channel(self):
        spy = SpyReporter()
        _startup(spy, slack_connection=Conn(True, workspace="Personal"), slack_channel="#guardrail-hub")
        ready = self._ready(spy)
        self.assertEqual(ready["status"], "Healthy")
        self.assertEqual(ready["integrations"], [("🤖 Slack", "Connected (#guardrail-hub)")])

    def test_startup_folds_slack_disconnected_and_degrades(self):
        spy = SpyReporter()
        _startup(spy, slack_connection=Conn(False, error="token_revoked"))
        ready = self._ready(spy)
        self.assertEqual(ready["status"], "Degraded")
        self.assertEqual(ready["integrations"], [("🤖 Slack", "Disconnected")])

    def test_startup_without_slack_has_no_integrations(self):
        spy = SpyReporter()
        _startup(spy)
        self.assertIsNone(self._ready(spy)["integrations"])

    def test_shutdown_fires_stopping(self):
        spy = SpyReporter()
        report_shutdown(spy)
        self.assertEqual(self._names(spy), ["shutting_down"])
        self.assertEqual(spy.calls[0][1]["reason"], "Manual shutdown")


if __name__ == "__main__":
    unittest.main()
