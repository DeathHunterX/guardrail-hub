"""JMeterAnalyzer: reading a persisted result, and refusing to do anything else.

The analyzer's only input is ``operation.result``, so every test here builds a
record by hand and hands it over through a fake DAO. There is no JMeter, no
worker, no runtime and no filesystem in this file — which is itself the point:
if the analyzer ever needed one of those, these tests could not be written this
way, and that is the boundary they protect.
"""

import unittest
from datetime import datetime, timezone

from app.constants.batch import BatchType
from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase
from app.schemas.tools.jmeter.jmeter_test_result import (
    JMeterArtifacts,
    JMeterExecutionMetadata,
    JMeterExecutionSummary,
    JMeterLabelMetrics,
    JMeterLatency,
    JMeterMetrics,
    JMeterTestResult,
)
from app.services.tools.jmeter import JMeterAnalyzer

_OP = "op-1"
_TARGET = "https://api.example.com/v1/orders"


def _latency(p50=100.0, p95=200.0) -> JMeterLatency:
    return JMeterLatency(
        min_ms=50.0,
        max_ms=400.0,
        mean_ms=120.0,
        p50_ms=p50,
        p90_ms=180.0,
        p95_ms=p95,
        p99_ms=350.0,
    )


def _metadata() -> JMeterExecutionMetadata:
    return JMeterExecutionMetadata(
        worker_id="jmeter-1",
        started_at=datetime(2026, 7, 29, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 29, 10, 5, tzinfo=timezone.utc),
        thread_count=50,
        ramp_up_seconds=30,
        hold_seconds=240,
    )


def _artifacts() -> JMeterArtifacts:
    base = f"/public/report/jmeter/detail-report/{_OP}"
    return JMeterArtifacts(
        view_report=f"{base}/report/index.html",
        results_data=f"{base}/results.jtl",
        test_plan=f"{base}/plan.jmx",
        engine_log=f"{base}/jmeter.log",
    )


def _result(*, summary=True, metrics=True, labels=None, **summary_overrides):
    """A persisted result, with either derived section optionally removed."""
    summary_fields = {
        "target_url": _TARGET,
        "total_samples": 1000,
        "error_count": 20,
        "error_rate_percent": 2.0,
        "duration_seconds": 270.0,
    }
    summary_fields.update(summary_overrides)
    return JMeterTestResult(
        operation_id=_OP,
        summary=JMeterExecutionSummary(**summary_fields) if summary else None,
        metrics=(
            JMeterMetrics(
                latency=_latency(),
                throughput_rps=3.7,
                received_kb_per_sec=48.5,
                sent_kb_per_sec=12.25,
                labels=labels if labels is not None else [],
            )
            if metrics
            else None
        ),
        artifacts=_artifacts(),
        metadata=_metadata(),
    )


def _record(
    *,
    status=OperationPhase.COMPLETED,
    batch_type=BatchType.JMETER_TEST,
    result=None,
    error=None,
) -> OperationRecord:
    return OperationRecord(
        operation_id=_OP,
        status=status,
        batch_type=batch_type,
        result=result,
        error=error,
    )


class _FakeDAO:
    """A read-only stand-in that also records every call made against it."""

    def __init__(self, record=None):
        self._record = record
        self.reads = []
        self.writes = []

    def get_operation(self, operation_id):
        self.reads.append(operation_id)
        return self._record if self._record else None

    def __getattr__(self, name):
        # Any method other than get_operation is a boundary violation. Record
        # the attempt instead of raising, so the assertion names the method.
        def _recorder(*args, **kwargs):
            self.writes.append(name)

        return _recorder


def _analyze(record):
    dao = _FakeDAO(record)
    return JMeterAnalyzer(operation_dao=dao).analyze_jmeter_result(_OP), dao


