"""Filesystem-backed PlanStore and ReportStore — server-owned durable storage.

Concrete implementations of the `PlanStore` / `ReportStore` ports the
`WorkerCoordinator` depends on (ADR-0010 §4.5 / §4.6). Server-owned, under
injected base directories, mirroring the ZAP subsystem's on-disk convention
(``data/<engine>`` for inputs, ``reports/<engine>`` for outputs).

Additive and engine-neutral: the ports, `StoredPlan`, and `PlanNotFoundError`
are unchanged and imported from where they are defined; nothing here is
engine-specific (a plan is opaque bytes, a report is neutral artifacts). Base
directories are **injected** — no `Settings` are read here (governance Gate E);
the composition root resolves the paths.
"""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path
from typing import Optional

from app.schemas.performance.report import OperationReport
from app.services.performance.worker_api import PlanNotFoundError, StoredPlan

_PLAN_FILE = "plan"
_PLAN_META = "meta.json"
_REPORT_META = "report.json"
_ARTIFACTS_DIR = "artifacts"


class UnsafeOperationIdError(ValueError):
    """An operation_id that could escape the store root (path traversal)."""


def _safe_segment(operation_id: str) -> str:
    """Reject an operation_id that could traverse outside the store root."""
    if not operation_id or "/" in operation_id or "\\" in operation_id or ".." in operation_id:
        raise UnsafeOperationIdError(operation_id)
    return operation_id


class FilesystemPlanStore:
    """Server-owned validated-plan store — plans under ``<base>/plans/<op_id>/``."""

    def __init__(self, base_dir: Path) -> None:
        self._base = Path(base_dir)

    def put(self, operation_id: str, plan: bytes, timeout_seconds: Optional[float] = None) -> None:
        """Store the (already-validated) plan bytes + resolved timeout for an operation."""
        directory = self._op_dir(operation_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / _PLAN_FILE).write_bytes(plan)
        (directory / _PLAN_META).write_text(json.dumps({"timeout_seconds": timeout_seconds}))

    def get(self, operation_id: str) -> StoredPlan:
        """Return the stored plan, or raise :class:`PlanNotFoundError`."""
        directory = self._op_dir(operation_id)
        plan_path = directory / _PLAN_FILE
        if not plan_path.is_file():
            raise PlanNotFoundError(operation_id)
        timeout: Optional[float] = None
        meta_path = directory / _PLAN_META
        if meta_path.is_file():
            timeout = json.loads(meta_path.read_text()).get("timeout_seconds")
        return StoredPlan(plan=plan_path.read_bytes(), timeout_seconds=timeout)

    def _op_dir(self, operation_id: str) -> Path:
        return self._base / "plans" / _safe_segment(operation_id)


class FilesystemReportStore:
    """Server-owned durable report store — reports under ``<base>/<op_id>/``."""

    def __init__(self, base_dir: Path) -> None:
        self._base = Path(base_dir)

    def save(self, report: OperationReport) -> None:
        """Persist a finished operation's (already-redacted) report + artifacts.

        Idempotent per operation: a prior report directory for the same
        operation is replaced.
        """
        directory = self._op_dir(report.operation_id)
        if directory.exists():
            shutil.rmtree(directory)
        artifacts_dir = directory / _ARTIFACTS_DIR
        artifacts_dir.mkdir(parents=True)
        for artifact in report.artifacts:
            name = Path(artifact.name).name  # basename only (defense in depth)
            (artifacts_dir / name).write_bytes(base64.b64decode(artifact.content_b64))
        (directory / _REPORT_META).write_text(
            json.dumps(
                {
                    "operation_id": report.operation_id,
                    "status": report.status,
                    "exit_code": report.exit_code,
                    "duration_seconds": report.duration_seconds,
                    "error": report.error,
                    "artifacts": [
                        {"kind": a.kind, "name": Path(a.name).name} for a in report.artifacts
                    ],
                },
                indent=2,
            )
        )

    def _op_dir(self, operation_id: str) -> Path:
        return self._base / _safe_segment(operation_id)
