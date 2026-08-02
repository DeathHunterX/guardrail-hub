"""The run package: self-descriptive filenames, execution.json, summary.html.

What these lock down is that a completed run's directory can be zipped, mailed
and opened six months later by someone who was not there — which is the only
reason any of it exists.
"""

import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.integrations.jmeter.process import JMeterProcessRunner
from app.schemas.tools.jmeter.jmeter_test_result import (
    JMeterExecutionSummary,
    JMeterLatency,
    JMeterMetrics,
)
from app.schemas.tools.jmeter.run_jmeter_test import JMeterHttpMethod, JMeterTestRequest
from app.schemas.tools.jmeter.worker import JMeterWorkerInfo
from app.services.tools.jmeter.execution.artifact_package import (
    EXECUTION_METADATA_FILE,
    SUMMARY_PAGE_FILE,
    JMeterArtifactPackageWriter,
)

_WORKER = JMeterWorkerInfo(
    worker_id="jmeter-3", hostname="jmeter-3", endpoint="http://jmeter-3:8090", port=8090
)
_STARTED = datetime(2026, 7, 31, 9, 0, tzinfo=timezone.utc)
_FINISHED = datetime(2026, 7, 31, 9, 5, tzinfo=timezone.utc)


def _request(**overrides) -> JMeterTestRequest:
    fields = {
        "target_url": "https://api.example.com/v1/orders",
        "method": JMeterHttpMethod.POST,
        "thread_count": 20,
        "ramp_up_seconds": 10,
        "hold_seconds": 60,
    }
    fields.update(overrides)
    return JMeterTestRequest(**fields)


def _summary() -> JMeterExecutionSummary:
    return JMeterExecutionSummary(
        target_url="https://api.example.com/v1/orders",
        total_samples=12480,
        error_count=37,
        error_rate_percent=0.2965,
        duration_seconds=70.2,
    )


def _metrics() -> JMeterMetrics:
    return JMeterMetrics(
        latency=JMeterLatency(
            min_ms=12.0, max_ms=1840.0, mean_ms=88.4,
            p50_ms=71.0, p90_ms=160.0, p95_ms=214.0, p99_ms=903.0,
        ),
        throughput_rps=177.8,
        received_kb_per_sec=402.5,
        sent_kb_per_sec=25.1,
    )


class ArtifactFilenameTests(unittest.TestCase):
    """The physical names are self-descriptive; the JSON keys did not change."""

    def test_filenames_describe_their_content(self):
        self.assertEqual("test-plan.jmx", JMeterProcessRunner.PLAN_FILE)
        self.assertEqual("test-results.jtl", JMeterProcessRunner.RESULTS_FILE)
        self.assertEqual("engine.log", JMeterProcessRunner.ENGINE_LOG)
        self.assertEqual("html-report", JMeterProcessRunner.REPORT_DIR)

    def test_the_jmeter_command_line_uses_the_new_names(self):
        runner = JMeterProcessRunner(binary="jmeter")
        command = " ".join(runner._build_command(Path("/tmp/ws")))

        self.assertIn("/tmp/ws/test-plan.jmx", command)
        self.assertIn("/tmp/ws/test-results.jtl", command)
        self.assertIn("/tmp/ws/html-report", command)
        self.assertIn("/tmp/ws/engine.log", command)


class _PackageTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.workspace = self._dir.name

    def write(self, **overrides):
        fields = {
            "workspace": self.workspace,
            "operation_id": "op-42",
            "request": _request(),
            "worker": _WORKER,
            "started_at": _STARTED,
            "finished_at": _FINISHED,
        }
        fields.update(overrides)
        JMeterArtifactPackageWriter().write(**fields)

    def metadata(self) -> dict:
        return json.loads(
            Path(self.workspace, EXECUTION_METADATA_FILE).read_text(encoding="utf-8")
        )

    def summary(self) -> str:
        return Path(self.workspace, SUMMARY_PAGE_FILE).read_text(encoding="utf-8")


