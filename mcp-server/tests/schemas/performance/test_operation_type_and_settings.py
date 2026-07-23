"""C3.1 — PerformanceOperationType + settings foundation (ADR-0010 §4.8/§4.9/§4.12)."""

import unittest

from app.core.config import settings
from app.schemas.performance.operation_type import PerformanceOperationType


class PerformanceOperationTypeTests(unittest.TestCase):
    def test_value_is_stable(self):
        self.assertEqual(PerformanceOperationType.PERFORMANCE_TEST.value, "performance_test")

    def test_supported_set_is_derivable(self):
        # Single source of truth for the dispatcher's supported type set (R-B).
        supported = frozenset(t.value for t in PerformanceOperationType)
        self.assertEqual(supported, {"performance_test"})

    def test_is_a_str_enum(self):
        # str-enum so the persisted metadata value is human-readable and stable.
        self.assertIsInstance(PerformanceOperationType.PERFORMANCE_TEST, str)


class PerformanceSettingsTests(unittest.TestCase):
    def test_defaults_present(self):
        self.assertEqual(settings.performance_worker_token, "change-this-performance-worker-token")
        self.assertEqual(settings.performance_queue_poll_interval_seconds, 2.0)
        self.assertEqual(settings.performance_worker_heartbeat_timeout_seconds, 60)
        self.assertEqual(settings.performance_worker_heartbeat_sweep_interval_seconds, 10.0)
        self.assertEqual(settings.performance_worker_heartbeat_interval_seconds, 5.0)
        self.assertIsNone(settings.performance_min_compatible_version)


if __name__ == "__main__":
    unittest.main()
