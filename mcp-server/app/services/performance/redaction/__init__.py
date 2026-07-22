"""Artifact redaction for the Performance capability (ADR-0010 §5 S4).

Public surface: the pure :func:`redact_text` core and the file/artifact-set
helpers the Runtime calls immediately before persistence.
"""

from app.services.performance.redaction.redactor import (
    redact_artifacts,
    redact_file,
    redact_text,
)

__all__ = [
    "redact_artifacts",
    "redact_file",
    "redact_text",
]
