"""JMeter implementation of the ``PerformanceRunner`` seam.

This is the one place that knows JMeter: it builds the ``jmeter -n`` command,
runs it in its own process group (via :mod:`.process_group`), enforces the
request's timeout locally, enacts cancellation by killing that group, and maps
JMeter's output files onto the neutral :class:`ArtifactSet`. It returns a neutral
:class:`ExecutionResult` and — per the protocol — never raises for an ordinary
engine failure (a non-zero exit is a ``FAILED`` result, a missing binary is a
``FAILED`` result). The Runtime, Service, and dispatcher never see any of this
(ADR-0010 §4.4).

Everything the run produces is written under ``request.output_dir`` (a fresh,
isolated workspace directory the Runtime owns); this Runner reads only
``request.plan_path`` and writes only under ``output_dir``.
"""

from __future__ import annotations

import time
from pathlib import Path
from threading import Event
from typing import List

from app.services.performance.engine.dto import (
    Artifact,
    ArtifactKind,
    ArtifactSet,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)
from app.integrations.jmeter.process_group import (
    ProcessTermination,
    run_in_process_group,
)

_DEFAULT_BINARY = "jmeter"

# Output filenames the Runner asks JMeter to produce, mapped to neutral kinds.
_RESULTS_NAME = "results.jtl"
_REPORT_DIR_NAME = "report"
_JMETER_LOG_NAME = "jmeter.log"
_STDOUT_NAME = "jmeter-stdout.log"
_STDERR_NAME = "jmeter-stderr.log"


class JMeterRunner:
    """Runs a validated JMeter plan in non-GUI mode. Implements ``PerformanceRunner``."""

    def __init__(
        self,
        binary: str = _DEFAULT_BINARY,
        *,
        grace_seconds: float = 10.0,
        poll_seconds: float = 0.1,
    ) -> None:
        self._binary = binary
        self._grace_seconds = grace_seconds
        self._poll_seconds = poll_seconds

    def run(self, request: ExecutionRequest, cancel: Event) -> ExecutionResult:
        out = request.output_dir
        results_path = out / _RESULTS_NAME
        report_dir = out / _REPORT_DIR_NAME
        jmeter_log = out / _JMETER_LOG_NAME
        stdout_path = out / _STDOUT_NAME
        stderr_path = out / _STDERR_NAME

        command = self._build_command(request.plan_path, results_path, report_dir, jmeter_log)

        started = time.monotonic()
        try:
            outcome = run_in_process_group(
                command,
                timeout_seconds=request.timeout_seconds,
                cancel=cancel,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                grace_seconds=self._grace_seconds,
                poll_seconds=self._poll_seconds,
            )
        except FileNotFoundError as exc:
            # Infrastructure fault (engine not installed): fail the operation
            # rather than crash the worker (protocol: never raise for a failure).
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                exit_code=None,
                duration_seconds=time.monotonic() - started,
                error=f"JMeter binary '{self._binary}' not found: {exc}",
            )

        duration = time.monotonic() - started
        artifacts = self._collect_artifacts(
            results_path, report_dir, jmeter_log, stdout_path, stderr_path
        )
        status = _map_status(outcome.termination, outcome.exit_code)
        error = None
        if status is ExecutionStatus.FAILED:
            error = f"JMeter exited with code {outcome.exit_code}"
        return ExecutionResult(
            status=status,
            exit_code=outcome.exit_code,
            duration_seconds=duration,
            artifacts=artifacts,
            error=error,
        )

    def _build_command(
        self, plan_path: Path, results_path: Path, report_dir: Path, jmeter_log: Path
    ) -> List[str]:
        """Assemble the ``jmeter -n`` command. The only JMeter-flag knowledge."""
        return [
            self._binary,
            "-n",                      # non-GUI / headless
            "-t", str(plan_path),      # the validated test plan
            "-l", str(results_path),   # raw results (JTL)
            "-j", str(jmeter_log),     # engine log
            "-e",                      # generate the HTML dashboard after the run
            "-o", str(report_dir),     # dashboard output dir (must not pre-exist)
        ]

    def _collect_artifacts(
        self,
        results_path: Path,
        report_dir: Path,
        jmeter_log: Path,
        stdout_path: Path,
        stderr_path: Path,
    ) -> ArtifactSet:
        """Map whichever output files JMeter actually produced onto neutral kinds."""
        found: List[Artifact] = []
        if results_path.is_file():
            found.append(Artifact(ArtifactKind.RESULTS, results_path))
        report_index = report_dir / "index.html"
        if report_index.is_file():
            found.append(Artifact(ArtifactKind.REPORT, report_index))
        elif report_dir.is_dir():
            found.append(Artifact(ArtifactKind.REPORT, report_dir))
        for log in (jmeter_log, stdout_path, stderr_path):
            if log.is_file():
                found.append(Artifact(ArtifactKind.LOG, log))
        return ArtifactSet(tuple(found))


def _map_status(termination: ProcessTermination, exit_code) -> ExecutionStatus:
    if termination is ProcessTermination.TIMED_OUT:
        return ExecutionStatus.TIMED_OUT
    if termination is ProcessTermination.CANCELLED:
        return ExecutionStatus.CANCELLED
    return ExecutionStatus.COMPLETED if exit_code == 0 else ExecutionStatus.FAILED