class SuccessfulAnalysisTests(unittest.TestCase):
    def setUp(self):
        result = _result(
            labels=[
                JMeterLabelMetrics(
                    label="orders",
                    sample_count=600,
                    error_count=0,
                    error_rate_percent=0.0,
                    latency=_latency(p50=80.0, p95=150.0),
                    throughput_rps=2.2,
                ),
                JMeterLabelMetrics(
                    label="checkout",
                    sample_count=400,
                    error_count=20,
                    error_rate_percent=5.0,
                    latency=_latency(p50=260.0, p95=500.0),
                    throughput_rps=1.5,
                ),
            ]
        )
        self.response, _ = _analyze(
            _record(result=result.model_dump(mode="json", by_alias=True))
        )

    def test_the_headline_reports_target_load_and_the_core_figures(self):
        summary = self.response.summary
        self.assertIn(_TARGET, summary)
        self.assertIn("50 concurrent threads", summary)
        self.assertIn("1,000 samples", summary)
        self.assertIn("2%", summary)

    def test_latency_percentiles_are_all_reported(self):
        for expected in ("p50 100 ms", "p90 180 ms", "p95 200 ms", "p99 350 ms"):
            self.assertIn(expected, self.response.details)

    def test_throughput_is_reported(self):
        self.assertIn("3.7 requests/second", self.response.details)
        self.assertIn("48.5 KB/s received", self.response.details)

    def test_error_rate_is_reported(self):
        self.assertIn("20 of 1,000 samples failed", self.response.details)

    def test_every_sampler_label_appears_in_the_breakdown(self):
        self.assertIn("orders —", self.response.details)
        self.assertIn("checkout —", self.response.details)

    def test_the_slowest_label_is_named_by_measured_median(self):
        self.assertIn("Highest median response time: checkout", self.response.details)

    def test_artifacts_are_linked_not_reopened(self):
        self.assertIn("results.jtl", self.response.details)
        self.assertIn("index.html", self.response.details)

    def test_the_response_is_deterministic(self):
        # Same record in, same words out — no clock, no randomness, no model.
        result = _result()
        record = _record(result=result.model_dump(mode="json", by_alias=True))
        first, _ = _analyze(record)
        second, _ = _analyze(record)
        self.assertEqual(first.summary, second.summary)
        self.assertEqual(first.details, second.details)


class PercentileInterpretationTests(unittest.TestCase):
    """The spread sentence describes shape; it never grades the run."""

    def _details_for(self, p50, p95):
        result = _result()
        result.metrics.latency = _latency(p50=p50, p95=p95)
        response, _ = _analyze(
            _record(result=result.model_dump(mode="json", by_alias=True))
        )
        return response.details

    def test_a_wide_spread_is_described_as_a_long_tail(self):
        details = self._details_for(p50=100.0, p95=500.0)
        self.assertIn("p95 is 5.0x the median", details)
        self.assertIn("took substantially longer", details)

    def test_a_narrow_spread_is_described_as_close_to_typical(self):
        details = self._details_for(p50=100.0, p95=120.0)
        self.assertIn("p95 is 1.2x the median", details)
        self.assertIn("close to the typical one", details)

    def test_a_zero_median_does_not_divide_by_zero(self):
        details = self._details_for(p50=0.0, p95=0.0)
        self.assertIn("cannot be expressed as a ratio", details)

    def test_no_verdict_vocabulary_appears_anywhere(self):
        # The Parser/Analyzer line allows description and forbids judgment.
        # These words are how judgment would show up if it ever crept in.
        details = self._details_for(p50=100.0, p95=900.0).lower()
        for forbidden in (
            "should", "recommend", "too slow", "unacceptable", "acceptable",
            "pass", "fail the", "sla", "threshold", "poor", "good performance",
            "optimi",
        ):
            self.assertNotIn(forbidden, details, f"judgment leaked in: {forbidden!r}")


class ParserDegradedTests(unittest.TestCase):
    """Completed, but the results file could not be read back."""

    def setUp(self):
        result = _result(summary=False, metrics=False)
        self.response, _ = _analyze(
            _record(result=result.model_dump(mode="json", by_alias=True))
        )

    def test_it_says_the_run_happened_not_that_it_failed(self):
        # The load was generated. Absent numbers describe the recording, not the
        # run — conflating the two would tell the reader the target was spared.
        self.assertIn("ran to completion", self.response.summary)
        self.assertIn("could not be read back", self.response.summary)
        self.assertNotIn("did not complete", self.response.summary)

    def test_execution_metadata_is_still_returned(self):
        self.assertIn("jmeter-1", self.response.details)
        self.assertIn("50 threads", self.response.details)

    def test_artifacts_are_still_returned(self):
        self.assertIn("results.jtl", self.response.details)

    def test_no_metrics_are_invented(self):
        self.assertIn("No latency, throughput or error-rate figures", self.response.details)
        self.assertNotIn("Percentiles", self.response.details)

    def test_one_missing_section_is_enough_to_count_as_degraded(self):
        # summary present, metrics absent: reporting half a reading would imply
        # the other half was measured and found empty.
        result = _result(metrics=False)
        response, _ = _analyze(
            _record(result=result.model_dump(mode="json", by_alias=True))
        )
        self.assertIn("could not be read back", response.summary)


