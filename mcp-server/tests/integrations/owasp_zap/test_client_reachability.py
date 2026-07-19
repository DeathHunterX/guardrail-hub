"""ZapClient.check_target_reachable: worker-side pre-flight reachability check.

The check probes the target THROUGH the assigned worker's proxy (the same path a
replay or active scan takes), so its verdict reflects the worker's network view.
Any HTTP response from the target means "reachable"; only a genuine connection
failure (DNS, refused, timeout, unreachable network) raises
``ZapTargetUnreachableError`` with actionable, Docker-aware guidance. It must
never alter behaviour for reachable targets.
"""

import unittest
from unittest.mock import patch

import pytest

pytest.importorskip("zapv2")

import httpx  # noqa: E402

from app.integrations.owasp_zap import client as client_module  # noqa: E402
from app.integrations.owasp_zap.client import (  # noqa: E402
    ZapClient,
    ZapTargetUnreachableError,
)


class _Resp:
    """Minimal stand-in for an httpx.Response (only what the check reads)."""

    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class _FakeHttpClient:
    """Stands in for ``httpx.Client`` used as a context manager."""

    def __init__(self, *, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.requested = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, method, url):
        self.requested.append((method, url))
        if self._exc is not None:
            raise self._exc
        return self._response


def _client():
    return ZapClient(api_url="http://worker:8080", api_key="k")


def _patch(fake):
    # ``httpx.Client(**kwargs)`` returns the fake context manager.
    return patch.object(client_module.httpx, "Client", return_value=fake)


class CheckTargetReachableTests(unittest.TestCase):
    # ----- reachable: any HTTP response means the worker reached the target -----

    def test_ok_response_does_not_raise(self):
        fake = _FakeHttpClient(response=_Resp(200))
        with _patch(fake):
            # Must not raise — reachable targets keep the existing scan behaviour.
            self.assertIsNone(
                _client().check_target_reachable("http://demo-api:8000/products")
            )
        # The probe is a read-only HEAD to the exact target URL.
        self.assertEqual(fake.requested, [("HEAD", "http://demo-api:8000/products")])

    def test_target_error_status_is_still_reachable(self):
        # 401/404/500 come FROM the target => reached => no raise.
        for status in (401, 404, 500):
            fake = _FakeHttpClient(response=_Resp(status))
            with _patch(fake):
                self.assertIsNone(
                    _client().check_target_reachable("http://demo-api:8000/x")
                )

    def test_target_own_502_without_zap_signature_is_reachable(self):
        # A 502 produced by the target itself (no ZAP error page) is not a
        # proxy-level failure — do not false-fail.
        fake = _FakeHttpClient(response=_Resp(502, text="upstream app error"))
        with _patch(fake):
            self.assertIsNone(
                _client().check_target_reachable("http://demo-api:8000/x")
            )

    # ----- unreachable via ZAP forward-proxy error page (classified) -----

    def test_unknown_host_classified_as_dns(self):
        body = "ZAP Error [java.net.UnknownHostException]: demo-api"
        fake = _FakeHttpClient(response=_Resp(502, text=body))
        with _patch(fake), self.assertRaises(ZapTargetUnreachableError) as ctx:
            _client().check_target_reachable("http://demo-api:8000/products")
        self.assertIn("hostname could not be resolved", str(ctx.exception))

    def test_connection_refused_classified(self):
        body = "ZAP Error [java.net.ConnectException: Connection refused]"
        fake = _FakeHttpClient(response=_Resp(502, text=body))
        with _patch(fake), self.assertRaises(ZapTargetUnreachableError) as ctx:
            _client().check_target_reachable("http://demo-api:8080/products")
        self.assertIn("connection was refused", str(ctx.exception))

    # ----- unreachable via httpx transport exceptions -----

    def test_timeout_exception_classified(self):
        fake = _FakeHttpClient(exc=httpx.ConnectTimeout("timed out"))
        with _patch(fake), self.assertRaises(ZapTargetUnreachableError) as ctx:
            _client().check_target_reachable("http://demo-api:8000/x")
        self.assertIn("timed out", str(ctx.exception))

    def test_proxy_connect_error_points_at_worker(self):
        # Cannot reach the worker's proxy listener at all -> worker problem.
        fake = _FakeHttpClient(exc=httpx.ConnectError("refused"))
        with _patch(fake), self.assertRaises(ZapTargetUnreachableError) as ctx:
            _client().check_target_reachable("http://demo-api:8000/x")
        self.assertIn("worker", str(ctx.exception).lower())

    # ----- Docker guidance in the message -----

    def test_localhost_target_adds_docker_worker_container_hint(self):
        body = "ZAP Error [java.net.ConnectException: Connection refused]"
        for target in (
            "http://localhost:8000/products",
            "http://127.0.0.1:8000/products",
            "http://[::1]:8000/products",
        ):
            fake = _FakeHttpClient(response=_Resp(502, text=body))
            with _patch(fake), self.assertRaises(ZapTargetUnreachableError) as ctx:
                _client().check_target_reachable(target)
            self.assertIn("worker container", str(ctx.exception))

    def test_non_loopback_target_gets_generic_docker_hint(self):
        body = "ZAP Error [java.net.ConnectException: Connection refused]"
        fake = _FakeHttpClient(response=_Resp(502, text=body))
        with _patch(fake), self.assertRaises(ZapTargetUnreachableError) as ctx:
            _client().check_target_reachable("http://demo-api:8080/products")
        message = str(ctx.exception)
        self.assertNotIn("worker container", message)
        self.assertIn("container port", message)  # published-vs-container-port guidance

    def test_message_never_rewrites_the_url(self):
        body = "ZAP Error [java.net.UnknownHostException]"
        fake = _FakeHttpClient(response=_Resp(502, text=body))
        with _patch(fake), self.assertRaises(ZapTargetUnreachableError) as ctx:
            _client().check_target_reachable("http://demo-api:8000/products")
        # The original URL is echoed verbatim; no host/port substitution.
        self.assertIn("http://demo-api:8000/products", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
