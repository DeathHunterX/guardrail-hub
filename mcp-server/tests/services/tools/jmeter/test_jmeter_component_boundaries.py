"""Component boundary tests for the JMeter module.

No runtime behaviour is asserted — none is implemented. What these do assert is
that every module imports cleanly and still exposes the interface the accepted
architecture fixed, so a rename or a dropped method is caught here rather than
in Phase 2. They also keep the module out of "dead code": every file below is
reachable and exercised.

They deliberately do NOT assert that methods raise NotImplementedError. That
would have to be deleted the moment each one is implemented, which is churn
disguised as coverage.
"""

import inspect
import unittest

from app.constants.batch import BatchType
from app.integrations.jmeter.parser import JMeterParser
from app.integrations.jmeter.worker import JMeterWorker
from app.services.tools.jmeter.analyze_jmeter_result_service import JMeterAnalyzer
from app.services.tools.jmeter.execution.dispatcher import JMeterDispatcher
from app.services.tools.jmeter.execution.runtime import JMeterRuntime


def _exposes_callables(cls, *method_names: str) -> bool:
    """Whether *cls* exposes every one of *method_names* as a callable."""
    return all(callable(getattr(cls, name, None)) for name in method_names)


class RuntimeBoundaryTests(unittest.TestCase):
    """JMeterRuntime owns the pipeline, and only the pipeline."""

    def test_exposes_the_five_pipeline_phases(self):
        self.assertTrue(
            _exposes_callables(
                JMeterRuntime,
                "run",
                "_generate_plan",
                "_validate_plan",
                "_execute_on_worker",
                "_parse_results",
                "_persist_result",
            )
        )

    def test_run_takes_an_already_assigned_worker(self):
        # Runtime does no scheduling: the worker arrives as an argument.
        params = inspect.signature(JMeterRuntime.run).parameters
        self.assertIn("worker", params)
        self.assertIn("operation_id", params)


class DispatcherBoundaryTests(unittest.TestCase):
    """JMeterDispatcher owns when work starts, and consumes only its lane."""

    def test_lane_is_the_jmeter_lane(self):
        self.assertEqual(BatchType.ALL_JMETER_TYPES, JMeterDispatcher.LANE)

    def test_lane_does_not_overlap_the_zap_lane(self):
        self.assertFalse(JMeterDispatcher.LANE & BatchType.ALL_SCAN_TYPES)

    def test_exposes_start_stop_and_a_poll_tick(self):
        self.assertTrue(
            _exposes_callables(
                JMeterDispatcher, "start", "stop", "_dispatch_queued_operations"
            )
        )


class WorkerBoundaryTests(unittest.TestCase):
    """JMeterWorker owns the assignment and the process, nothing persistent.

    Registration and heartbeat are deliberately **not** on this class. They live
    in ``docker/jmeter/register-worker.sh``, mirroring how a ZAP worker
    announces itself — the container's sidecar registers, the application code
    only executes. That keeps the agent process free of any server-lifecycle
    concern, which is the boundary these tests exist to protect.
    """

    def test_exposes_the_assignment_lifecycle(self):
        self.assertTrue(
            _exposes_callables(JMeterWorker, "accept", "report_for", "cancel")
        )

    def test_does_not_take_persistence_dependencies(self):
        # The worker never touches the Operations table, the DAO, or
        # OperationService — that boundary is checked at the constructor.
        params = set(inspect.signature(JMeterWorker.__init__).parameters)
        self.assertEqual(set(), params & {"operation_service", "operation_dao", "dao"})


class ParserBoundaryTests(unittest.TestCase):
    """JMeterParser is a pure file-to-numbers step."""

    def test_parse_takes_a_results_path_and_the_target_it_describes(self):
        """Plain data in, numbers out — no operation, no DAO, no pool.

        Phase 1 guessed this signature as ``(jtl_path)`` alone. Implementing the
        parser added ``target_url``, because ``JMeterExecutionSummary.target_url``
        is the one field in the contract a JTL cannot supply: a JTL records
        sampler labels, not the request that authorized them. That is still a
        value the caller passes, not a dependency the parser reaches for, so the
        boundary in ``runtime-responsibility.md`` §5 is unchanged — which is
        what the assertions below now check directly.
        """
        params = list(inspect.signature(JMeterParser.parse).parameters)
        self.assertEqual(["self", "jtl_path", "target_url"], params)

    def test_the_parser_takes_no_persistence_or_infrastructure_dependencies(self):
        params = set(inspect.signature(JMeterParser.__init__).parameters)
        self.assertEqual(
            set(),
            params
            & {"operation_service", "operation_dao", "dao", "pool_manager", "client"},
        )


class AnalyzerBoundaryTests(unittest.TestCase):
    """JMeterAnalyzer reads the persisted result and nothing else."""

    def test_analyze_takes_only_an_operation_id(self):
        params = list(
            inspect.signature(JMeterAnalyzer.analyze_jmeter_result).parameters
        )
        self.assertEqual(["self", "operation_id"], params)

    def test_ownership_check_uses_the_queue_lane_field(self):
        self.assertTrue(JMeterAnalyzer._is_jmeter_operation(BatchType.JMETER_TEST))
        self.assertFalse(JMeterAnalyzer._is_jmeter_operation(BatchType.API_SCAN))


class ResultContractTests(unittest.TestCase):
    """The ADR-0010 contract shape, which Phase 2 must produce."""

    def test_result_has_exactly_the_four_accepted_sections(self):
        from app.schemas.tools.jmeter.jmeter_test_result import JMeterTestResult

        self.assertEqual(
            ["operation_id", "summary", "metrics", "artifacts", "metadata"],
            list(JMeterTestResult.model_fields),
        )

    def test_result_carries_no_lifecycle_status_or_error(self):
        # The Operation owns lifecycle state (ADR-0008 I2/I3); duplicating it
        # here would create a second source of truth.
        from app.schemas.tools.jmeter.jmeter_test_result import JMeterTestResult

        fields = set(JMeterTestResult.model_fields)
        self.assertEqual(set(), fields & {"status", "error"})


if __name__ == "__main__":
    unittest.main()
