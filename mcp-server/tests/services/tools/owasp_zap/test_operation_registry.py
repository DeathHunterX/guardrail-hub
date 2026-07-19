"""Unit tests for the generic ZAP operation registry and its abstractions.

These exercise only the execution layer (pydantic-only, no zaproxy/fastapi), so
they run everywhere the unit sandbox does.
"""

import unittest

from pydantic import BaseModel

from app.services.tools.owasp_zap.execution.execution_strategy import ExecutionStrategy
from app.services.tools.owasp_zap.execution.handler import ZapOperation
from app.services.tools.owasp_zap.execution.operation_type import ZapOperationType
from app.services.tools.owasp_zap.execution.registry import (
    UnknownOperationTypeError,
    ZapOperationRegistry,
)


class _FakeRequest(BaseModel):
    value: str


class _RecordingHandler:
    """Handler stub that records the arguments passed to execute()."""

    def __init__(self) -> None:
        self.calls: list = []

    def execute(self, operation_id, request, worker) -> None:
        self.calls.append((operation_id, request, worker))


def _make_operation(
    op_type=ZapOperationType.API_SCAN,
    strategy=ExecutionStrategy.SEQUENTIAL,
    handler=None,
) -> ZapOperation:
    return ZapOperation(
        operation_type=op_type,
        execution_strategy=strategy,
        request_model=_FakeRequest,
        handler=handler or _RecordingHandler(),
    )


class ExecutionStrategyTests(unittest.TestCase):
    def test_worker_bound_strategies_require_a_worker(self):
        self.assertTrue(ExecutionStrategy.SEQUENTIAL.requires_worker)
        self.assertTrue(ExecutionStrategy.PARALLEL.requires_worker)
        self.assertTrue(ExecutionStrategy.BATCH.requires_worker)

    def test_orchestration_strategies_do_not_require_a_worker(self):
        self.assertFalse(ExecutionStrategy.FAN_OUT.requires_worker)
        self.assertFalse(ExecutionStrategy.FAN_IN.requires_worker)


class ZapOperationSerializationTests(unittest.TestCase):
    def test_round_trips_request_through_metadata(self):
        operation = _make_operation()
        payload = operation.serialize_request(_FakeRequest(value="hello"))
        rebuilt = operation.deserialize_request({"request": payload})
        self.assertEqual(rebuilt, _FakeRequest(value="hello"))

    def test_deserialize_raises_on_missing_request_key(self):
        operation = _make_operation()
        with self.assertRaises(KeyError):
            operation.deserialize_request({})


class ZapOperationRegistryTests(unittest.TestCase):
    def test_register_and_get(self):
        registry = ZapOperationRegistry()
        operation = _make_operation()
        registry.register(operation)
        self.assertIs(registry.get(ZapOperationType.API_SCAN), operation)

    def test_duplicate_registration_is_rejected(self):
        registry = ZapOperationRegistry()
        registry.register(_make_operation())
        with self.assertRaises(ValueError):
            registry.register(_make_operation())

    def test_get_unknown_type_raises(self):
        registry = ZapOperationRegistry()
        with self.assertRaises(UnknownOperationTypeError):
            registry.get(ZapOperationType.API_SUITE)

    def test_resolve_reads_operation_type_from_metadata(self):
        registry = ZapOperationRegistry()
        suite = _make_operation(
            op_type=ZapOperationType.API_SUITE, strategy=ExecutionStrategy.FAN_OUT
        )
        registry.register(suite)
        resolved = registry.resolve_from_metadata(
            {"operation_type": "api_suite", "request": {"value": "x"}}
        )
        self.assertIs(resolved, suite)

    def test_legacy_metadata_without_operation_type_defaults_to_api_scan(self):
        # Backward compatibility: rows queued before the refactor have no
        # operation_type and must still resolve (to API_SCAN).
        registry = ZapOperationRegistry()
        api_scan = _make_operation()
        registry.register(api_scan)
        resolved = registry.resolve_from_metadata({"request": {"value": "x"}})
        self.assertIs(resolved, api_scan)

    def test_invalid_operation_type_value_raises(self):
        registry = ZapOperationRegistry()
        registry.register(_make_operation())
        with self.assertRaises(ValueError):
            registry.resolve_from_metadata({"operation_type": "not_a_real_type"})


if __name__ == "__main__":
    unittest.main()
