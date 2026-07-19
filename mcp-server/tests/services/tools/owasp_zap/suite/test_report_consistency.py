"""Production-readiness tests: report determinism, dedup, and cross-format consistency."""

import json
import unittest

from app.services.tools.owasp_zap.suite.aggregator import (
    EndpointOutcome,
    aggregate_application_report,
)
from app.services.tools.owasp_zap.suite.findings import (
    collect_findings,
    derive_recommendations,
    overall_risk,
)
from app.services.tools.owasp_zap.suite.reporter import SuiteReporter


def _outcomes():
    xss = {"alert_ref": "40012", "name": "XSS", "risk": "High",
           "description": "reflected", "url": "https://api/login", "solution": "encode output"}
    return [
        EndpointOutcome(
            category="Auth", method="POST", url="https://api/login", operation_id="c1",
            status="completed",
            summary={"total": 2, "high": 2, "medium": 0, "low": 0, "informational": 0},
            alerts=[xss, dict(xss, url="https://api/login2")],  # same rule, 2 instances
        ),
        EndpointOutcome(
            category="Orders", method="GET", url="https://api/orders", operation_id="c2",
            status="completed",
            summary={"total": 1, "high": 0, "medium": 1, "low": 0, "informational": 0},
            alerts=[{"alert_ref": "40018", "name": "SQLi", "risk": "Medium",
                     "description": "d", "url": "https://api/orders", "solution": "params"}],
        ),
    ]


class DeterminismTests(unittest.TestCase):
    def test_aggregation_is_deterministic_except_timestamp(self):
        r1 = aggregate_application_report("App", "p", _outcomes())
        r2 = aggregate_application_report("App", "p", _outcomes())
        r1.pop("generated_at"); r2.pop("generated_at")
        r1["executive_summary"].pop("headline", None)
        r2["executive_summary"].pop("headline", None)
        self.assertEqual(r1, r2)

    def test_detailed_findings_deduped_and_ranked_stably(self):
        findings = collect_findings(_outcomes())
        # 2 distinct rules; High before Medium; XSS counted twice.
        self.assertEqual([f["name"] for f in findings], ["XSS", "SQLi"])
        self.assertEqual(findings[0]["count"], 2)
        self.assertEqual(findings[0]["categories"], ["Auth"])


class CrossFormatConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.outcomes = _outcomes()
        self.report = aggregate_application_report("App", "p", self.outcomes)
        self.reporter = SuiteReporter()

    def test_severity_totals_match_across_json_and_sarif(self):
        # JSON severity_summary high count == number of High SARIF results.
        sarif = json.loads(self.reporter.to_sarif(self.outcomes))
        errors = [r for r in sarif["runs"][0]["results"] if r["level"] == "error"]
        self.assertEqual(len(errors), self.report["severity_summary"]["high"])

    def test_markdown_reflects_same_finding_count(self):
        md = self.reporter.to_markdown(self.report)
        # Both distinct findings appear in the Detailed Findings table.
        self.assertIn("XSS", md)
        self.assertIn("SQLi", md)

    def test_sarif_rules_are_deduplicated(self):
        sarif = json.loads(self.reporter.to_sarif(self.outcomes))
        rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        rule_ids = [r["id"] for r in rules]
        self.assertEqual(len(rule_ids), len(set(rule_ids)))  # no duplicate rules
        self.assertEqual(sorted(rule_ids), ["40012", "40018"])


class FindingsEdgeCaseTests(unittest.TestCase):
    def test_overall_risk_none_when_empty(self):
        self.assertEqual(overall_risk({"high": 0, "medium": 0, "low": 0, "informational": 0}), "None")

    def test_recommendations_for_clean_scan(self):
        recs = derive_recommendations([], {"high": 0, "medium": 0, "low": 0, "informational": 0})
        self.assertEqual(len(recs), 1)
        self.assertIn("No findings", recs[0])


if __name__ == "__main__":
    unittest.main()
