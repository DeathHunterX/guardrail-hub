"""Per-operation workspace lifecycle — the first and last stages of an execution.

The Runtime runs one operation entirely inside an **isolated workspace** it
owns, and destroys that workspace when the operation is over. Two invariants
from [ADR-0010](../../../../../.ai/decisions/0010-performance-engine-capability.md)
are enforced here and nowhere else:

- **INV2** — one workspace belongs to exactly one operation and is never reused.
  Each workspace is keyed by ``operation_id``; :meth:`WorkspaceManager.create`
  clears any stale remnant so every operation starts from an empty tree.
- **INV5** — cleanup always occurs, on success *and* failure, and (per the
  execution lifecycle) *after* persistence, never immediately after execution.
  :meth:`WorkspaceManager.workspace` is a context manager that wraps the whole
  ``validate → execute → collect → redact → persist`` sequence; its ``finally``
  destroys the workspace once — after persist on the happy path, or on a
  confirmed failure if any stage raised.

This module is engine-neutral: it deals in a plan file, an output directory, and
a logs directory — never JMeter specifics.
"""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class InvalidOperationIdError(ValueError):
    """Raised when an operation_id could escape the workspace root.

    operation_ids are server-generated, but a workspace path is built from one,
    so path separators / traversal are rejected as defense in depth (a workspace
    must never be able to write outside its own root — ADR-0010 §5 S2).
    """


@dataclass(frozen=True)
class Workspace:
    """The isolated filesystem area for one operation.

    ``plan_path`` is where the (already-validated) plan is written; the Runner
    reads it and writes only under ``output_dir`` / ``logs_dir``. All four live
    under ``root``, which is destroyed as a unit at cleanup.
    """

    operation_id: str
    root: Path
    plan_path: Path
    output_dir: Path
    logs_dir: Path


class WorkspaceManager:
    """Creates and destroys per-operation workspaces under one base directory."""

    def __init__(self, base_dir: Path) -> None:
        self._base = Path(base_dir)

    def create(self, operation_id: str) -> Workspace:
        """Create a fresh, empty workspace for *operation_id* (INV2).

        Any pre-existing directory for this id (a crash remnant) is removed
        first so the operation never inherits stale state.
        """
        root = self._operation_root(operation_id)
        if root.exists():
            shutil.rmtree(root)
        output_dir = root / "output"
        logs_dir = root / "logs"
        output_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)
        return Workspace(
            operation_id=operation_id,
            root=root,
            plan_path=root / "plan",
            output_dir=output_dir,
            logs_dir=logs_dir,
        )

    def cleanup(self, workspace: Workspace) -> None:
        """Destroy *workspace*. Idempotent — a missing tree is not an error."""
        shutil.rmtree(workspace.root, ignore_errors=True)

    @contextmanager
    def workspace(self, operation_id: str) -> Iterator[Workspace]:
        """Yield a fresh workspace and guarantee its destruction (INV5).

        Cleanup runs in ``finally`` — so it happens after the caller's whole
        lifecycle body (which ends with persistence) on success, and after a
        confirmed failure if the body raises. Never mid-execution.
        """
        ws = self.create(operation_id)
        try:
            yield ws
        finally:
            self.cleanup(ws)

    def _operation_root(self, operation_id: str) -> Path:
        if not operation_id or "/" in operation_id or "\\" in operation_id or ".." in operation_id:
            raise InvalidOperationIdError(operation_id)
        return self._base / "operations" / operation_id
