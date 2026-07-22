"""The operation report — the worker→server wire contract for a finished run.

When a worker finishes (or fails/cancels) an operation it reports the outcome
plus its already-redacted artifacts over the report channel (ADR-0010 §4.6). The
server persists this durably. Artifact bytes travel base64-encoded inside the
JSON body (not a shared volume), keeping the worker inbound-channel-free and the
transport filesystem-agnostic.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ArtifactPayload(BaseModel):
    """One redacted artifact, carried inline."""

    kind: str = Field(..., description="Neutral ArtifactKind value (results/report/log/metadata).")
    name: str = Field(..., description="Artifact file name (basename only).")
    content_b64: str = Field(..., description="Base64 of the (already-redacted) artifact bytes.")


class OperationReport(BaseModel):
    """Terminal outcome of one operation, reported by the worker."""

    operation_id: str
    status: str = Field(..., description="Neutral ExecutionStatus value.")
    exit_code: Optional[int] = None
    duration_seconds: float = 0.0
    error: Optional[str] = None
    artifacts: List[ArtifactPayload] = Field(default_factory=list)