class ExecutionMetadataTests(_PackageTestCase):
    def setUp(self):
        super().setUp()
        self.write()

    def test_the_file_is_written_beside_the_artifacts(self):
        self.assertTrue(Path(self.workspace, EXECUTION_METADATA_FILE).exists())

    def test_it_identifies_the_run(self):
        data = self.metadata()
        self.assertEqual("op-42", data["operation_id"])
        self.assertEqual("completed", data["status"])

    def test_it_records_the_target_and_method(self):
        target = self.metadata()["target"]
        self.assertEqual("https://api.example.com/v1/orders", target["url"])
        self.assertEqual("POST", target["method"])

    def test_it_records_the_load_profile(self):
        execution = self.metadata()["execution"]
        self.assertEqual(
            {"thread_count": 20, "ramp_up_seconds": 10, "hold_seconds": 60}, execution
        )

    def test_it_records_the_worker_and_the_time_window(self):
        worker = self.metadata()["worker"]
        self.assertEqual("jmeter-3", worker["worker_id"])
        self.assertEqual("2026-07-31T09:00:00Z", worker["started_at"])
        self.assertEqual("2026-07-31T09:05:00Z", worker["finished_at"])

    def test_it_carries_no_metrics(self):
        """Metadata only — metrics have three homes already, and a fourth copy
        is a fourth chance to disagree with the other three."""
        blob = json.dumps(self.metadata()).lower()
        for metric in (
            "latency", "throughput", "percentile", "p50", "p95", "p99",
            "error_rate", "sample", "total_samples", "min_ms", "max_ms",
        ):
            self.assertNotIn(metric, blob, f"metric leaked into metadata: {metric}")

    def test_the_top_level_shape_is_exactly_the_agreed_one(self):
        self.assertEqual(
            {"operation_id", "status", "target", "execution", "worker"},
            set(self.metadata()),
        )


class SummaryPageTests(_PackageTestCase):
    def setUp(self):
        super().setUp()
        self.write()
        self.page = self.summary()

    def test_the_page_is_written_beside_the_artifacts(self):
        self.assertTrue(Path(self.workspace, SUMMARY_PAGE_FILE).exists())
        self.assertTrue(self.page.lstrip().startswith("<!DOCTYPE html>"))

    def test_every_required_field_is_displayed(self):
        for expected in (
            "op-42",                                  # Operation ID
            "completed",                              # Status
            "https://api.example.com/v1/orders",      # Target URL
            "POST",                                   # HTTP Method
            "20 concurrent threads",                  # Thread Count
            "10s",                                    # Ramp-up
            "60s",                                    # Hold Time
            "jmeter-3",                               # Worker ID
            "2026-07-31T09:00:00Z",                   # Started At
            "2026-07-31T09:05:00Z",                   # Finished At
        ):
            self.assertIn(expected, self.page, f"missing from summary: {expected}")

    def test_it_links_to_every_artifact(self):
        for label, href in (
            ("Open Dashboard", "html-report/index.html"),
            ("Open Test Plan", "test-plan.jmx"),
            ("Open Engine Log", "engine.log"),
            ("Open Raw Results", "test-results.jtl"),
        ):
            self.assertIn(label, self.page)
            self.assertIn(f'href="{href}"', self.page)

    def test_it_offers_the_dashboard_button(self):
        self.assertIn("Open JMeter Dashboard", self.page)
        self.assertIn('class="cta" href="html-report/index.html"', self.page)

    def test_links_are_relative_so_the_package_survives_being_copied(self):
        # An absolute link would tie the package to the host that produced it,
        # defeating the point of making it self-contained.
        self.assertNotIn('href="http://', self.page)
        self.assertNotIn('href="/', self.page)

    def test_a_hostile_target_url_cannot_inject_script(self):
        # target_url is caller-supplied text rendered into a page a human opens.
        self.write(
            request=_request(target_url="https://evil.example.com/<script>alert(1)</script>")
        )
        page = self.summary()
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_the_page_reports_what_it_generated_and_what_it_did_not(self):
        self.assertIn("Guardrail Hub", self.page)
        self.assertIn("left untouched", self.page)


class VendorDashboardTests(_PackageTestCase):
    """Nothing in the package writer may touch JMeter's own output."""

    def test_the_generated_dashboard_is_left_byte_identical(self):
        report_dir = Path(self.workspace, JMeterProcessRunner.REPORT_DIR)
        report_dir.mkdir()
        index = report_dir / "index.html"
        original = "<html><body>JMeter's own dashboard</body></html>"
        index.write_text(original, encoding="utf-8")
        stats = report_dir / "statistics.json"
        stats.write_text('{"Total": {}}', encoding="utf-8")

        self.write()

        self.assertEqual(original, index.read_text(encoding="utf-8"))
        self.assertEqual('{"Total": {}}', stats.read_text(encoding="utf-8"))

    def test_nothing_new_is_created_inside_the_dashboard_directory(self):
        report_dir = Path(self.workspace, JMeterProcessRunner.REPORT_DIR)
        report_dir.mkdir()
        (report_dir / "index.html").write_text("x", encoding="utf-8")

        self.write()

        self.assertEqual(["index.html"], sorted(p.name for p in report_dir.iterdir()))

    def test_our_files_sit_beside_the_dashboard_not_inside_it(self):
        self.write()
        names = sorted(p.name for p in Path(self.workspace).iterdir())
        self.assertEqual([EXECUTION_METADATA_FILE, SUMMARY_PAGE_FILE], names)


