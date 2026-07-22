"""PerformanceRuntime — the composition root of one operation's execution.

A **pure orchestrator** (ADR-0010 §4.4): it owns the execution lifecycle and
nothing else. It parses nothing, stores nothing, invokes no ``subprocess``, knows
no engine and no Docker. It sequences five independent collaborators inside the
workspace it owns, in the one order the lifecycle mandates:

    Workspace → Validate → Execute → Collect → Redact → Persist → Cleanup

Cleanup is not a step it calls; it is the workspace context manager's guarantee,
so it runs *after* persistence — on success, or after a definitive persist
failure, or after a rejected plan — and never mid-execution (INV5).

Contract of :meth:`execute`:

- a plan that runs (whatever the engine outcome) returns its neutral
  :class:`ExecutionResult`, after its artifacts are redacted and persisted;
- a plan the validator rejects, or a persistence that fails, raises — and the
  workspace is still destroyed. Both are the caller's (worker's) cue to mark the
  operation FAILED (at-most-once; no retry — ADR-0010 §4.6).
"""

from __future__ import annotations

from threading import Event
from typing import Callable, Optional

from app.services.performance.engine.dto import (
    ArtifactSet,
    ExecutionRequest,
    ExecutionResult,
)
from app.services.performance.redaction import redact_artifacts
from app.services.performance.runtime.ports import PlanValidator, PersistencePort
from app.services.performance.runtime.workspace import WorkspaceManager

# Redaction is a collaborator, injected as a callable so it stays independent and
# swappable; the neutral in-repo redactor is the default.
Redactor = Callable[[ArtifactSet], None]


class PerformanceRuntime:
    """Orchestrates the per-operation execution lifecycle over injected collaborators."""

    def __init__(
        self,
        *,
        workspaces: WorkspaceManager,
        validator: PlanValidator,
        runner,  # PerformanceRunner (protocol) — untyped here to avoid importing the seam name twice
        persistence: PersistencePort,
        redactor: Redactor = redact_artifacts,
    ) -> None:
        self._workspaces = workspaces
        self._validator = validator
        self._runner = runner
        self._persistence = persistence
        self._redactor = redactor

    def execute(
        self,
        operation_id: str,
        plan: bytes,
        *,
        timeout_seconds: Optional[float] = None,
        cancel: Optional[Event] = None,
    ) -> ExecutionResult:
        """Run *plan* for *operation_id* through the full lifecycle.

        See the module docstring for the return/raise contract. The workspace is
        always destroyed on exit, after persistence.
        """
        cancel = cancel or Event()
        with self._workspaces.workspace(operation_id) as workspace:
            # Validate before any engine invocation (defense in depth on the worker).
            self._validator.validate(plan)
            workspace.plan_path.write_bytes(plan)

            # Execute + Collect: the Runner runs the engine and returns artifacts.
            request = ExecutionRequest(
                operation_id=operation_id,
                plan_path=workspace.plan_path,
                output_dir=workspace.output_dir,
                timeout_seconds=timeout_seconds,
            )
            result = self._runner.run(request, cancel)

            # Redact on the worker, then persist — before cleanup (INV4/INV5).
            self._redactor(result.artifacts)
            self._persistence.persist(operation_id, result)
            return result
        # workspace.__exit__ destroys the tree here, after persist / on any raise.
