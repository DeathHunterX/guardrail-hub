"""The JMeter MCP endpoints as HTTP: status codes and the adapter boundary.

Only what the router itself decides is tested here — which exception becomes
which status code. The readings themselves are the analyzer's, and are covered
in ``tests/services/tools/jmeter/test_analyze_jmeter_result_service.py``.

The 404-vs-500 split is the reason this file exists: "no such operation" and
"that operation belongs to ZAP" are client mistakes with a recoverable answer,
while anything else is the server's problem. Collapsing them into one code
would tell an MCP client to retry something it can never succeed at.
"""

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.mcp.jmeter_router import jmeter_router
from app.schemas.tools.jmeter.run_jmeter_test import JMeterResultAnalysisResponse

_ANALYZE = "/jmeter/analyze_result"
_TARGET_SERVICE = "app.routers.mcp.jmeter_router.JMeterAnalyzer"


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(jmeter_router)
    return TestClient(app)


class AnalyzeEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_a_successful_analysis_is_returned_verbatim(self):
        reading = JMeterResultAnalysisResponse(
            operation_id="op-1", summary="A reading.", details="Some observations."
        )
        with patch(_TARGET_SERVICE) as analyzer:
            analyzer.return_value.analyze_jmeter_result.return_value = reading
            response = self.client.post(_ANALYZE, json={"operation_id": "op-1"})

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "operation_id": "op-1",
                "summary": "A reading.",
                "details": "Some observations.",
            },
            response.json(),
        )

    def test_an_unknown_operation_is_a_404_not_a_500(self):
        with patch(_TARGET_SERVICE) as analyzer:
            analyzer.return_value.analyze_jmeter_result.side_effect = LookupError(
                "No operation found with id 'nope'."
            )
            response = self.client.post(_ANALYZE, json={"operation_id": "nope"})

        self.assertEqual(404, response.status_code)
        self.assertIn("No operation found", response.json()["detail"])

    def test_another_tools_operation_is_a_404_carrying_the_reason(self):
        with patch(_TARGET_SERVICE) as analyzer:
            analyzer.return_value.analyze_jmeter_result.side_effect = LookupError(
                "Operation 'op-1' is a 'api_scan' operation, not a JMeter load test."
            )
            response = self.client.post(_ANALYZE, json={"operation_id": "op-1"})

        self.assertEqual(404, response.status_code)
        self.assertIn("not a JMeter load test", response.json()["detail"])

    def test_an_unexpected_failure_is_a_500(self):
        with patch(_TARGET_SERVICE) as analyzer:
            analyzer.return_value.analyze_jmeter_result.side_effect = RuntimeError(
                "database unreachable"
            )
            response = self.client.post(_ANALYZE, json={"operation_id": "op-1"})

        self.assertEqual(500, response.status_code)

    def test_a_missing_operation_id_is_rejected_before_the_service_is_reached(self):
        with patch(_TARGET_SERVICE) as analyzer:
            response = self.client.post(_ANALYZE, json={})

        self.assertEqual(422, response.status_code)
        analyzer.return_value.analyze_jmeter_result.assert_not_called()


class AdapterBoundaryTests(unittest.TestCase):
    """The endpoint delegates; it does not analyze."""

    def test_the_endpoint_passes_the_operation_id_through_untouched(self):
        with patch(_TARGET_SERVICE) as analyzer:
            analyzer.return_value.analyze_jmeter_result.return_value = (
                JMeterResultAnalysisResponse(operation_id="op-1", summary="x")
            )
            _client().post(_ANALYZE, json={"operation_id": "op-1"})

        analyzer.return_value.analyze_jmeter_result.assert_called_once_with("op-1")

    def test_the_tool_is_registered_under_its_mcp_operation_id(self):
        # MCP clients address the tool by operation_id, not by path, so this
        # name is the public contract — see app/routers/endpoints.py.
        routes = {
            route.path: route.operation_id
            for route in jmeter_router.routes
            if hasattr(route, "operation_id")
        }
        self.assertEqual("analyze_jmeter_result", routes["/jmeter/analyze_result"])
        self.assertEqual("run_jmeter", routes["/jmeter/run_test"])


if __name__ == "__main__":
    unittest.main()
