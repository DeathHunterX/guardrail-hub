"""Unit test for ZapScanRunner: it drives the existing ZapClient correctly.

Uses a fake ZapClient so no live ZAP is required.
"""

import unittest
from dataclasses import dataclass

from app.services.tools.owasp_zap.sync_runner import ZapScanRunner


@dataclass
class FakeRequest:
    url: str = "https://target.example.com/api"
    method: str = "POST"
    report_group: str = "demo"


class FakeZapClient:
    """Records the sequence of ZAP client calls and returns canned values."""

    def __init__(self):
        self.calls = []

    def require_healthy(self):
        self.calls.append("require_healthy")

    def new_session(self, name):
        self.calls.append(("new_session", name))

    def create_context(self, name):
        self.calls.append(("create_context", name))
        return "ctx-1"

    def include_in_context(self, name, regex):
        self.calls.append(("include_in_context", name))

    def wait_for_passive_scan(self, *args, **kwargs):
        self.calls.append("wait_for_passive_scan")

    def run_spider(self, url, context_name=None, **kwargs):
        self.calls.append(("run_spider", url))
        return "spider-1"

    def wait_for_spider(self, scan_id, *args, **kwargs):
        self.calls.append(("wait_for_spider", scan_id))

    def run_active_scan(self, url, context_id=None, recurse=True, method=None, **kwargs):
        self.calls.append(("run_active_scan", url, method))
        return "ascan-1"

    def wait_for_active_scan(self, scan_id, *args, **kwargs):
        self.calls.append(("wait_for_active_scan", scan_id))

    def get_alerts(self, base_url, **kwargs):
        self.calls.append(("get_alerts", base_url))
        return [{"risk": "High"}, {"risk": "Low"}]

    def remove_context(self, name):
        self.calls.append(("remove_context", name))


class ZapScanRunnerTests(unittest.TestCase):
    def test_runs_scan_sequence_and_returns_result(self):
        client = FakeZapClient()
        runner = ZapScanRunner(client=client)

        result = runner(FakeRequest(url="https://t/api", method="POST"))

        self.assertEqual(result["target_url"], "https://t/api")
        self.assertEqual(result["alert_count"], 2)
        self.assertEqual(len(result["alerts"]), 2)

        step_names = [c if isinstance(c, str) else c[0] for c in client.calls]
        for expected in (
            "require_healthy",
            "run_spider",
            "wait_for_spider",
            "run_active_scan",
            "wait_for_active_scan",
            "get_alerts",
        ):
            self.assertIn(expected, step_names)

    def test_passes_http_method_to_active_scan(self):
        client = FakeZapClient()
        ZapScanRunner(client=client)(FakeRequest(method="PUT"))
        ascan = next(c for c in client.calls if c[0] == "run_active_scan")
        self.assertEqual(ascan[2], "PUT")


if __name__ == "__main__":
    unittest.main()
