"""Worker fitness — is a worker eligible to receive the next operation?

Scheduling here is health- and version-aware (ADR-0010 §2.3 / §4.8), not just
"is it idle". A worker can be registered and idle yet unfit: an incompatible
version (INV11), a leaked engine process (orphan count), or disk pressure. These
predicates express that; the scheduler consumes one, and the composition root
builds it from the server's ``min_compatible_version``.

Deliberately small: concrete thresholds are the extension point ADR-0010 §4.8
reserves; this is the minimal honest policy, not a tuning framework.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from app.schemas.performance.worker import PerformanceWorkerInfo, WorkerHealth

WorkerFitness = Callable[[PerformanceWorkerInfo], bool]

_DISK_CEILING_PERCENT = 95.0


def version_compatible(worker_version: Optional[str], min_version: Optional[str]) -> bool:
    """True if *worker_version* is at least *min_version* (fail closed).

    No minimum → all pass. Otherwise the worker must report a parseable version
    that is >= the minimum; a missing or unparseable version is incompatible.
    """
    if min_version is None:
        return True
    worker_parsed = _parse(worker_version)
    min_parsed = _parse(min_version)
    if worker_parsed is None or min_parsed is None:
        return False
    return worker_parsed >= min_parsed


def health_ok(health: WorkerHealth) -> bool:
    """True unless health shows a disqualifying condition (leak / disk pressure)."""
    if health.orphan_process_count not in (None, 0):
        return False
    if health.disk_percent is not None and health.disk_percent >= _DISK_CEILING_PERCENT:
        return False
    return True


def build_fitness(min_compatible_version: Optional[str] = None) -> WorkerFitness:
    """Compose the eligibility predicate: schedulable AND compatible AND healthy."""

    def fit(worker: PerformanceWorkerInfo) -> bool:
        return (
            worker.is_schedulable
            and version_compatible(worker.version, min_compatible_version)
            and health_ok(worker.health)
        )

    return fit


def _parse(version: Optional[str]) -> Optional[Tuple[int, ...]]:
    if not version:
        return None
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return None
