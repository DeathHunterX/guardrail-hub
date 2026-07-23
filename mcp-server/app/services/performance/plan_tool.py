"""Server-side plan generation for the ``generate_performance_plan`` tool (C3.5).

One responsibility: take a submitted plan, **validate** it (a ``.jmx`` file is an
executable document, so it is checked against the safe-component allow-list —
ADR-0010 §5 S1 / INV3), **persist** the validated bytes through the plan store,
and return the reference under which it was stored. Nothing is enqueued, nothing
is executed, no dispatcher is touched, and there is no LLM / analysis here.

Everything is injected (governance Gates C/D/E): the validator and the plan
store are supplied by the composition root. This module reads no ``Settings``,
constructs no infrastructure, and imports no composition-root module. The plan is
opaque bytes to this service — all engine-specific judgement lives behind the
injected ``validator`` — so it stays engine-neutral.
"""

from __future__ import annotations

import uuid
from typing import Optional, Protocol


class PlanValidator(Protocol):
    """Validates a plan; raises if it is unsafe to store/execute."""

    def validate(self, plan: bytes | str) -> None: ...


class ValidatedPlanWriter(Protocol):
    """Server-side write side of the plan store (the concrete store's ``put``).

    Distinct from the frozen worker-facing ``PlanStore`` port (read-only ``get``):
    persistence is a server concern, so it is expressed as its own narrow seam and
    the frozen contract is left untouched.
    """

    def put(self, operation_id: str, plan: bytes, timeout_seconds: Optional[float] = None) -> None: ...


class PerformancePlanService:
    """Validate a submitted plan and store it, returning its reference."""

    def __init__(self, validator: PlanValidator, plan_store: ValidatedPlanWriter) -> None:
        self._validator = validator
        self._plan_store = plan_store

    def generate_plan(self, plan: str, timeout_seconds: Optional[float] = None) -> str:
        """Validate *plan*, persist it, and return its generated reference.

        Raises whatever the injected validator raises (e.g. ``JmxValidationError``)
        when the plan is unsafe or malformed — nothing is stored in that case.
        """
        # Validate BEFORE anything is written: an unsafe plan never reaches disk.
        self._validator.validate(plan)

        plan_id = str(uuid.uuid4())
        data = plan.encode() if isinstance(plan, str) else plan
        self._plan_store.put(plan_id, data, timeout_seconds)
        return plan_id
