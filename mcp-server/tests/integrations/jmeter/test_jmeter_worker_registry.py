"""JMeter worker registry: registration, heartbeat, assignment, expiry.

Pure in-memory unit tests — no HTTP, no database, no JMeter.
"""

import unittest
from datetime import datetime, timedelta, timezone

from app.integrations.jmeter.registry import (
    JMeterWorkerNotRegisteredError,
    JMeterWorkerRegistry,
)
from app.schemas.tools.jmeter.worker import JMeterWorkerState


def _registry_with(*worker_ids: str) -> JMeterWorkerRegistry:
    registry = JMeterWorkerRegistry()
    for index, worker_id in enumerate(worker_ids):
        registry.register(
            worker_id=worker_id,
            hostname=worker_id,
            endpoint=f"http://{worker_id}:8090",
            port=8090,
        )
    return registry


class RegistrationTests(unittest.TestCase):
    def test_register_returns_an_active_idle_worker(self):
        registry = JMeterWorkerRegistry()
        info = registry.register(
            worker_id="jmeter-1",
            hostname="jmeter-1",
            endpoint="http://jmeter-1:8090",
            port=8090,
        )
        self.assertEqual(JMeterWorkerState.ACTIVE, info.state)
        self.assertTrue(info.is_idle)
        self.assertTrue(info.is_schedulable)

    def test_worker_id_defaults_to_hostname(self):
        registry = JMeterWorkerRegistry()
        info = registry.register(
            worker_id=None,
            hostname="jmeter-7",
            endpoint="http://jmeter-7:8090",
            port=8090,
        )
        self.assertEqual("jmeter-7", info.worker_id)

    def test_re_registration_refreshes_address_but_keeps_in_flight_operation(self):
        registry = _registry_with("jmeter-1")
        registry.assign("jmeter-1", "op-1")

        info = registry.register(
            worker_id="jmeter-1",
            hostname="jmeter-1",
            endpoint="http://jmeter-1:9999",
            port=9999,
        )
        # Address updated; the operation bookkeeping is deliberately untouched.
        self.assertEqual("http://jmeter-1:9999", info.endpoint)
        self.assertEqual("op-1", info.op_id)


class HeartbeatTests(unittest.TestCase):
    def test_heartbeat_of_unknown_worker_raises(self):
        registry = JMeterWorkerRegistry()
        with self.assertRaises(JMeterWorkerNotRegisteredError):
            registry.heartbeat("never-registered")

    def test_heartbeat_advances_the_timestamp(self):
        registry = _registry_with("jmeter-1")
        before = registry.get("jmeter-1").last_heartbeat
        after = registry.heartbeat("jmeter-1").last_heartbeat
        self.assertGreaterEqual(after, before)

    def test_offline_worker_self_heals_on_heartbeat(self):
        registry = _registry_with("jmeter-1")
        registry.sweep_expired(timeout_seconds=-1)  # force it Offline
        self.assertEqual(JMeterWorkerState.OFFLINE, registry.get("jmeter-1").state)

        healed = registry.heartbeat("jmeter-1")
        self.assertEqual(JMeterWorkerState.ACTIVE, healed.state)


class AssignmentTests(unittest.TestCase):
    def test_assigned_worker_is_no_longer_schedulable(self):
        registry = _registry_with("jmeter-1")
        registry.assign("jmeter-1", "op-1")
        self.assertFalse(registry.get("jmeter-1").is_schedulable)

    def test_release_requires_the_matching_operation(self):
        registry = _registry_with("jmeter-1")
        registry.assign("jmeter-1", "op-1")

        # A late release from a previous operation must not free a reassigned slot.
        registry.release("jmeter-1", "op-stale")
        self.assertEqual("op-1", registry.get("jmeter-1").op_id)

        registry.release("jmeter-1", "op-1")
        self.assertIsNone(registry.get("jmeter-1").op_id)

    def test_draining_worker_goes_offline_once_released(self):
        registry = _registry_with("jmeter-1")
        registry.assign("jmeter-1", "op-1")
        registry.mark_draining("jmeter-1")

        registry.release("jmeter-1", "op-1")
        self.assertEqual(JMeterWorkerState.OFFLINE, registry.get("jmeter-1").state)

    def test_draining_worker_is_not_schedulable(self):
        registry = _registry_with("jmeter-1")
        registry.mark_draining("jmeter-1")
        self.assertFalse(registry.get("jmeter-1").is_schedulable)

    def test_remove_returns_the_orphaned_operation(self):
        registry = _registry_with("jmeter-1")
        registry.assign("jmeter-1", "op-1")
        self.assertEqual("op-1", registry.remove("jmeter-1"))
        self.assertIsNone(registry.get("jmeter-1"))


class HeartbeatExpiryTests(unittest.TestCase):
    def _age_worker(self, registry, worker_id, seconds):
        stale = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        # Reach past the lock only to fabricate an old heartbeat; the sweep
        # under test is what actually reads it.
        with registry._lock:  # pylint: disable=protected-access
            info = registry._workers[worker_id]  # pylint: disable=protected-access
            registry._workers[worker_id] = info.model_copy(  # pylint: disable=protected-access
                update={"last_heartbeat": stale}
            )

    def test_expired_worker_is_marked_offline_and_reports_its_operation(self):
        registry = _registry_with("jmeter-1")
        registry.assign("jmeter-1", "op-1")
        self._age_worker(registry, "jmeter-1", seconds=300)

        orphaned = registry.sweep_expired(timeout_seconds=120)

        self.assertEqual([("jmeter-1", "op-1")], orphaned)
        info = registry.get("jmeter-1")
        self.assertEqual(JMeterWorkerState.OFFLINE, info.state)
        self.assertIsNone(info.op_id)

    def test_a_live_worker_is_untouched(self):
        registry = _registry_with("jmeter-1")
        self.assertEqual([], registry.sweep_expired(timeout_seconds=120))
        self.assertEqual(JMeterWorkerState.ACTIVE, registry.get("jmeter-1").state)

    def test_one_dead_worker_is_reported_only_once(self):
        registry = _registry_with("jmeter-1")
        registry.assign("jmeter-1", "op-1")
        self._age_worker(registry, "jmeter-1", seconds=300)

        self.assertEqual(1, len(registry.sweep_expired(timeout_seconds=120)))
        # Second sweep: already Offline, so no repeated failure for the same worker.
        self.assertEqual([], registry.sweep_expired(timeout_seconds=120))


class ListingTests(unittest.TestCase):
    def test_listing_is_stably_sorted(self):
        registry = _registry_with("jmeter-3", "jmeter-1", "jmeter-2")
        ids = [w.worker_id for w in registry.list_all()]
        self.assertEqual(["jmeter-1", "jmeter-2", "jmeter-3"], ids)


if __name__ == "__main__":
    unittest.main()
