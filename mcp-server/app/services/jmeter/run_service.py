"""Run an existing JMeter ``.jmx`` test plan (``run_jmeter_test``).

The public, JMeter-first entry point: a tester points at a ``.jmx`` file they
already have and it runs — the analogue of ``jmeter -n -t <file>``. There is no
"generate" step and no plan id; running the same file again just starts another
run.

This is a thin public adapter over the **unchanged** internal engine: it reads
the file, validates it (the existing JMX whitelist), stores the plan, and creates
a QUEUED operation on the shared Operations queue. The dispatcher then assigns it
and a worker pulls and runs it. No runtime, worker, dispatcher, scheduler, or
queue behaviour changes here.

Internals stay internal: the operation still carries the ``performance_test``
operation type in its metadata (the dispatcher's scope key), and the plan is
stored under the operation id (the key the worker pulls by) — the plan is stored
*before* the operation is enqueued so a worker can never observe an operation
whose plan is not yet on disk. Everything is injected (composition-root wiring):
this module reads no ``Settings`` and constructs no infrastructure.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional, Protocol

from app.constants.batch import BatchType
from app.schemas.performance.operation_type import PerformanceOperationType


class JmxFileNotFoundError(FileNotFoundError):
    """The referenced ``.jmx`` path does not exist or is not a regular file."""

    def __init__(self, jmx_file: str) -> None:
        super().__init__(f"JMX file not found or not a regular file: {jmx_file}")
        self.jmx_file = jmx_file


class PlanValidator(Protocol):
    """Validate a plan; raise if it is unsafe to run."""

    def validate(self, plan: bytes | str) -> None: ...


class PlanWriter(Protocol):
    """Server-side write side of the plan store (keyed by operation id)."""

    def put(self, operation_id: str, plan: bytes, timeout_seconds: Optional[float] = None) -> None: ...


class OperationCreator(Protocol):
    """Create surface of the existing ``OperationService``."""

    def create(
        self,
        batch_type: str,
        metadata: Optional[dict[str, Any]] = None,
        log_path: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> str: ...


class JMeterTestService:
    """Validate and enqueue an existing ``.jmx`` file; return its run's operation id."""

    def __init__(
        self,
        validator: PlanValidator,
        plan_store: PlanWriter,
        operation_service: OperationCreator,
    ) -> None:
        self._validator = validator
        self._plan_store = plan_store
        self._operation_service = operation_service

    def run(self, jmx_file: str, timeout_seconds: Optional[float] = None) -> str:
        """Run the ``.jmx`` file at *jmx_file*; return the run's operation id.

        Raises:
            JmxFileNotFoundError: the path does not exist / is not a regular file.
            JmxValidationError: the plan is unsafe or not a valid JMeter plan
                (raised by the injected validator) — nothing is enqueued.
        """
        path = Path(jmx_file)
        if not path.is_file():
            raise JmxFileNotFoundError(jmx_file)

        plan = path.read_bytes()
        # Validate before anything is stored or queued: an unsafe plan never runs.
        self._validator.validate(plan)

        operation_id = str(uuid.uuid4())
        # Store the plan under the operation id FIRST — the worker pulls the plan
        # by operation id, so it must be on disk before the operation is visible
        # in the queue. Then enqueue (QUEUED), stamping the internal engine type
        # the dispatcher scopes on.
        self._plan_store.put(operation_id, plan, timeout_seconds)
        self._operation_service.create(
            batch_type=BatchType.PERFORMANCE_TEST,
            operation_id=operation_id,
            metadata={
                "operation_type": PerformanceOperationType.PERFORMANCE_TEST.value,
                "jmx_file": str(path),
            },
        )
        return operation_id
