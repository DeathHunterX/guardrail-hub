"""Registry-specific exceptions for the Intelligence Layer.

The registry lifecycle distinguishes two error classes:

- ``RegistryLoadError`` — the registry YAML could not be loaded at all.
  File missing, file unreadable, YAML syntax error, environment variable
  unresolved, required field missing, or field value unparseable. These
  errors are surfaced before any record is registered.

- ``RegistryValidationError`` — the YAML loaded successfully but the
  records it produced violate an invariant. Duplicate ``provider_id``,
  model referencing an unknown ``provider_id``, an invalid enum value,
  a negative priority. These errors are surfaced after loading.

The separation lets the loader and the validator evolve independently
without coupling diagnostics. Both inherit from ``LLMConfigurationError``
so the standard error-mapping at the routing layer can translate either
into HTTP 500 / 503 (configuration problems at startup) without special
casing.

Authority: Decision 0014 §3 — "validation is separate from loading".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from app.intelligence.exceptions.llm import LLMConfigurationError


@dataclass(frozen=True, slots=True)
class LoadIssue:
    """A single load issue: file, position, and message."""

    file_path: str
    position: str  # e.g. "providers[2].connection.base_url" or "(root)"
    message: str


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A single validation issue: entity type, entity id, field, message."""

    entity_type: str  # 'provider' or 'model'
    entity_id: str
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class LoadReport:
    """Structured report of all issues encountered while loading a registry."""

    issues: Sequence[LoadIssue] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return len(self.issues) == 0

    @property
    def count(self) -> int:
        return len(self.issues)

    def __str__(self) -> str:
        if self.ok:
            return "LoadReport: ok"
        lines = [f"LoadReport: {self.count} issue(s)"]
        for issue in self.issues:
            lines.append(f"  - {issue.file_path} :: {issue.position}: {issue.message}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Structured report of all validation issues for a registry."""

    issues: Sequence[ValidationIssue] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return len(self.issues) == 0

    @property
    def count(self) -> int:
        return len(self.issues)


class RegistryLoadError(LLMConfigurationError):
    """Raised when a registry YAML cannot be loaded.

    Carries a structured :class:`LoadReport` so callers can render diagnostics
    with file paths and structured positions (e.g. ``providers[2].connection``).
    """

    def __init__(self, report: LoadReport) -> None:
        self.report = report
        super().__init__(str(report))


class RegistryValidationError(LLMConfigurationError):
    """Raised when registry records fail validation.

    Carries a structured :class:`ValidationReport` so callers can render
    per-record diagnostics with the offending field.
    """

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        lines = [f"Registry validation failed ({report.count} error(s)):"]
        for issue in report.issues:
            lines.append(
                f"  - {issue.entity_type}/{issue.entity_id}."
                f"{issue.field}: {issue.message}"
            )
        super().__init__("\n".join(lines))


__all__ = [
    "LoadIssue",
    "LoadReport",
    "ValidationIssue",
    "ValidationReport",
    "RegistryLoadError",
    "RegistryValidationError",
]
