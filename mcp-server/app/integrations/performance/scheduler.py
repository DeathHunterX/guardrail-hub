"""Worker scheduling — pick the next worker, and only that.

**Invariant (ADR-0010, Phase 2):** the scheduler's responsibility ends at
*selection*. It never assigns, never touches the queue, and — critically — never
invokes the execution runtime. Selecting a worker and running a job are different
responsibilities on different sides of the pull boundary: the pool assigns, the
worker executes. This module therefore imports nothing from the runtime or any
engine.

Round Robin over the *fit* workers (see ``fitness``), keeping a cursor so load
spreads across the pool rather than always favouring whoever sorts first —
matching the ZAP scheduler's proven behaviour.
"""

from __future__ import annotations

import threading
from typing import List, Optional, Protocol

from app.integrations.performance.fitness import WorkerFitness, build_fitness
from app.schemas.performance.worker import PerformanceWorkerInfo


class WorkerScheduler(Protocol):
    """Strategy: pick one worker to run the next operation, or None."""

    def select(self, workers: List[PerformanceWorkerInfo]) -> Optional[PerformanceWorkerInfo]:
        ...


class RoundRobinScheduler:
    """Fair rotation across workers the *fitness* predicate accepts."""

    def __init__(self, fitness: Optional[WorkerFitness] = None) -> None:
        self._fitness = fitness or build_fitness()
        self._cursor = 0
        self._lock = threading.Lock()

    def select(self, workers: List[PerformanceWorkerInfo]) -> Optional[PerformanceWorkerInfo]:
        if not workers:
            return None
        with self._lock:
            n = len(workers)
            for step in range(n):
                idx = (self._cursor + step) % n
                candidate = workers[idx]
                if self._fitness(candidate):
                    self._cursor = (idx + 1) % n
                    return candidate
            return None
