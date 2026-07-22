"""Engine-neutral execution DTOs — the data half of the replaceable-engine seam.

These types describe *running a performance plan* in terms no engine owns: a
plan file, an output directory, a time bound, and the artifacts/outcome that
come back. JMeter (and, later, k6/Gatling) map their specifics onto these at the
adapter boundary (``app/integrations/jmeter/``); nothing here names ``.jmx``,
``.jtl``, ``-n -t``, or any engine flag (ADR-0010 §2.4 / §4.4). Keeping this the
sole vocabulary the Runtime speaks is what lets the engine be replaced without
touching orchestration.

Deliberately plain frozen dataclasses (stdlib only): these are internal
in-process values passed Runtime→Runner, not a wire contract, so they carry no
serialization framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


class ExecutionStatus(str, Enum):
    """Terminal outcome of one engine execution — engine-independent."""

    COMPLETED = "completed"   # the engine ran and exited cleanly
    FAILED = "failed"         # the engine ran and exited non-zero / errored
    TIMED_OUT = "timed_out"   # the policy timeout elapsed; process group killed
    CANCELLED = "cancelled"   # cancellation was observed; process group killed


class ArtifactKind(str, Enum):
    """Neutral classification of a produced artifact.

    Engines map their outputs onto these kinds at the adapter boundary (e.g.
    JMeter: ``.jtl`` → RESULTS, HTML dashboard → REPORT, ``jmeter.log`` → LOG).
    The Runtime persists/redacts by kind and never by engine file extension.
    """

    RESULTS = "results"       # raw per-sample results
    REPORT = "report"         # human-facing rendered report
    LOG = "log"               # engine run log
    METADATA = "metadata"     # execution metadata (timings, exit code, …)


@dataclass(frozen=True)
class Artifact:
    """One produced file and its neutral kind."""

    kind: ArtifactKind
    path: Path


@dataclass(frozen=True)
class ArtifactSet:
    """The collection of artifacts one execution produced (possibly empty)."""

    artifacts: Tuple[Artifact, ...] = ()

    def of_kind(self, kind: ArtifactKind) -> Tuple[Artifact, ...]:
        """Return the artifacts matching *kind* (order preserved)."""
        return tuple(a for a in self.artifacts if a.kind == kind)


@dataclass(frozen=True)
class ExecutionRequest:
    """Everything the Runner needs to run one plan — no engine specifics.

    ``plan_path`` and ``output_dir`` are absolute paths inside the operation's
    isolated workspace (the Runtime owns their creation/cleanup); the Runner
    only reads the plan and writes under ``output_dir``. ``timeout_seconds`` is
    the resolved policy bound the Runner enforces locally.
    """

    operation_id: str
    plan_path: Path
    output_dir: Path
    timeout_seconds: Optional[float] = None


@dataclass(frozen=True)
class ExecutionResult:
    """The outcome the Runner returns to the Runtime — no engine specifics."""

    status: ExecutionStatus
    exit_code: Optional[int]
    duration_seconds: float
    artifacts: ArtifactSet = field(default_factory=ArtifactSet)
    error: Optional[str] = None
