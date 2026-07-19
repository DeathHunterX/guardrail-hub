"""ZapClient.run_active_scan: fail fast when ZAP declines to start the scan.

ZAP returns a numeric scan id on success, or an error token (e.g. url_not_found)
when it has no node for the target. The client must reject the token up front —
a scan that never started is a different failure mode from one that disappeared
mid-run — and never enter the polling loop.
"""

import unittest

import pytest

pytest.importorskip("zapv2")

from app.integrations.owasp_zap.client import (  # noqa: E402
    ZapClient,
    ZapScanStartError,
)


class _FakeAscan:
    def __init__(self, scan_return):
        self._scan_return = scan_return
        self.status_calls = 0
        self.stop_calls = 0

    def scan(self, **kwargs):
        return self._scan_return

    def status(self, scan_id):
        self.status_calls += 1
        return "100"

    def stop(self, scan_id):
        self.stop_calls += 1


class _FakeZap:
    def __init__(self, scan_return):
        self.ascan = _FakeAscan(scan_return)


def _client(scan_return):
    client = ZapClient(api_url="http://fake:8080", api_key="k")
    client._zap = _FakeZap(scan_return)  # inject fake, bypass real ZAPv2
    return client


class RunActiveScanStartTests(unittest.TestCase):
    def test_numeric_id_is_returned_unchanged(self):
        client = _client("7")
        self.assertEqual(
            client.run_active_scan(url="http://api.example.com/x", context_id="1"),
            "7",
        )

    def test_numeric_id_as_int_is_accepted(self):
        client = _client(7)
        self.assertEqual(client.run_active_scan(url="http://api.example.com/x"), "7")

    def test_error_token_raises_scan_start_error(self):
        client = _client("url_not_found")
        with self.assertRaises(ZapScanStartError):
            client.run_active_scan(url="http://api.example.com/x", context_id="1")

    def test_error_token_does_not_enter_polling(self):
        client = _client("url_not_found")
        with self.assertRaises(ZapScanStartError):
            client.run_active_scan(url="http://api.example.com/x")
        # ZAP status/stop must never be called — the scan never started.
        self.assertEqual(client._zap.ascan.status_calls, 0)
        self.assertEqual(client._zap.ascan.stop_calls, 0)

    def test_message_distinguishes_not_started_and_preserves_token(self):
        client = _client("does_not_exist")
        with self.assertRaises(ZapScanStartError) as ctx:
            client.run_active_scan(url="http://api.example.com/x")
        message = str(ctx.exception)
        self.assertIn("could not start the active scan", message)
        self.assertIn("instead of a scan id", message)  # "not started", not "disappeared"
        self.assertIn("does_not_exist", message)  # original token preserved
        self.assertNotIn("disappeared", message)

    def test_localhost_target_adds_docker_reachability_hint(self):
        # IPv6 hosts must be bracketed in a URL; ZAP/clients pass them that way.
        for target in (
            "http://localhost:8080/products",
            "http://127.0.0.1:8080/products",
            "http://0.0.0.0:8080/products",
            "http://[::1]:8080/products",
        ):
            client = _client("url_not_found")
            with self.assertRaises(ZapScanStartError) as ctx:
                client.run_active_scan(url=target)
            message = str(ctx.exception)
            self.assertIn("worker container", message)
            self.assertIn("reachable", message)

    def test_non_loopback_target_has_no_docker_hint(self):
        client = _client("url_not_found")
        with self.assertRaises(ZapScanStartError) as ctx:
            client.run_active_scan(url="http://api.example.com/products")
        self.assertNotIn("worker container", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
