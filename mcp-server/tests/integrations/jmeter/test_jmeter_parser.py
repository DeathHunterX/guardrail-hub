"""JMeterParser: the arithmetic, against fixture JTL files.

The parser is the one JMeter component that is a pure function — file in,
numbers out — so it is tested with no JMeter, no worker, no server and no
database. Every figure below is hand-computable from the fixture, which is the
point: if an aggregation is wrong, it is wrong here and visibly so.
"""

import tempfile
import unittest
from pathlib import Path

from app.integrations.jmeter.parser import JMeterParser, JMeterResultsFileError

_TARGET = "https://api.example.com/v1/orders"

_HEADER = (
    "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,"
    "success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,"
    "IdleTime,Connect"
)

#: All fixtures start here so timestamps stay readable as offsets.
_T0 = 1_700_000_000_000


def _row(
    *,
    offset_ms: int,
    elapsed_ms: int,
    label: str = "orders",
    success: bool = True,
    received_bytes: int = 1024,
    sent_bytes: int = 512,
) -> str:
    return (
        f"{_T0 + offset_ms},{elapsed_ms},{label},200,OK,tg 1-1,text,"
        f"{'true' if success else 'false'},,{received_bytes},{sent_bytes},"
        f"5,5,{_TARGET},{elapsed_ms},0,10"
    )


class _JtlFixture:
    """Writes a JTL into a temp directory for the lifetime of one test."""

    def __init__(self, *lines: str, header: str = _HEADER):
        self._dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self._dir.name) / "results.jtl")
        Path(self.path).write_text(
            "\n".join([header, *lines]) + "\n", encoding="utf-8"
        )

    def cleanup(self):
        self._dir.cleanup()


class _ParserTestCase(unittest.TestCase):
    def parse(self, *lines: str, header: str = _HEADER, target: str = _TARGET):
        fixture = _JtlFixture(*lines, header=header)
        self.addCleanup(fixture.cleanup)
        return JMeterParser().parse(fixture.path, target)


class LatencyTests(_ParserTestCase):
    """Ten samples of 10..100 ms — every percentile is checkable by hand."""

    def setUp(self):
        rows = [
            _row(offset_ms=index * 1000, elapsed_ms=(index + 1) * 10)
            for index in range(10)
        ]
        self.summary, self.metrics = self.parse(*rows)

    def test_min_max_and_mean(self):
        latency = self.metrics.latency
        self.assertEqual(10.0, latency.min_ms)
        self.assertEqual(100.0, latency.max_ms)
        self.assertEqual(55.0, latency.mean_ms)

    def test_percentiles_use_nearest_rank(self):
        # Nearest rank over [10..100]: p50 -> 5th value, p90 -> 9th,
        # p95/p99 -> 10th. Every one is a response time actually measured.
        latency = self.metrics.latency
        self.assertEqual(50.0, latency.p50_ms)
        self.assertEqual(90.0, latency.p90_ms)
        self.assertEqual(100.0, latency.p95_ms)
        self.assertEqual(100.0, latency.p99_ms)

    def test_duration_spans_first_start_to_last_finish(self):
        # First starts at 0ms, last starts at 9000ms and takes 100ms.
        self.assertEqual(9.1, self.summary.duration_seconds)

    def test_sample_count(self):
        self.assertEqual(10, self.summary.total_samples)


class ErrorRateTests(_ParserTestCase):
    def test_failed_samples_are_counted_and_expressed_as_a_percentage(self):
        rows = [
            _row(offset_ms=0, elapsed_ms=10),
            _row(offset_ms=1000, elapsed_ms=10, success=False),
            _row(offset_ms=2000, elapsed_ms=10, success=False),
            _row(offset_ms=3000, elapsed_ms=10),
        ]
        summary, _ = self.parse(*rows)

        self.assertEqual(4, summary.total_samples)
        self.assertEqual(2, summary.error_count)
        self.assertEqual(50.0, summary.error_rate_percent)

    def test_a_clean_run_reports_zero_percent(self):
        summary, _ = self.parse(_row(offset_ms=0, elapsed_ms=10))
        self.assertEqual(0, summary.error_count)
        self.assertEqual(0.0, summary.error_rate_percent)


class ThroughputTests(_ParserTestCase):
    def test_throughput_and_byte_rates_use_the_measured_window(self):
        # Two samples spanning exactly 2s: starts at 0 and 1000ms, the last
        # taking 1000ms. 2 samples / 2s = 1 rps.
        summary, metrics = self.parse(
            _row(offset_ms=0, elapsed_ms=100, received_bytes=1024, sent_bytes=512),
            _row(offset_ms=1000, elapsed_ms=1000, received_bytes=1024, sent_bytes=512),
        )

        self.assertEqual(2.0, summary.duration_seconds)
        self.assertEqual(1.0, metrics.throughput_rps)
        # 2048 bytes = 2 KB over 2s.
        self.assertEqual(1.0, metrics.received_kb_per_sec)
        self.assertEqual(0.5, metrics.sent_kb_per_sec)

    def test_a_single_instantaneous_sample_does_not_divide_by_zero(self):
        summary, metrics = self.parse(_row(offset_ms=0, elapsed_ms=0))
        self.assertEqual(0.0, summary.duration_seconds)
        self.assertEqual(0.0, metrics.throughput_rps)
        self.assertEqual(0.0, metrics.received_kb_per_sec)


