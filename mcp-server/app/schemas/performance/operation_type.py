"""Strongly-typed identity of a Performance operation.

``PerformanceOperationType`` is the value persisted in an operation's
``metadata["operation_type"]`` and the Performance dispatcher's **supported
operation type set** (ADR-0010 §4.12). It is the Performance-engine analogue of
``ZapOperationType`` — a closed, validated ``str`` enum so the dispatcher scopes
its queue read to a known set and an unknown/typo'd type fails fast at
``PerformanceOperationType(value)`` rather than routing nowhere.

Single source of truth: the dispatcher derives its supported set from this enum,
and the public ``run_jmeter_test`` tool stamps operations with it — the two
never drift (roadmap risk R-B).
"""

from enum import Enum


class PerformanceOperationType(str, Enum):
    """What is being executed by the Performance engine. The dispatcher's scope key."""

    # A performance/load test run (one `jmeter -n` execution today).
    PERFORMANCE_TEST = "performance_test"
