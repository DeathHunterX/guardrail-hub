"""HttpReportSender tests — delivers the report over a real local HTTP endpoint."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.integrations.performance.report_sender import HttpReportSender, ReportSendError
from app.schemas.performance.report import ArtifactPayload, OperationReport


class _CapturingHandler(BaseHTTPRequestHandler):
    received = {}
    status_to_return = 200

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        type(self).received = {
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "body": json.loads(body),
        }
        self.send_response(self.status_to_return)
        self.end_headers()

    def log_message(self, *args):  # silence the test server
        pass


def _report():
    return OperationReport(
        operation_id="op-1",
        status="completed",
        exit_code=0,
        duration_seconds=1.0,
        artifacts=[ArtifactPayload(kind="log", name="jmeter.log", content_b64="bG9n")],
    )


class HttpReportSenderTests(unittest.TestCase):
    def setUp(self):
        _CapturingHandler.received = {}
        _CapturingHandler.status_to_return = 200
        self.server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _url(self, path="/performance/operations/report"):
        return f"http://127.0.0.1:{self.port}{path}"

    def test_posts_json_report_with_auth(self):
        HttpReportSender(self._url(), auth_token="tok").send(_report())
        received = _CapturingHandler.received
        self.assertEqual(received["path"], "/performance/operations/report")
        self.assertEqual(received["auth"], "Bearer tok")
        self.assertEqual(received["body"]["operation_id"], "op-1")
        self.assertEqual(received["body"]["artifacts"][0]["name"], "jmeter.log")

    def test_non_2xx_raises_report_send_error(self):
        _CapturingHandler.status_to_return = 500
        with self.assertRaises(ReportSendError):
            HttpReportSender(self._url()).send(_report())

    def test_unreachable_endpoint_raises_report_send_error(self):
        # Nothing listening on this port/path.
        with self.assertRaises(ReportSendError):
            HttpReportSender("http://127.0.0.1:1/none", timeout_seconds=1.0).send(_report())


if __name__ == "__main__":
    unittest.main()