class SummarySectionTests(_PackageTestCase):
    """The headline numbers, rendered from the parsed figures."""

    def setUp(self):
        super().setUp()
        self.write(summary=_summary(), metrics=_metrics())
        self.page = self.summary()

    def test_the_page_carries_the_four_prescribed_sections(self):
        for heading in (
            "Execution Information",
            "Test Configuration",
            "Summary",
            "Available Artifacts",
        ):
            self.assertIn(f"<h2>{heading}</h2>", self.page)

    def test_every_headline_figure_is_shown(self):
        for label, value in (
            ("Total Samples", "12,480"),
            ("Error Count", "37"),
            ("Error Rate", "0.2965%"),
            ("Throughput", "177.8 requests/second"),
            ("Mean Latency", "88.4 ms"),
            ("p95", "214 ms"),
            ("p99", "903 ms"),
        ):
            self.assertIn(f"<th>{label}</th><td>{value}</td>", self.page)

    def test_duration_is_derived_from_the_displayed_timestamps(self):
        # 09:00:00Z -> 09:05:00Z. A Duration that disagreed with the Started and
        # Finished rows directly above it would be a bug report waiting to happen.
        self.assertIn("<th>Duration</th><td>5m 0s</td>", self.page)

    def test_a_sub_minute_run_reads_in_seconds(self):
        self.write(
            finished_at=datetime(2026, 7, 31, 9, 0, 43, tzinfo=timezone.utc),
            summary=_summary(),
            metrics=_metrics(),
        )
        self.assertIn("<th>Duration</th><td>43s</td>", self.summary())

    def test_unreadable_timestamps_say_unknown_rather_than_lying(self):
        page = JMeterArtifactPackageWriter._summary_page(
            {
                "operation_id": "op-1", "status": "completed",
                "target": {"url": "https://x", "method": "GET"},
                "execution": {"thread_count": 1, "ramp_up_seconds": 0, "hold_seconds": 1},
                "worker": {"worker_id": "w", "started_at": "not-a-date",
                           "finished_at": "also-not"},
            },
            None,
            None,
        )
        self.assertIn("<th>Duration</th><td>unknown</td>", page)


class DegradedSummarySectionTests(_PackageTestCase):
    """No parsed figures: the page says why, and never shows zeros."""

    def setUp(self):
        super().setUp()
        self.write(summary=None, metrics=None)
        self.page = self.summary()

    def test_it_explains_that_the_load_still_happened(self):
        self.assertIn("could not be read back", self.page)
        self.assertIn("the missing numbers describe the recording, not the run", self.page)

    def test_it_does_not_render_a_zero_filled_table(self):
        # Zeros here would read as "the target was never touched".
        for label in ("Total Samples", "Error Rate", "Throughput", "p95", "p99"):
            self.assertNotIn(f"<th>{label}</th>", self.page)

    def test_the_rest_of_the_package_is_unaffected(self):
        self.assertIn("<th>Operation ID</th><td>op-42</td>", self.page)
        self.assertIn('href="html-report/index.html"', self.page)


class ArtifactListTests(_PackageTestCase):
    def setUp(self):
        super().setUp()
        self.write(summary=_summary(), metrics=_metrics())
        self.page = self.summary()

    def test_all_five_artifacts_are_listed(self):
        for label, href in (
            ("Open Dashboard", "html-report/index.html"),
            ("Open Engine Log", "engine.log"),
            ("Open Test Plan", "test-plan.jmx"),
            ("Open Raw Results", "test-results.jtl"),
            ("Open execution.json", EXECUTION_METADATA_FILE),
        ):
            self.assertIn(label, self.page)
            self.assertIn(f'href="{href}"', self.page)

    def test_no_link_names_a_host(self):
        # Hardcoding a hostname would break the package the moment it is copied
        # anywhere, which is the whole thing the package is for.
        for href in re.findall(r'href="([^"]+)"', self.page):
            self.assertFalse(href.startswith(("http://", "https://", "//", "/")), href)

    def test_a_hostile_value_is_escaped_even_beside_the_metrics(self):
        self.write(
            request=_request(target_url="https://evil.example.com/<script>alert(1)</script>"),
            summary=_summary(), metrics=_metrics(),
        )
        page = self.summary()
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)


class ResilienceTests(unittest.TestCase):
    def test_an_unwritable_workspace_does_not_raise(self):
        """A convenience layered on a run that already succeeded must never be
        able to turn a completed load test into a failed operation."""
        JMeterArtifactPackageWriter().write(
            workspace="/nonexistent/directory/that/does/not/exist",
            operation_id="op-1",
            request=_request(),
            worker=_WORKER,
            started_at=_STARTED,
            finished_at=_FINISHED,
        )  # must not raise


if __name__ == "__main__":
    unittest.main()
