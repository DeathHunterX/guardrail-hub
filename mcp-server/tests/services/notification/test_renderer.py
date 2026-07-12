"""Unit tests for the professional status-card renderer.

Covers the presentation hierarchy (title/target/status first), human-friendly
status wording, concise completion/failure cards, short-reference identity, and
the Debug-Mode isolation of Level-4 infrastructure detail.
"""

import unittest

from app.services.notification.operation_progress import (
    LifecyclePhase,
    OperationProgress,
    ScanFindings,
)
from app.services.notification.renderer import (
    OperationNotificationRenderer,
    humanize_stage,
)


class RendererDefaultTests(unittest.TestCase):
    def setUp(self):
        self.renderer = OperationNotificationRenderer()

    def test_queued_shows_title_and_friendly_status(self):
        text = self.renderer.render(
            OperationProgress(
                "api_scan:1d015005",
                LifecyclePhase.QUEUED,
                title="API Security Scan",
                reference="1D015005",
            )
        )
        self.assertIn("API Security Scan", text)
        self.assertIn("Waiting for available worker", text)
        # By default only a short reference is shown; the full id is Level-4.
        self.assertIn("Operation #1D015005", text)
        self.assertNotIn("api_scan:1d015005", text)

    def test_running_shows_target_friendly_phase_progress_elapsed(self):
        text = self.renderer.render(
            OperationProgress(
                "api_scan:1d015005",
                LifecyclePhase.RUNNING,
                stage="active scan",
                progress=40,
                title="API Security Scan",
                target="POST /api/auth/login",
                worker_id="worker-2",
                elapsed_seconds=75,
                reference="1D015005",
            )
        )
        self.assertIn("POST /api/auth/login", text)   # target prominent (L1)
        self.assertIn("Security testing", text)        # friendly, not "active scan"
        self.assertNotIn("active scan", text)
        self.assertIn("40%", text)
        self.assertIn("1m 15s", text)
        self.assertNotIn("worker-2", text)             # worker is Level 4 (hidden)

    def test_completed_summarizes_findings_and_points_to_get_result(self):
        text = self.renderer.render(
            OperationProgress(
                "op1",
                LifecyclePhase.COMPLETED,
                title="API Security Scan",
                target="POST /api/auth/login",
                duration_seconds=42,
                findings=ScanFindings(critical=0, high=1, medium=3, low=8),
                reference="1D015005",
            )
        )
        self.assertIn("POST /api/auth/login", text)     # target always shown
        self.assertIn("Completed", text)
        self.assertIn("42s", text)
        self.assertIn("Critical 0 · High 1 · Medium 3 · Low 8", text)
        self.assertIn("Operation ID: op1", text)        # full id, never truncated
        self.assertIn("get-result", text)               # points user to retrieval
        self.assertNotIn("{", text)                     # no raw JSON

    def test_completed_includes_report_link_when_available(self):
        text = self.renderer.render(
            OperationProgress(
                "op1",
                LifecyclePhase.COMPLETED,
                title="API Security Scan",
                duration_seconds=42,
                findings=ScanFindings(high=1),
                report_link="https://example/report/op1",
            )
        )
        self.assertIn("Report", text)
        self.assertIn("https://example/report/op1", text)

    def test_completed_with_no_findings_omits_results_gracefully(self):
        text = self.renderer.render(
            OperationProgress(
                "op1",
                LifecyclePhase.COMPLETED,
                title="API Security Scan",
                findings=ScanFindings(),
            )
        )
        self.assertIn("No vulnerabilities found", text)

    def test_failed_is_concise_actionable_and_hides_traceback(self):
        text = self.renderer.render(
            OperationProgress(
                "api_scan:1d015005",
                LifecyclePhase.FAILED,
                title="API Security Scan",
                reason="Worker stopped responding\nTraceback (most recent call last):\n  File ...",
                failed_phase="active scan",
                reference="1D015005",
            )
        )
        self.assertIn("Failed", text)
        self.assertIn("Worker stopped responding", text)   # concise reason
        self.assertNotIn("Traceback", text)                # no stack traces
        self.assertIn("Operation #1D015005", text)         # short reference only
        self.assertNotIn("api_scan:1d015005", text)        # full id hidden by default

    def test_default_hides_all_level4_infrastructure(self):
        text = self.renderer.render(
            OperationProgress(
                "api_scan:1d015005",
                LifecyclePhase.RUNNING,
                stage="spider",
                worker_id="worker-2",
                reference="1D015005",
                debug={"Container": "zap-worker-3"},
            )
        )
        # Worker / container / debug AND the full operation id are all Level-4.
        for infra in ("worker-2", "zap-worker-3", "Debug", "api_scan:1d015005"):
            self.assertNotIn(infra, text)
        # Only a short, non-sensitive reference appears by default.
        self.assertIn("Operation #1D015005", text)


class RendererDebugModeTests(unittest.TestCase):
    def test_debug_mode_exposes_infrastructure_section(self):
        renderer = OperationNotificationRenderer(debug=True)
        text = renderer.render(
            OperationProgress(
                "api_scan:1d015005",
                LifecyclePhase.RUNNING,
                stage="active scan",
                worker_id="worker-2",
                debug={"Container": "zap-worker-3"},
            )
        )
        self.assertIn("Debug", text)
        self.assertIn("worker-2", text)
        self.assertIn("api_scan:1d015005", text)
        self.assertIn("Container", text)
        self.assertIn("zap-worker-3", text)


class HumanizeStageTests(unittest.TestCase):
    def test_maps_technical_stages_to_user_language(self):
        self.assertEqual(humanize_stage("initializing"), "Preparing scan")
        self.assertEqual(humanize_stage("spider"), "Discovering attack surface")
        self.assertEqual(humanize_stage("passive scan"), "Passive analysis")
        self.assertEqual(humanize_stage("active scan"), "Security testing")
        self.assertEqual(humanize_stage("report generation"), "Preparing report")

    def test_is_case_insensitive(self):
        self.assertEqual(humanize_stage("Active Scan"), "Security testing")

    def test_unknown_stage_passes_through(self):
        self.assertEqual(humanize_stage("fuzzing"), "fuzzing")
        self.assertIsNone(humanize_stage(None))


if __name__ == "__main__":
    unittest.main()
