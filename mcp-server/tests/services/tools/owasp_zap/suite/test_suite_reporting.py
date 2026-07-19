"""Unit tests for suite aggregation + report rendering (pure)."""

import json
import unittest

from app.services.tools.owasp_zap.suite.aggregator import (
    EndpointOutcome,
    aggregate_application_report,
)
from app.services.tools.owasp_zap.suite.reporter import SuiteReporter


def _outcomes():
    return [
        EndpointOutcome(
            category="Auth", method="POST", url="https://api/login",
            operation_id="c1", status="completed",
            summary={"total": 2, "high": 1, "medium": 0, "low": 1, "informational": 0},
            alerts=[{"alert_ref": "40012", "name": "XSS", "risk": "High",
                     "description": "reflected", "url": "https://api/login"}],
        ),
        EndpointOutcome(
            category="Orders", method="GET", url="https://api/orders",
            operation_id="c2", status="failed",
            summary={}, error="worker died", alerts=[],
        ),
    ]


class AggregationTests(unittest.TestCase):
    def test_application_and_category_summaries(self):
        report = aggregate_application_report("Shop", "proj", _outcomes())
        s = report["application_summary"]
        self.assertEqual(s["endpoints"], 2)
        self.assertEqual(s["completed"], 1)
        self.assertEqual(s["failed"], 1)
        self.assertEqual(s["high"], 1)
        self.assertEqual(s["low"], 1)
        cats = {c["name"]: c for c in report["categories"]}
        self.assertEqual(cats["Auth"]["summary"]["high"], 1)
        self.assertEqual(len(cats["Orders"]["endpoints"]), 1)


class ReporterTests(unittest.TestCase):
    def setUp(self):
        self.report = aggregate_application_report("Shop", "proj", _outcomes())
        self.reporter = SuiteReporter()

    def test_json_is_valid_and_roundtrips(self):
        parsed = json.loads(self.reporter.to_json(self.report))
        self.assertEqual(parsed["suite_name"], "Shop")

    def test_markdown_contains_summaries(self):
        md = self.reporter.to_markdown(self.report)
        self.assertIn("# Application Security Report — Shop", md)
        self.assertIn("Category Summary", md)
        self.assertIn("Auth", md)

    def test_sarif_is_valid_and_has_results(self):
        sarif = json.loads(self.reporter.to_sarif(_outcomes()))
        self.assertEqual(sarif["version"], "2.1.0")
        run = sarif["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "OWASP ZAP")
        self.assertEqual(len(run["results"]), 1)  # one alert
        self.assertEqual(run["results"][0]["level"], "error")  # High -> error


class EnhancedReportSectionTests(unittest.TestCase):
    def setUp(self):
        self.report = aggregate_application_report("Shop", "proj", _outcomes())

    def test_report_has_all_required_sections(self):
        for key in (
            "executive_summary", "scan_summary", "severity_summary",
            "category_summary", "recommendations", "detailed_findings",
        ):
            self.assertIn(key, self.report)

    def test_executive_summary_overall_risk(self):
        self.assertEqual(self.report["executive_summary"]["overall_risk"], "High")

    def test_detailed_findings_deduped_and_ranked(self):
        findings = self.report["detailed_findings"]
        self.assertEqual(findings[0]["risk"], "High")
        self.assertEqual(findings[0]["name"], "XSS")

    def test_recommendations_not_empty(self):
        self.assertTrue(self.report["recommendations"])

    def test_markdown_renders_new_sections(self):
        md = SuiteReporter().to_markdown(self.report)
        for heading in ("Executive Summary", "Severity Summary", "Recommendations", "Detailed Findings"):
            self.assertIn(heading, md)


if __name__ == "__main__":
    unittest.main()