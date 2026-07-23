"""Tests for fitness, the round-robin scheduler, and the pool manager.

Includes the structural guard for the Phase-2 invariant: scheduling ends at
assignment — the scheduler and pool never import the execution runtime.
"""

import ast
import unittest
from pathlib import Path

import app.integrations.performance.pool as pool_module
import app.integrations.performance.scheduler as scheduler_module
from app.integrations.performance.fitness import (
    build_fitness,
    health_ok,
    version_compatible,
)
from app.integrations.performance.pool import PerformancePoolManager
from app.integrations.performance.registry import PerformanceWorkerRegistry
from app.integrations.performance.scheduler import RoundRobinScheduler
from app.schemas.performance.worker import (
    PerformanceWorkerInfo,
    PerformanceWorkerLifecycleState,
    WorkerHealth,
)


def _worker(wid, *, idle=True, state=PerformanceWorkerLifecycleState.ACTIVE, version="1.0", health=None):
    return PerformanceWorkerInfo(
        worker_id=wid,
        hostname=wid,
        version=version,
        state=state,
        op_id=None if idle else "busy-op",
        health=health or WorkerHealth(),
    )


class FitnessTests(unittest.TestCase):
    def test_version_compatibility(self):
        self.assertTrue(version_compatible("1.2", None))       # no minimum
        self.assertTrue(version_compatible("1.2.0", "1.2.0"))  # equal
        self.assertTrue(version_compatible("1.3", "1.2"))      # higher
        self.assertFalse(version_compatible("1.1", "1.2"))     # lower
        self.assertFalse(version_compatible(None, "1.0"))      # missing, fail closed
        self.assertFalse(version_compatible("weird", "1.0"))   # unparseable

    def test_health_ok(self):
        self.assertTrue(health_ok(WorkerHealth()))
        self.assertTrue(health_ok(WorkerHealth(orphan_process_count=0, disk_percent=50)))
        self.assertFalse(health_ok(WorkerHealth(orphan_process_count=3)))  # leak
        self.assertFalse(health_ok(WorkerHealth(disk_percent=99)))         # disk pressure

    def test_build_fitness_combines_schedulable_version_health(self):
        fit = build_fitness(min_compatible_version="1.0")
        self.assertTrue(fit(_worker("w")))
        self.assertFalse(fit(_worker("w", idle=False)))                       # busy
        self.assertFalse(fit(_worker("w", state=PerformanceWorkerLifecycleState.DRAINING)))
        self.assertFalse(fit(_worker("w", version="0.9")))                    # incompatible
        self.assertFalse(fit(_worker("w", health=WorkerHealth(orphan_process_count=1))))


class RoundRobinSchedulerTests(unittest.TestCase):
    def test_returns_none_when_no_fit_worker(self):
        sched = RoundRobinScheduler()
        self.assertIsNone(sched.select([]))
        self.assertIsNone(sched.select([_worker("w", idle=False)]))

    def test_rotates_over_fit_workers(self):
        sched = RoundRobinScheduler()
        workers = [_worker("w-a"), _worker("w-b"), _worker("w-c")]
        picks = [sched.select(workers).worker_id for _ in range(4)]
        self.assertEqual(picks, ["w-a", "w-b", "w-c", "w-a"])  # fair rotation

    def test_skips_unfit_workers(self):
        sched = RoundRobinScheduler(fitness=build_fitness(min_compatible_version="1.0"))
        workers = [_worker("w-a", version="0.9"), _worker("w-b")]  # a incompatible
        self.assertEqual(sched.select(workers).worker_id, "w-b")


class PoolManagerTests(unittest.TestCase):
    def setUp(self):
        self.registry = PerformanceWorkerRegistry()
        self.pool = PerformancePoolManager(self.registry, RoundRobinScheduler())

    def test_try_assign_selects_and_binds(self):
        self.registry.register(worker_id="w", hostname="w", version="1.0")
        assigned = self.pool.try_assign("op-1")
        self.assertEqual(assigned.worker_id, "w")
        self.assertEqual(self.registry.get("w").op_id, "op-1")

    def test_try_assign_returns_none_when_no_worker(self):
        self.assertIsNone(self.pool.try_assign("op-1"))

    def test_try_assign_skips_busy_worker(self):
        self.registry.register(worker_id="w", hostname="w", version="1.0")
        self.registry.assign("w", "op-existing")
        self.assertIsNone(self.pool.try_assign("op-2"))  # only worker is busy


class SchedulingPurityTests(unittest.TestCase):
    """Scheduling ends at assignment: no runtime/engine import."""

    def _imports(self, module):
        src = Path(module.__file__).read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name
            elif isinstance(node, ast.ImportFrom):
                yield node.module or ""

    def test_scheduler_and_pool_never_import_the_runtime(self):
        for module in (scheduler_module, pool_module):
            for name in self._imports(module):
                self.assertNotIn("performance.runtime", name)
                self.assertNotIn("performance_runtime", name)
                self.assertNotIn("jmeter", name.lower())


if __name__ == "__main__":
    unittest.main()
