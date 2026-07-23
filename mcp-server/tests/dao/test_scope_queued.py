"""Unit tests for the shared type-scoped queued read helper (ADR-0010 §4.12)."""

import unittest

from app.dao.base import scope_queued_by_type
from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase


def _op(operation_id, operation_type=None):
    metadata = {} if operation_type is None else {"operation_type": operation_type}
    return OperationRecord(
        operation_id=operation_id,
        status=OperationPhase.QUEUED,
        batch_type="x",
        metadata=metadata,
    )


class ScopeQueuedByTypeTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            _op("zap-1", "api_scan"),
            _op("perf-1", "performance_test"),
            _op("zap-2", "api_suite"),
            _op("legacy", None),  # pre-refactor row with no operation_type
        ]

    def test_none_returns_all_unchanged(self):
        # Backward-compatible unscoped read.
        self.assertEqual(scope_queued_by_type(self.records, None), self.records)

    def test_scopes_to_the_given_types(self):
        scoped = scope_queued_by_type(self.records, {"api_scan", "api_suite"})
        self.assertEqual([r.operation_id for r in scoped], ["zap-1", "zap-2"])

    def test_scopes_to_a_single_engine(self):
        scoped = scope_queued_by_type(self.records, {"performance_test"})
        self.assertEqual([r.operation_id for r in scoped], ["perf-1"])

    def test_missing_operation_type_is_excluded_when_scoped(self):
        # A scoped caller asks for explicit types; a typeless legacy row is not
        # one of them (legacy rows are handled by the unscoped reader).
        scoped = scope_queued_by_type(self.records, {"api_scan"})
        self.assertNotIn("legacy", [r.operation_id for r in scoped])

    def test_empty_types_returns_nothing(self):
        self.assertEqual(scope_queued_by_type(self.records, set()), [])


if __name__ == "__main__":
    unittest.main()
