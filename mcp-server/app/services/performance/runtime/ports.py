"""Ports the Runtime depends on — abstractions, never concrete implementations.

The Runtime is a pure orchestrator (ADR-0010 §4.4). It must not know *how* a plan
is validated or *where* artifacts are persisted — only that a collaborator can do
each. These protocols are those seams:

- :class:`PlanValidator` — validate a plan, raising on rejection. The JMeter
  implementation (``integrations/jmeter``) wraps the JMX whitelist validator;
  the Runtime never imports it, so it carries no engine-specific dependency.
- :class:`PersistencePort` — durably persist an operation's (already-redacted)
  result. The concrete implementation is the worker→server report channel added
  in Phase 2; the Runtime names no store.

Both are ``runtime_checkable`` so a structural fake satisfies them in tests
without inheritance.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.services.performance.engine.dto import ExecutionResult


@runtime_checkable
class PlanValidator(Protocol):
    """Validate a plan before execution; raise if it must not run."""

    def validate(self, plan: bytes | str) -> None:
        """Return ``None`` if the plan is safe to execute, else raise."""
        ...


@runtime_checkable
class PersistencePort(Protocol):
    """Durably persist one operation's redacted result; raise on failure."""

    def persist(self, operation_id: str, result: ExecutionResult) -> None:
        """Persist *result* for *operation_id*. Raise if it could not be stored."""
        ...
