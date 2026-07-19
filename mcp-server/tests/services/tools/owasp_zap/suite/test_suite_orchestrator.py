"""Unit tests for SuiteOrchestrator fan-out / fan-in (no ZAP, no DB, no pool)."""

import unittest

from app.schemas.tools.owasp_zap.common import OperationStatus
from pydantic import ValidationError

from app.schemas.tools.owasp_zap.scan_api_suite import ZapApiSuiteScanRequest
from app.services.tools.owasp_zap.suite.orchestrator import SuiteOrchestrator


class _FakeOpService:
    def __init__(self):
        self.progress = []
        self.completed = None
        self.failed = None

    def report_progress(self, operation_id, **kw):
        self.progress.append(kw)

    def complete(self, operation_id, result=None, findings=None):
        self.completed = {"result": result, "findings": findings}

    def fail(self, operation_id, error):
        self.failed = error


class _FakeRecord:
    def __init__(self, status, result=None, error=None):
        self.status = status
        self.result = result
        self.error = error


class _FakeReporter:
    def save(self, operation_id, report, outcomes):
        self.saved = {"report": report, "outcomes": outcomes}
        return {"view_report": "md", "export_data": "json", "sarif": "sarif"}


def _suite_request():
    return ZapApiSuiteScanRequest(
        report_group="p",
        application_name="Shop",
        categories=[
            {
                "name": "Auth",
                "openapi_spec": {"paths": {"/login": {"post": {}}}},
                "base_url": "https://api",
                "defaults": {"token": "T", "token_type": "jwt"},
            },
            {
                "name": "Orders",
                "openapi_spec": {"paths": {"/orders": {"get": {}, "post": {}}}},
                "base_url": "https://api",
            },
        ],
    )


class SuiteOrchestratorTests(unittest.TestCase):
    def _run(self, results_by_child):
        op = _FakeOpService()
        submitted = []

        def submitter(child_request, parent_operation_id):
            child_id = f"child-{len(submitted)}"
            submitted.append((child_id, child_request, parent_operation_id))
            return child_id

        def getter(child_id):
            return results_by_child[child_id]

        reporter = _FakeReporter()
        orch = SuiteOrchestrator(
            op,
            scan_submitter=submitter,
            operation_getter=getter,
            reporter=reporter,
            sleep=lambda _s: None,
        )
        orch.run("suite-1", _suite_request())
        return op, submitted, reporter

    def test_fans_out_one_child_per_endpoint_and_aggregates(self):
        # 3 endpoints total: Auth POST /login, Orders GET+POST /orders
        completed = _FakeRecord(
            OperationStatus.COMPLETED,
            result={"summary": {"total": 2, "high": 1, "medium": 1, "low": 0, "informational": 0},
                    "alerts": [{"alert_ref": "40012", "name": "XSS", "risk": "High",
                               "description": "d", "url": "https://api/x"}]},
        )
        results = {f"child-{i}": completed for i in range(3)}
        op, submitted, reporter = self._run(results)

        self.assertEqual(len(submitted), 3)  # one child scan per endpoint
        self.assertIsNone(op.failed)
        self.assertIsNotNone(op.completed)
        report = op.completed["result"]
        self.assertEqual(report["application_summary"]["endpoints"], 3)
        self.assertEqual(report["application_summary"]["completed"], 3)
        self.assertEqual(report["application_summary"]["high"], 3)
        self.assertEqual({c["name"] for c in report["categories"]}, {"Auth", "Orders"})
        # findings forwarded for notification
        self.assertEqual(op.completed["findings"]["high"], 3)
        # parent id propagated to every child
        self.assertTrue(all(p == "suite-1" for _, _, p in submitted))
        # defaults applied to Auth child request
        auth_children = [r for _, r, _ in submitted if "Auth" in r.report_group]
        self.assertEqual(auth_children[0].token, "T")

    def test_child_failure_is_counted(self):
        ok = _FakeRecord(OperationStatus.COMPLETED, result={"summary": {"total": 0}, "alerts": []})
        bad = _FakeRecord(OperationStatus.FAILED, result=None, error="boom")
        results = {"child-0": ok, "child-1": bad, "child-2": ok}
        op, submitted, _ = self._run(results)
        summary = op.completed["result"]["application_summary"]
        self.assertEqual(summary["completed"], 2)
        self.assertEqual(summary["failed"], 1)

    def test_empty_category_is_rejected_at_validation_time(self):
        # A category that expands to zero endpoints is now caught up-front by the
        # request model (fail fast), before any orchestration runs.
        with self.assertRaises(ValidationError):
            ZapApiSuiteScanRequest(
                report_group="p", application_name="A",
                categories=[{"name": "Empty", "openapi_spec": {"paths": {}}}],
            )


if __name__ == "__main__":
    unittest.main()
