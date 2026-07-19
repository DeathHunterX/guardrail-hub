"""Integration: both Phase-2 operations register and resolve via the registry.

Building the operations imports the scan services (which pull the zaproxy client
and httpx); skip cleanly where those are absent from the sandbox.
"""

import unittest

import pytest

pytest.importorskip("zapv2")
pytest.importorskip("httpx")

from app.core.events.dispatcher import InProcessEventDispatcher  # noqa: E402
from app.services.operations.operation_service import OperationService  # noqa: E402
from app.services.tools.owasp_zap.execution.execution_strategy import (  # noqa: E402
    ExecutionStrategy,
)
from app.services.tools.owasp_zap.execution.operation_type import (  # noqa: E402
    ZapOperationType,
)


class _DAO:
    def create_operation(self, **k):
        pass

    def update_operation_status(self, **k):
        pass

    def get_operation(self, *a, **k):
        return None


def _registry():
    from app.bootstrap import build_zap_operation_registry  # noqa: PLC0415

    op_service = OperationService(_DAO(), InProcessEventDispatcher())
    return build_zap_operation_registry(operation_service=op_service)


class Phase2RegistrationTests(unittest.TestCase):
    def test_all_three_operations_registered(self):
        reg = _registry()
        self.assertEqual(
            reg.registered_types(),
            frozenset(
                {
                    ZapOperationType.API_SCAN,
                    ZapOperationType.API_SCENARIO,
                    ZapOperationType.API_SUITE,
                }
            ),
        )

    def test_scenario_is_worker_bound_sequential(self):
        op = _registry().get(ZapOperationType.API_SCENARIO)
        self.assertEqual(op.execution_strategy, ExecutionStrategy.SEQUENTIAL)
        self.assertTrue(op.execution_strategy.requires_worker)

    def test_suite_is_orchestration_fan_out_without_worker(self):
        op = _registry().get(ZapOperationType.API_SUITE)
        self.assertEqual(op.execution_strategy, ExecutionStrategy.FAN_OUT)
        self.assertFalse(op.execution_strategy.requires_worker)

    def test_scenario_metadata_round_trips(self):
        reg = _registry()
        md = {
            "operation_type": "api_scenario",
            "request": {
                "report_group": "p",
                "steps": [
                    {"name": "login", "target_url": "https://x/login", "method": "POST"}
                ],
            },
        }
        op = reg.resolve_from_metadata(md)
        req = op.deserialize_request(md)
        self.assertEqual(req.steps[0].name, "login")

    def test_suite_metadata_round_trips(self):
        reg = _registry()
        md = {
            "operation_type": "api_suite",
            "request": {
                "report_group": "p",
                "application_name": "App",
                "categories": [
                    {"name": "Auth", "openapi_spec": {"paths": {"/login": {"post": {}}}}}
                ],
            },
        }
        op = reg.resolve_from_metadata(md)
        req = op.deserialize_request(md)
        self.assertEqual(req.categories[0].name, "Auth")


if __name__ == "__main__":
    unittest.main()
