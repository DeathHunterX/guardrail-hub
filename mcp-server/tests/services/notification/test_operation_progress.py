"""Unit tests for the generic OperationProgress model and lifecycle phases."""

import unittest

from app.domain.lifecycle import OperationPhase
from app.services.notification.rendering.operation_progress import (
    OperationProgress,
)


class OperationPhaseTests(unittest.TestCase):
    def test_string_values_match_domain_status(self):
        self.assertEqual(OperationPhase.QUEUED.value, "queued")
        self.assertEqual(OperationPhase.RUNNING.value, "running")
        self.assertEqual(OperationPhase.COMPLETED.value, "completed")
        self.assertEqual(OperationPhase.FAILED.value, "failed")

    def test_terminal_phases(self):
        self.assertTrue(OperationPhase.COMPLETED.is_terminal)
        self.assertTrue(OperationPhase.FAILED.is_terminal)
        self.assertTrue(OperationPhase.CANCELLED.is_terminal)
        self.assertFalse(OperationPhase.QUEUED.is_terminal)
        self.assertFalse(OperationPhase.RUNNING.is_terminal)


class OperationProgressTests(unittest.TestCase):
    def test_minimal_construction_defaults(self):
        p = OperationProgress(operation_id="api_scan:1", phase=OperationPhase.QUEUED)
        self.assertEqual(p.operation_id, "api_scan:1")
        self.assertIsNone(p.stage)
        self.assertIsNone(p.progress)
        self.assertIsNotNone(p.timestamp)

    def test_progress_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            OperationProgress("op:1", OperationPhase.RUNNING, progress=101)
        with self.assertRaises(ValueError):
            OperationProgress("op:1", OperationPhase.RUNNING, progress=-1)

    def test_progress_bounds_accepted(self):
        self.assertEqual(
            OperationProgress("op:1", OperationPhase.RUNNING, progress=0).progress, 0
        )
        self.assertEqual(
            OperationProgress("op:1", OperationPhase.RUNNING, progress=100).progress, 100
        )


if __name__ == "__main__":
    unittest.main()
