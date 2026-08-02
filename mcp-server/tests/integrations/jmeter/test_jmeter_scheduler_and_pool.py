"""JMeter scheduling and pool assignment.

The scheduler must be deterministic and fair; the pool must never hand out a
worker that is busy, draining or offline.
"""

import unittest

from app.integrations.jmeter.pool import JMeterWorkerPoolManager
from app.integrations.jmeter.registry import JMeterWorkerRegistry
from app.integrations.jmeter.scheduler import RoundRobinJMeterWorkerScheduler
from app.integrations.jmeter.worker_client import JMeterWorkerClient
from app.schemas.tools.jmeter.worker import JMeterWorkerInfo, JMeterWorkerState


def _worker(worker_id: str, *, state=JMeterWorkerState.ACTIVE, op_id=None):
    return JMeterWorkerInfo(
        worker_id=worker_id,
        hostname=worker_id,
        endpoint=f"http://{worker_id}:8090",
        port=8090,
        state=state,
        op_id=op_id,
    )


def _pool(*worker_ids: str):
    registry = JMeterWorkerRegistry()
    for worker_id in worker_ids:
        registry.register(
            worker_id=worker_id,
            hostname=worker_id,
            endpoint=f"http://{worker_id}:8090",
            port=8090,
        )
    return JMeterWorkerPoolManager(registry, RoundRobinJMeterWorkerScheduler())


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = RoundRobinJMeterWorkerScheduler()

    def test_empty_pool_selects_nothing(self):
        self.assertIsNone(self.scheduler.select([]))

    def test_rotates_rather_than_always_picking_the_first(self):
        workers = [_worker("a"), _worker("b"), _worker("c")]
        picked = [self.scheduler.select(workers).worker_id for _ in range(4)]
        self.assertEqual(["a", "b", "c", "a"], picked)

    def test_selection_is_deterministic_for_the_same_state(self):
        workers = [_worker("a"), _worker("b")]
        first = RoundRobinJMeterWorkerScheduler().select(workers)
        second = RoundRobinJMeterWorkerScheduler().select(workers)
        self.assertEqual(first.worker_id, second.worker_id)

    def test_busy_draining_and_offline_workers_are_skipped(self):
        workers = [
            _worker("a", op_id="op-1"),
            _worker("b", state=JMeterWorkerState.DRAINING),
            _worker("c", state=JMeterWorkerState.OFFLINE),
            _worker("d"),
        ]
        self.assertEqual("d", self.scheduler.select(workers).worker_id)

    def test_returns_none_when_nobody_is_eligible(self):
        workers = [_worker("a", op_id="op-1"), _worker("b", state=JMeterWorkerState.OFFLINE)]
        self.assertIsNone(self.scheduler.select(workers))

    def test_cursor_survives_a_pass_with_no_eligible_worker(self):
        workers = [_worker("a"), _worker("b")]
        self.assertEqual("a", self.scheduler.select(workers).worker_id)

        busy = [_worker("a", op_id="x"), _worker("b", op_id="y")]
        self.assertIsNone(self.scheduler.select(busy))

        # Rotation resumes where it left off rather than restarting at "a".
        self.assertEqual("b", self.scheduler.select(workers).worker_id)


class PoolAssignmentTests(unittest.TestCase):
    def test_assignment_binds_the_operation_to_the_worker(self):
        pool = _pool("jmeter-1")
        assigned = pool.try_assign("op-1")

        self.assertIsNotNone(assigned)
        self.assertEqual("op-1", pool.registry.get(assigned.worker_id).op_id)

    def test_second_assignment_is_refused_when_the_only_worker_is_busy(self):
        pool = _pool("jmeter-1")
        self.assertIsNotNone(pool.try_assign("op-1"))
        self.assertIsNone(pool.try_assign("op-2"))

    def test_empty_pool_refuses_assignment(self):
        self.assertIsNone(_pool().try_assign("op-1"))

    def test_release_makes_the_worker_assignable_again(self):
        pool = _pool("jmeter-1")
        assigned = pool.try_assign("op-1")
        pool.release_worker(assigned.worker_id, "op-1")
        self.assertIsNotNone(pool.try_assign("op-2"))

    def test_two_operations_land_on_two_different_workers(self):
        pool = _pool("jmeter-1", "jmeter-2")
        first = pool.try_assign("op-1")
        second = pool.try_assign("op-2")
        self.assertNotEqual(first.worker_id, second.worker_id)

    def test_offline_worker_is_never_assigned(self):
        pool = _pool("jmeter-1")
        pool.registry.sweep_expired(timeout_seconds=-1)  # force Offline
        self.assertIsNone(pool.try_assign("op-1"))


class PoolClientCacheTests(unittest.TestCase):
    def test_client_is_cached_per_worker(self):
        pool = _pool("jmeter-1")
        worker = pool.registry.get("jmeter-1")
        first = pool.get_client(worker)
        self.assertIsInstance(first, JMeterWorkerClient)
        self.assertIs(first, pool.get_client(worker))

    def test_client_is_rebuilt_when_the_worker_moves(self):
        pool = _pool("jmeter-1")
        worker = pool.registry.get("jmeter-1")
        first = pool.get_client(worker)

        moved = worker.model_copy(update={"endpoint": "http://jmeter-1:9999"})
        rebuilt = pool.get_client(moved)
        self.assertIsNot(first, rebuilt)
        self.assertEqual("http://jmeter-1:9999", rebuilt.endpoint)


if __name__ == "__main__":
    unittest.main()
