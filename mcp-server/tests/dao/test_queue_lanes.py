"""Queue lane isolation (ADR-0011).

Two properties are guarded here, both of which caused silent data loss before
the lane filter existed:

1. A dispatcher reading its own lane never sees another engine's rows. Without
   this, the ZAP dispatcher marks every JMeter operation FAILED within one poll
   tick, before any JMeter code runs.
2. Every dispatchable ``BatchType`` belongs to exactly one lane. A member with
   no lane is invisible to every dispatcher and stalls ``QUEUED`` forever —
   quieter than the bug it replaced, so it gets an explicit assertion.

These run against the base DAO implementation, which both backends share for
lane filtering, with no database.
"""

import unittest
from datetime import datetime, timedelta, timezone

from app.constants.batch import BatchType
from app.dao.base import BaseOperationDAO
from app.dao.operation_record import OperationRecord
from app.domain.lifecycle import OperationPhase

_NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)


def _record(operation_id: str, batch_type: str, age_seconds: int) -> OperationRecord:
    return OperationRecord(
        operation_id=operation_id,
        status=OperationPhase.QUEUED,
        batch_type=batch_type,
        created_at=_NOW + timedelta(seconds=age_seconds),
    )


class _FakeDAO(BaseOperationDAO):
    """Minimal DAO exposing only what get_queued_operations() needs."""

    def __init__(self, records: list[OperationRecord]) -> None:
        self._records = records

    def get_by_status(self, *statuses: str) -> list[OperationRecord]:
        return [r for r in self._records if r.status in statuses]

    # Unused by these tests; the ABC requires them to exist.
    def create_operation(self, *a, **kw):  # pragma: no cover - not exercised
        raise NotImplementedError

    def update_operation_status(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError

    def get_operation(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError

    def get_all(self):  # pragma: no cover
        raise NotImplementedError

    def get_by_type(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError

    def initialize_schema(self):  # pragma: no cover
        raise NotImplementedError


class QueueLaneIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dao = _FakeDAO(
            [
                _record("zap-1", BatchType.API_SCAN, 0),
                _record("jmeter-1", BatchType.JMETER_TEST, 1),
                _record("zap-2", BatchType.SUITE_SCAN, 2),
                _record("jmeter-2", BatchType.JMETER_TEST, 3),
            ]
        )

    def test_zap_lane_excludes_jmeter_operations(self):
        ids = [
            r.operation_id
            for r in self.dao.get_queued_operations(BatchType.ALL_SCAN_TYPES)
        ]
        self.assertEqual(["zap-1", "zap-2"], ids)

    def test_jmeter_lane_excludes_zap_operations(self):
        ids = [
            r.operation_id
            for r in self.dao.get_queued_operations(BatchType.ALL_JMETER_TYPES)
        ]
        self.assertEqual(["jmeter-1", "jmeter-2"], ids)

    def test_lane_preserves_fifo_order_by_created_at(self):
        dao = _FakeDAO(
            [
                _record("newer", BatchType.JMETER_TEST, 60),
                _record("older", BatchType.JMETER_TEST, 0),
            ]
        )
        ids = [
            r.operation_id for r in dao.get_queued_operations(BatchType.ALL_JMETER_TYPES)
        ]
        self.assertEqual(["older", "newer"], ids)

    def test_only_queued_rows_are_returned(self):
        running = _record("running", BatchType.JMETER_TEST, 0)
        running.status = OperationPhase.RUNNING
        dao = _FakeDAO([running])
        self.assertEqual([], dao.get_queued_operations(BatchType.ALL_JMETER_TYPES))


class BatchTypeLaneOwnershipTests(unittest.TestCase):
    def test_every_dispatchable_batch_type_belongs_to_exactly_one_lane(self):
        lanes = (BatchType.ALL_SCAN_TYPES, BatchType.ALL_JMETER_TYPES)
        dispatchable = {
            value
            for name, value in vars(BatchType).items()
            if isinstance(value, str)
            and not name.startswith("_")
            and value != BatchType.UNKNOWN
        }
        unowned = {
            batch_type
            for batch_type in dispatchable
            if sum(batch_type in lane for lane in lanes) != 1
        }
        self.assertEqual(
            set(),
            unowned,
            "Every dispatchable BatchType must belong to exactly one queue lane; "
            f"these belong to none or several: {sorted(unowned)}",
        )


if __name__ == "__main__":
    unittest.main()
