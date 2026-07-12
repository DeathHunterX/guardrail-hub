"""Unit tests for the generic OperationProgress model and lifecycle phases."""

import unittest

from app.services.notification.operation_progress import (
    LifecyclePhase,
    OperationProgress,
)


class LifecyclePhaseTests(unittest.TestCase):
    def test_string_values_match_domain_status(self):
        self.assertEqual(LifecyclePhase.QUEUED.value, "queued")
        self.assertEqual(LifecyclePhase.RUNNING.value, "running")
        self.assertEqual(LifecyclePhase.COMPLETED.value, "completed")
        self.assertEqual(LifecyclePhase.FAILED.value, "failed")

    def test_terminal_phases(self):
        self.assertTrue(LifecyclePhase.COMPLETED.is_terminal)
        self.assertTrue(LifecyclePhase.FAILED.is_terminal)
        self.assertTrue(LifecyclePhase.CANCELLED.is_terminal)
        self.assertFalse(LifecyclePhase.QUEUED.is_terminal)
        self.assertFalse(LifecyclePhase.RUNNING.is_terminal)


class OperationProgressTests(unittest.TestCase):
    def test_minimal_construction_defaults(self):
        p = OperationProgress(operation_id="api_scan:1", phase=LifecyclePhase.QUEUED)
        self.assertEqual(p.operation_id, "api_scan:1")
        self.assertIsNone(p.stage)
        self.assertIsNone(p.progress)
        self.assertIsNotNone(p.timestamp)

    def test_progress_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            OperationProgress("op:1", LifecyclePhase.RUNNING, progress=101)
        with self.assertRaises(ValueError):
            OperationProgress("op:1", LifecyclePhase.RUNNING, progress=-1)

    def test_progress_bounds_accepted(self):
        self.assertEqual(
            OperationProgress("op:1", LifecyclePhase.RUNNING, progress=0).progress, 0
        )
        self.assertEqual(
            OperationProgress("op:1", LifecyclePhase.RUNNING, progress=100).progress, 100
        )


if __name__ == "__main__":
    unittest.main()
