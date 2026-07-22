"""Tests for ReportChannelPersistence — the concrete PersistencePort (ADR-0010 §4.6)."""

import base64
import tempfile
import unittest
from pathlib import Path

from app.services.performance.engine.dto import (
    Artifact,
    ArtifactKind,
    ArtifactSet,
    ExecutionResult,
    ExecutionStatus,
)
from app.services.performance.persistence import ReportChannelPersistence
from app.services.performance.runtime import PersistencePort


class _FakeSender:
    def __init__(self, *, fail=False):
        self.sent = None
        self._fail = fail

    def send(self, report):
        if self._fail:
            raise RuntimeError("delivery failed")
        self.sent = report


class ReportChannelPersistenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _result(self):
        results = self.dir / "results.jtl"
        results.write_text("sample-results")
        log = self.dir / "jmeter.log"
        log.write_text("engine-log")
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            duration_seconds=1.25,
            artifacts=ArtifactSet(
                (
                    Artifact(ArtifactKind.RESULTS, results),
                    Artifact(ArtifactKind.LOG, log),
                )
            ),
        )

    def test_satisfies_persistence_port(self):
        self.assertIsInstance(ReportChannelPersistence(_FakeSender()), PersistencePort)

    def test_builds_report_from_result_with_inlined_artifact_bytes(self):
        sender = _FakeSender()
        ReportChannelPersistence(sender).persist("op-1", self._result())

        report = sender.sent
        self.assertEqual(report.operation_id, "op-1")
        self.assertEqual(report.status, "completed")
        self.assertEqual(report.exit_code, 0)
        self.assertEqual(report.duration_seconds, 1.25)
        self.assertEqual({a.kind for a in report.artifacts}, {"results", "log"})
        by_name = {a.name: a for a in report.artifacts}
        self.assertEqual(
            base64.b64decode(by_name["results.jtl"].content_b64), b"sample-results"
        )
        self.assertEqual(base64.b64decode(by_name["jmeter.log"].content_b64), b"engine-log")

    def test_persist_propagates_delivery_failure(self):
        # PersistencePort contract: raise on failure so the Runtime cleans up
        # after a definitive persist failure (INV5).
        with self.assertRaises(RuntimeError):
            ReportChannelPersistence(_FakeSender(fail=True)).persist("op-1", self._result())

    def test_directory_artifacts_are_skipped(self):
        report_dir = self.dir / "report"
        report_dir.mkdir()
        result = ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            duration_seconds=0.0,
            artifacts=ArtifactSet((Artifact(ArtifactKind.REPORT, report_dir),)),
        )
        sender = _FakeSender()
        ReportChannelPersistence(sender).persist("op-1", result)
        self.assertEqual(sender.sent.artifacts, [])  # dir skipped, no crash


if __name__ == "__main__":
    unittest.main()