class PerLabelTests(_ParserTestCase):
    def setUp(self):
        rows = [
            _row(offset_ms=0, elapsed_ms=10, label="orders"),
            _row(offset_ms=1000, elapsed_ms=30, label="checkout", success=False),
            _row(offset_ms=2000, elapsed_ms=50, label="orders"),
            _row(offset_ms=3000, elapsed_ms=70, label="checkout"),
        ]
        _, self.metrics = self.parse(*rows)
        self.by_label = {entry.label: entry for entry in self.metrics.labels}

    def test_every_sampler_label_gets_its_own_entry(self):
        self.assertEqual({"orders", "checkout"}, set(self.by_label))

    def test_labels_keep_the_order_they_first_appear_in(self):
        self.assertEqual(["orders", "checkout"], [e.label for e in self.metrics.labels])

    def test_counts_and_latency_are_scoped_to_the_label(self):
        orders = self.by_label["orders"]
        self.assertEqual(2, orders.sample_count)
        self.assertEqual(0, orders.error_count)
        self.assertEqual(10.0, orders.latency.min_ms)
        self.assertEqual(50.0, orders.latency.max_ms)

    def test_error_rate_is_scoped_to_the_label_not_the_run(self):
        # checkout failed 1 of its own 2 samples: 50%, even though the run as a
        # whole is 25%.
        self.assertEqual(50.0, self.by_label["checkout"].error_rate_percent)

    def test_label_throughput_uses_that_labels_own_window(self):
        # orders ran from 0ms to 2050ms -> 2.05s for 2 samples.
        self.assertEqual(round(2 / 2.05, 4), self.by_label["orders"].throughput_rps)


class EmptyAndPartialFileTests(_ParserTestCase):
    def test_a_header_only_jtl_parses_to_zeros_rather_than_failing(self):
        # A run that started and was stopped before its first sample completed
        # is a real, if useless, outcome — not a parse error.
        summary, metrics = self.parse()

        self.assertEqual(0, summary.total_samples)
        self.assertEqual(0.0, summary.error_rate_percent)
        self.assertEqual(0.0, summary.duration_seconds)
        self.assertEqual(0.0, metrics.latency.p99_ms)
        self.assertEqual([], metrics.labels)

    def test_a_truncated_final_row_is_skipped_not_fatal(self):
        # SIGTERM mid-write leaves a half-line. The samples before it are still
        # worth keeping — that is the whole reason cancellation uses SIGTERM.
        summary, _ = self.parse(
            _row(offset_ms=0, elapsed_ms=10),
            _row(offset_ms=1000, elapsed_ms=20),
            "1700000002000,notanumber",
        )
        self.assertEqual(2, summary.total_samples)

    def test_missing_byte_columns_default_to_zero(self):
        summary, metrics = self.parse(
            "1700000000000,100,orders,true",
            header="timeStamp,elapsed,label,success",
        )
        self.assertEqual(1, summary.total_samples)
        self.assertEqual(0.0, metrics.received_kb_per_sec)


class UnreadableFileTests(_ParserTestCase):
    def test_a_missing_results_file_is_reported_clearly(self):
        with self.assertRaises(JMeterResultsFileError) as raised:
            JMeterParser().parse("/nonexistent/results.jtl", _TARGET)
        self.assertIn("Could not read", str(raised.exception))

    def test_a_csv_that_is_not_a_jtl_is_rejected_by_its_header(self):
        # Guards against a saveservice config drift silently yielding zeros.
        with self.assertRaises(JMeterResultsFileError) as raised:
            self.parse("1,2,3", header="alpha,beta,gamma")
        self.assertIn("not a JMeter CSV results file", str(raised.exception))


class SummaryContractTests(_ParserTestCase):
    def test_target_url_is_echoed_from_the_request_not_the_jtl(self):
        # The JTL records sampler labels, not the request that authorized them,
        # so this one summary field has to be passed in.
        summary, _ = self.parse(_row(offset_ms=0, elapsed_ms=10))
        self.assertEqual(_TARGET, summary.target_url)

    def test_the_parser_reports_no_verdict_of_any_kind(self):
        # Task 7's boundary: extract structured data, never evaluate it. If a
        # pass/fail, threshold or recommendation field ever appears on these
        # models, it was added on the wrong side of the Parser/Analyzer line.
        summary, metrics = self.parse(_row(offset_ms=0, elapsed_ms=10))
        forbidden = {
            "sla", "sla_status", "passed", "verdict", "threshold", "thresholds",
            "recommendation", "recommendations", "insight", "insights", "rating",
        }
        self.assertEqual(set(), forbidden & set(summary.model_dump()))
        self.assertEqual(set(), forbidden & set(metrics.model_dump()))


if __name__ == "__main__":
    unittest.main()
