"""ReportChannelPersistence — the concrete ``PersistencePort`` (ADR-0010 §4.6).

The worker-side persistence: it turns a finished :class:`ExecutionResult` into an
:class:`OperationReport` (reading each already-redacted artifact file and
inlining its bytes) and hands it to a :class:`ReportSender` for delivery. It is a
pure consumer of the result — it never mutates execution state — and it raises if
delivery fails, so the Runtime's "cleanup after a definitive persist failure"
guarantee (INV5) holds.

Directory artifacts are skipped here (the JMeter runner reports the dashboard's
``index.html`` file, not the directory); bundling a whole report tree is a future
concern, not needed by the current engine.
"""

from __future__ import annotations

import base64

from app.integrations.performance.report_sender import ReportSender
from app.schemas.performance.report import ArtifactPayload, OperationReport
from app.services.performance.engine.dto import ExecutionResult


class ReportChannelPersistence:
    """``PersistencePort`` implementation that reports over the worker→server channel."""

    def __init__(self, sender: ReportSender) -> None:
        self._sender = sender

    def persist(self, operation_id: str, result: ExecutionResult) -> None:
        report = OperationReport(
            operation_id=operation_id,
            status=result.status.value,
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            error=result.error,
            artifacts=[
                ArtifactPayload(
                    kind=artifact.kind.value,
                    name=artifact.path.name,
                    content_b64=base64.b64encode(artifact.path.read_bytes()).decode("ascii"),
                )
                for artifact in result.artifacts.artifacts
                if artifact.path.is_file()
            ],
        )
        self._sender.send(report)  # raises ReportSendError on failure → propagates
