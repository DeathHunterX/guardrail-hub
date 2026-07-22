"""How an operation is executed — independent of *what* it is.

``ExecutionStrategy`` (HOW) is kept deliberately separate from
``ZapOperationType`` (WHAT): two different operation types can share a strategy
(``API_SCAN`` and ``API_SCENARIO`` are both ``SEQUENTIAL`` — a single scan bound
to one worker), and the two concepts evolve independently.

The Dispatcher reads exactly one thing off a strategy: :attr:`requires_worker`.
That single generic flag is what lets the Dispatcher route every operation
without ever learning a tool's identity:

* worker-bound strategies claim a ZAP worker from the pool and run a scan on it;
* orchestration strategies (``FAN_OUT``) run WITHOUT ever occupying a worker —
  they spawn child operations. This is what keeps an ``api_suite`` orchestrator
  from holding a worker slot while its child scans run (workers only ever
  execute real scan operations).

Only the two members actually used today are defined. ``PARALLEL``, ``BATCH``,
and ``FAN_IN`` were speculative members removed by ADR-0009 H3 (verified unused);
a genuinely new strategy is added back only when a tool needs it.
"""

from enum import Enum


class ExecutionStrategy(str, Enum):
    """How work runs. Orthogonal to ZapOperationType."""

    # Worker-bound: one operation runs on one assigned ZAP worker.
    SEQUENTIAL = "sequential"  # ordered work on one worker (api_scan, api_scenario)

    # Orchestration: no worker is ever claimed.
    FAN_OUT = "fan_out"        # spawns child operations (api_suite)

    @property
    def requires_worker(self) -> bool:
        """Whether the Dispatcher must assign a ZAP worker before executing.

        Orchestration strategies never hold a pool worker; every other strategy
        is worker-bound. This is the ONLY property the Dispatcher inspects, so
        routing stays fully generic.
        """
        return self is not ExecutionStrategy.FAN_OUT
