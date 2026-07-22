"""The replaceable-engine seam — the behaviour half.

``PerformanceRunner`` is the entire contract a performance engine must satisfy:
given a neutral :class:`ExecutionRequest`, run one execution and return a neutral
:class:`ExecutionResult`. JMeter is the only implementation today
(``app/integrations/jmeter/jmeter_runner.py``); k6/Gatling/Locust would each be a
*second* implementation of this same protocol — never a change to the Runtime,
Service, dispatcher, or queue (ADR-0010 §2.4 / D5). This is a seam, not a
framework: it is intentionally one method wide.

Cancellation is cooperative and inbound-channel-free (ADR-0010 §4.3): the
worker-side Runtime owns a ``threading.Event`` and sets it when a cancel is
observed on the heartbeat; the Runner watches that event and, on observing it
(or on the request's timeout elapsing), terminates the engine's **process
group** and returns a ``CANCELLED`` / ``TIMED_OUT`` result. The event is stdlib
so the seam names no engine and no transport.
"""

from __future__ import annotations

from threading import Event
from typing import Protocol, runtime_checkable

from app.services.performance.engine.dto import ExecutionRequest, ExecutionResult


@runtime_checkable
class PerformanceRunner(Protocol):
    """Run one performance execution for a single engine.

    Implementations own only *engine invocation*: build the engine's CLI
    arguments, launch it in its own process group, enforce
    ``request.timeout_seconds`` locally, enact cancellation by killing that
    group when *cancel* is set, capture stdout/stderr and the exit code, and
    collect the produced artifacts. They own no scheduling, no queue access, and
    no policy decisions — those belong to the server and the Runtime.
    """

    def run(self, request: ExecutionRequest, cancel: Event) -> ExecutionResult:
        """Run *request* to completion, cancellation, or timeout.

        Must not raise for an ordinary engine failure — a non-zero exit is a
        ``FAILED`` :class:`ExecutionResult`, not an exception. *cancel* is set by
        the Runtime to request early, process-group-wide termination.
        """
        ...