class UnsuccessfulOperationTests(unittest.TestCase):
    def test_a_failed_operation_quotes_its_recorded_reason(self):
        response, _ = _analyze(
            _record(status=OperationPhase.FAILED, error="Worker declined the assignment")
        )
        self.assertIn("did not complete", response.summary)
        self.assertIn("Worker declined the assignment", response.details)

    def test_a_failed_operation_without_a_reason_says_so(self):
        response, _ = _analyze(_record(status=OperationPhase.FAILED))
        self.assertIn("No reason was recorded", response.details)

    def test_a_cancelled_operation_is_reported_as_terminal_not_pending(self):
        response, _ = _analyze(_record(status=OperationPhase.CANCELLED))
        self.assertIn("ended as cancelled", response.summary)

    def test_a_running_operation_is_reported_as_unfinished(self):
        response, _ = _analyze(_record(status=OperationPhase.RUNNING))
        self.assertIn("has not finished", response.summary)
        self.assertIsNone(response.details)

    def test_a_queued_operation_is_reported_as_unfinished(self):
        response, _ = _analyze(_record(status=OperationPhase.QUEUED))
        self.assertIn("has not finished", response.summary)


class IncompletePersistedResultTests(unittest.TestCase):
    def test_a_completed_operation_with_no_result_is_reported_not_crashed(self):
        response, _ = _analyze(_record(result=None))
        self.assertIn("cannot be read", response.summary)

    def test_a_result_that_does_not_match_the_contract_is_reported_not_crashed(self):
        response, _ = _analyze(_record(result={"unexpected": "shape"}))
        self.assertIn("cannot be read", response.summary)

    def test_nothing_is_concluded_from_an_unreadable_record(self):
        response, _ = _analyze(_record(result={"unexpected": "shape"}))
        self.assertIn("Nothing can be concluded", response.details)


class OwnershipAndLookupTests(unittest.TestCase):
    def test_a_missing_operation_raises_lookup_error(self):
        # The router turns LookupError into a 404.
        analyzer = JMeterAnalyzer(operation_dao=_FakeDAO(None))
        with self.assertRaises(LookupError) as raised:
            analyzer.analyze_jmeter_result("nope")
        self.assertIn("No operation found", str(raised.exception))

    def test_a_zap_operation_is_refused_by_the_queue_lane_field(self):
        with self.assertRaises(LookupError) as raised:
            _analyze(_record(batch_type=BatchType.API_SCAN))
        self.assertIn("not a JMeter load test", str(raised.exception))

    def test_ownership_uses_the_same_lane_constant_the_dispatcher_uses(self):
        self.assertTrue(JMeterAnalyzer._is_jmeter_operation(BatchType.JMETER_TEST))
        self.assertFalse(JMeterAnalyzer._is_jmeter_operation(BatchType.API_SCAN))


class ReadOnlyBoundaryTests(unittest.TestCase):
    """The analyzer reads one record and writes nothing, ever."""

    def test_analysis_performs_exactly_one_read_and_no_writes(self):
        result = _result()
        _, dao = _analyze(_record(result=result.model_dump(mode="json", by_alias=True)))

        self.assertEqual([_OP], dao.reads)
        self.assertEqual([], dao.writes)

    def test_the_persisted_result_is_not_mutated_by_being_analyzed(self):
        stored = _result().model_dump(mode="json", by_alias=True)
        before = dict(stored)

        _analyze(_record(result=stored))

        self.assertEqual(before, stored)

    def test_the_analyzer_takes_no_execution_dependencies(self):
        # No runtime, no pool, no process runner, no parser: if any of these
        # could be injected, execution would have moved into the analyzer.
        import inspect

        params = set(inspect.signature(JMeterAnalyzer.__init__).parameters)
        self.assertEqual(
            set(),
            params
            & {"runtime", "pool_manager", "runner", "parser", "worker", "client"},
        )


if __name__ == "__main__":
    unittest.main()
