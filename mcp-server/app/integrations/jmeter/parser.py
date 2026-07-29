"""JMeterParser — what the numbers are.

Skeleton: the interface is fixed; no parsing is implemented.

**What Parser owns:** reading a JTL file and producing
:class:`JMeterMetrics` plus the numeric parts of
:class:`JMeterExecutionSummary` — aggregation, percentiles, error rate,
throughput, and the per-label breakdown.

**What Parser does not own:** I/O beyond reading the files it is handed; the
database, the operation, the pool, or the network. It makes no judgment about
whether the values are good — that is the Analyzer's.

The point of that narrowness: the parser is a pure function from file to
numbers, so it is unit-testable against a fixture JTL with no JMeter, no worker
and no database. That is where the arithmetic bugs will actually be caught.
"""

from app.schemas.tools.jmeter.jmeter_test_result import (
    JMeterExecutionSummary,
    JMeterMetrics,
)


class JMeterParser:
    """Turns a JMeter JTL results file into the metrics section of the result."""

    def parse(self, jtl_path: str) -> tuple[JMeterExecutionSummary, JMeterMetrics]:
        """Read the JTL at *jtl_path* and aggregate it.

        Args:
            jtl_path: Path to the JTL (CSV) file JMeter wrote with ``-l``.

        Returns:
            The summary counts and the aggregate + per-label metrics.

        Raises:
            Exception: If the file is missing or not readable as a JTL. The
                caller (Runtime) turns that into a FAILED operation.
        """
        # TODO(Phase 2): read the JTL columns (timeStamp, elapsed, label,
        # success, bytes, sentBytes), aggregate overall and per label, and
        # compute min/max/mean/p50/p90/p95/p99, throughput and error rate.
        raise NotImplementedError
