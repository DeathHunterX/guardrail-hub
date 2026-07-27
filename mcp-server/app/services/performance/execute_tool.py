"""Enqueue a Performance operation for a stored plan (``execute_performance_test``).

The server side of "run this plan" (ADR-0010 §4.12 / C3.6). It does **not** run
anything: it retrieves the already-validated plan, checks preconditions, and
creates a ``QUEUED`` Performance operation through the existing
``OperationService`` — the running dispatcher then assigns it and the worker
pulls and executes. This module never touches the runtime, the worker, the
dispatcher, or the pool.

plan_id ↔ operation_id — **identity.** The frozen ``WorkerCoordinator`` fetches
the plan by ``operation_id`` (``PlanStore.get(operation_id)``), and the plan was
stored under its plan_id in the same store. Creating the operation with
``operation_id == plan_id`` makes the already-stored bytes retrievable by the
worker with no copy and no second write: the plan reference is promoted to the
operation that runs it (a single source of truth), and a plan can be executed
exactly once (operation-id uniqueness).

The operation type is stamped into ``metadata["operation_type"]`` — the exact key
the dispatcher's scoped queue read matches (INV12) — and is never rewritten
afterward (INV13). Everything is injected (Gates C/D/E): the plan store and the
operation service come from the composition root; this module reads no
``Settings`` and constructs no infrastructure. The plan is opaque bytes to it.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol

from app.constants.batch import BatchType
from app.schemas.performance.operation_type import PerformanceOperationType
from app.services.performance.worker_api import PlanNotFoundError, StoredPlan


class PlanReader(Protocol):
    """Read side of the plan store (the frozen ``PlanStore.get`` contract)."""

    def get(self, operation_id: str) -> StoredPlan: ...


class OperationCreator(Protocol):
    """Create/lookup surface of the existing ``OperationService`` used here."""

    def create(
        self,
        batch_type: str,
        metadata: Optional[dict[str, Any]] = None,
        log_path: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> str: ...

    def get(self, operation_id: str) -> Any: ...


class PlanAlreadyExecutedError(Exception):
    """A plan reference already has an operation — it can be executed only once."""

    def __init__(self, plan_id: str) -> None:
        super().__init__(f"plan '{plan_id}' has already been executed")
        self.plan_id = plan_id


class PerformanceExecuteService:
    """Enqueue a Performance operation for a stored plan; never executes it."""

    def __init__(self, plan_store: PlanReader, operation_service: OperationCreator) -> None:
        self._plan_store = plan_store
        self._operation_service = operation_service

    def execute(self, plan_id: str) -> str:
        """Enqueue the stored plan *plan_id* and return the operation id (== plan_id).

        Raises:
            PlanNotFoundError: No stored plan for *plan_id* (nothing is queued).
            PlanAlreadyExecutedError: An operation already exists for this plan.
        """
        # Precondition 1 — the plan must exist and load (retrieve via the store).
        # Fail fast here rather than queueing an operation whose plan is missing.
        self._plan_store.get(plan_id)

        # Precondition 2 — identity mapping means one plan → one operation.
        if self._operation_service.get(plan_id) is not None:
            raise PlanAlreadyExecutedError(plan_id)

        # Create the QUEUED operation. operation_id == plan_id so the worker's
        # PlanStore.get(operation_id) resolves to the stored plan. The type is
        # stamped where the dispatcher's scoped read looks (INV12), never rewritten.
        return self._operation_service.create(
            batch_type=BatchType.PERFORMANCE_TEST,
            operation_id=plan_id,
            metadata={
                "operation_type": PerformanceOperationType.PERFORMANCE_TEST.value,
                "plan_id": plan_id,
            },
        )
