"""JMeterAnalyzer — what the numbers mean.

Skeleton: the interface and its hard boundary are fixed; the interpretation is
Phase 2.

**What Analyzer owns:** backing the ``analyze_jmeter_result`` MCP tool. It loads
the persisted operation, confirms the operation is a JMeter one, handles the
FAILED case from the record's own status and error, and turns the stored
:class:`JMeterTestResult` into a human-readable reading.

**What Analyzer must never do:** re-open the JTL or the HTML report, recompute
any metric, re-run anything, or touch the worker pool. Its only input is
``operation.result``.

That last rule is load-bearing rather than stylistic: if the analyzer needs a
number, the number must be produced by the Parser and added to the result
contract (ADR-0010). "The analyzer will just read the JTL" is the boundary
violation this class exists to prevent.
"""

from typing import Optional

from app.constants.batch import BatchType
from app.core.mcp_logger import MCPLogger
from app.dao.base import BaseOperationDAO
from app.schemas.tools.jmeter.run_jmeter_test import JMeterResultAnalysisResponse


class JMeterAnalyzer:
    """Interprets a completed JMeter operation's persisted result."""

    def __init__(
        self,
        operation_dao: Optional[BaseOperationDAO] = None,
        logger: Optional[MCPLogger] = None,
    ) -> None:
        """
        Args:
            operation_dao: Read-only access to the persisted operation record.
                Resolved from the configured database provider when not
                injected, matching how ``JMeterTestService`` self-wires.
            logger: Optional logger; one is created if omitted.
        """
        if operation_dao is None:
            # Imported lazily so constructing this service does not select a
            # database provider at module import time.
            from app.dao.operation_dao import get_operation_dao  # noqa: PLC0415

            operation_dao = get_operation_dao()
        self._operation_dao = operation_dao
        self._logger = logger or MCPLogger("JMeterAnalyzer")

    def analyze_jmeter_result(
        self, operation_id: str
    ) -> JMeterResultAnalysisResponse:
        """Interpret the stored result of *operation_id*.

        Named for the ``analyze_jmeter_result`` tool it backs. Not an ``init_*``
        method: it answers synchronously and starts no operation.

        Ownership is checked with the same field that isolates the queue lane:
        ``record.batch_type in BatchType.ALL_JMETER_TYPES``. No second mechanism
        is needed, and asking an analyzer to read another tool's operation is a
        client error, not a crash.
        """
        # TODO(Phase 2): load the record, reject a non-JMeter or missing
        # operation, short-circuit FAILED/QUEUED/RUNNING from record.status,
        # then read JMeterTestResult from record.result and describe it.
        raise NotImplementedError

    @staticmethod
    def _is_jmeter_operation(batch_type: str) -> bool:
        """Whether a persisted operation belongs to this tool."""
        return batch_type in BatchType.ALL_JMETER_TYPES
