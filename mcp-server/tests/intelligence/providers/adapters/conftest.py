"""conftest.py — mock httpx for all adapter tests.

httpx is not installed in the test environment. This file creates a fake
httpx module and injects it into sys.modules before any adapter code runs,
so the adapter modules can be imported without a network or httpx package.
"""

import sys
from unittest.mock import MagicMock

# Build a complete fake httpx module.
fake_httpx = MagicMock()
fake_httpx.__name__ = "httpx"
fake_httpx.__version__ = "0.28.0.mock"

# Timeout sentinel used in the real httpx.
class Timeout:
    pass


class _MockTimeout:
    pass


fake_httpx.Timeout = _MockTimeout


class _MockAsyncClient:
    def __init__(self, **kwargs):
        self.base_url = kwargs.get("base_url", "")
        self.headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout")
        self._closed = False

    async def post(self, path, **kw):
        return _mock_response(200, {})

    def stream(self, method, path, **kw):
        return _mock_stream_context([])

    async def aclose(self):
        self._closed = True


class _MockResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise Exception(f"HTTP {self.status_code}")


class _MockStreamContext:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class TimeoutException(Exception):
    pass


class ConnectError(Exception):
    pass


class PoolTimeout(Exception):
    pass


class ProtocolError(Exception):
    pass


class HTTPStatusError(Exception):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


fake_httpx.AsyncClient = _MockAsyncClient
fake_httpx.Timeout = _MockTimeout
fake_httpx.TimeoutException = TimeoutException
fake_httpx.ConnectError = ConnectError
fake_httpx.PoolTimeout = PoolTimeout
fake_httpx.ProtocolError = ProtocolError
fake_httpx.HTTPStatusError = HTTPStatusError


def _mock_response(status_code, json_data):
    return _MockResponse(status_code, json_data)


def _mock_stream_context(lines):
    return _MockStreamContext(lines)


# Inject before any adapter code runs.
if "httpx" not in sys.modules:
    sys.modules["httpx"] = fake_httpx
