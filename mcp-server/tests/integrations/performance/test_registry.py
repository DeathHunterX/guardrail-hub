"""Unit tests for the Performance Worker Registry (ADR-0010 §4.2/§4.3/§4.8)."""

import unittest
from datetime import datetime, timedelta, timezone

from app.integrations.performance.registry import (
    PerformanceWorkerRegistry,
    WorkerNotRegisteredError,
)
from app.schemas.performance.worker import (
    PerformanceWorkerLifecycleState,
    WorkerHealth,
)


class RegistrationAndHeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.reg = PerformanceWorkerRegistry()

    def test_register_defaults_id_to_hostname_and_is_active(self):
        info = self.reg.register(worker_id=None, hostname="perf-1", version="1.0")
        self.assertEqual(info.worker_id, "perf-1")
        self.assertEqual(info.state, PerformanceWorkerLifecycleState.ACTIVE)
        self.assertTrue(info.is_idle)

    def test_reregister_preserves_op_id(self):
        self.reg.register(worker_id="w", hostname="w")
        self.reg.assign("w", "op-1")
        again = self.reg.register(worker_id="w", hostname="w", version="2.0")
        self.assertEqual(again.op_id, "op-1")  # in-flight bookkeeping preserved
        self.assertEqual(again.version, "2.0")

    def test_heartbeat_updates_health_and_rejects_unknown(self):
        self.reg.register(worker_id="w", hostname="w")
        info = self.reg.heartbeat("w", WorkerHealth(cpu_percent=42.0, orphan_process_count=0))
        self.assertEqual(info.health.cpu_percent, 42.0)
        with self.assertRaises(WorkerNotRegisteredError):
            self.reg.heartbeat("ghost")

    def test_heartbeat_self_heals_offline_worker(self):
        self.reg.register(worker_id="w", hostname="w")
        self.reg.mark_draining("w")
        self.reg.release("w")  # draining -> offline
        self.assertEqual(self.reg.get("w").state, PerformanceWorkerLifecycleState.OFFLINE)
        healed = self.reg.heartbeat("w")
        self.assertEqual(healed.state, PerformanceWorkerLifecycleState.ACTIVE)


class AssignmentAndCancellationTests(unittest.TestCase):
    def setUp(self):
        self.reg = PerformanceWorkerRegistry()
        self.reg.register(worker_id="w", hostname="w")

    def test_assign_marks_busy_and_clears_cancel(self):
        self.reg.assign("w", "op-1")
        info = self.reg.get("w")
        self.assertEqual(info.op_id, "op-1")
        self.assertFalse(info.is_idle)
        self.assertFalse(info.cancel_requested)

    def test_request_cancel_only_applies_to_the_held_operation(self):
        self.reg.assign("w", "op-1")
        self.assertTrue(self.reg.request_cancel("w", "op-1"))
        self.assertTrue(self.reg.get("w").cancel_requested)
        # A cancel for a different op is ignored (stale / reassigned).
        self.assertFalse(self.reg.request_cancel("w", "op-OTHER"))

    def test_release_clears_op_and_cancel(self):
        self.reg.assign("w", "op-1")
        self.reg.request_cancel("w", "op-1")
        self.reg.release("w", "op-1")
        info = self.reg.get("w")
        self.assertTrue(info.is_idle)
        self.assertFalse(info.cancel_requested)

    def test_release_with_mismatched_op_is_noop(self):
        self.reg.assign("w", "op-1")
        self.reg.release("w", "op-OTHER")
        self.assertEqual(self.reg.get("w").op_id, "op-1")

    def test_draining_worker_goes_offline_on_release(self):
        self.reg.assign("w", "op-1")
        self.reg.mark_draining("w")
        self.reg.release("w", "op-1")
        self.assertEqual(self.reg.get("w").state, PerformanceWorkerLifecycleState.OFFLINE)


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.reg = PerformanceWorkerRegistry()

    def _age_heartbeat(self, worker_id, seconds):
        info = self.reg.get(worker_id)
        old = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        self.reg._workers[worker_id] = info.model_copy(update={"last_heartbeat": old})

    def test_sweep_marks_expired_offline_and_reports_orphaned_op(self):
        self.reg.register(worker_id="w", hostname="w")
        self.reg.assign("w", "op-1")
        self._age_heartbeat("w", 120)
        orphaned = self.reg.sweep_expired(timeout_seconds=60)
        self.assertEqual(orphaned, [("w", "op-1")])
        self.assertEqual(self.reg.get("w").state, PerformanceWorkerLifecycleState.OFFLINE)

    def test_sweep_ignores_fresh_workers_and_does_not_double_report(self):
        self.reg.register(worker_id="w", hostname="w")
        self.reg.assign("w", "op-1")
        self._age_heartbeat("w", 120)
        self.assertEqual(len(self.reg.sweep_expired(60)), 1)
        self.assertEqual(self.reg.sweep_expired(60), [])  # already offline

    def test_list_all_is_sorted(self):
        for wid in ("w-c", "w-a", "w-b"):
            self.reg.register(worker_id=wid, hostname=wid)
        self.assertEqual([w.worker_id for w in self.reg.list_all()], ["w-a", "w-b", "w-c"])


if __name__ == "__main__":
    unittest.main()
