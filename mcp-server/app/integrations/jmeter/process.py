"""The JMeter subprocess adapter.

Owns exactly one thing: turning a JMX file into a finished JMeter process and
the files it wrote. Launch, timeout, cancellation, cleanup, exit code — and
nothing above that. It does not read the JTL it produced, does not know what an
Operation is, and never touches the database.

The command is always JMeter's non-GUI form::

    jmeter -n -t <test-plan.jmx> -l <test-results.jtl> -e -o <html-report/> -j <engine.log>

Which JMeter that resolves to is the worker image's business, not a setting —
see ``docker/jmeter/Dockerfile``.
"""

import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from app.core.mcp_logger import MCPLogger


class JMeterProcessError(RuntimeError):
    """JMeter could not be started at all (missing binary, unusable workspace)."""


@dataclass(frozen=True)
class JMeterRunOutcome:
    """What one JMeter process did.

    ``exit_code`` is JMeter's own: 0 is a completed run. A non-zero code means
    the engine itself failed — note that individual failed *samples* do not
    produce a non-zero exit code, so this says nothing about whether the target
    behaved well. That judgment needs the JTL.
    """

    exit_code: int
    timed_out: bool
    cancelled: bool
    workspace: str

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.cancelled


class JMeterProcessRunner:
    """Runs JMeter as a subprocess, one run at a time per instance."""

    #: Fixed filenames inside a run workspace. The Runtime builds public URLs
    #: from these, so they are part of the contract between the two and are
    #: deliberately not configurable.
    #:
    #: The names describe the *content*, not the tool, because a run package is
    #: downloaded, attached to tickets and archived — read months later, by
    #: someone who did not run it. "results.jtl" and "report/" mean nothing out
    #: of context; "test-results.jtl" and "html-report/" survive the trip.
    #: These are physical names only: the ``JMeterArtifacts`` JSON keys they are
    #: reported under are unchanged.
    PLAN_FILE = "test-plan.jmx"
    RESULTS_FILE = "test-results.jtl"
    REPORT_DIR = "html-report"
    ENGINE_LOG = "engine.log"

    def __init__(
        self,
        binary: str = "jmeter",
        terminate_grace_seconds: float = 15.0,
        logger: Optional[MCPLogger] = None,
    ) -> None:
        """
        Args:
            binary: JMeter executable, resolved on PATH. Not a version selector.
            terminate_grace_seconds: How long a terminated run gets to flush its
                JTL after SIGTERM before it is killed.
            logger: Optional logger; one is created if omitted.
        """
        self._binary = binary
        self._grace = terminate_grace_seconds
        self._logger = logger or MCPLogger("JMeterProcessRunner")
        self._processes: Dict[str, subprocess.Popen] = {}
        self._cancelled: set = set()
        self._lock = threading.Lock()

    # ── Execution ────────────────────────────────────────────────────────

    def run(
        self,
        operation_id: str,
        workspace: str,
        jmx_xml: str,
        timeout_seconds: float,
    ) -> JMeterRunOutcome:
        """Write *jmx_xml* into *workspace* and run JMeter over it to completion.

        Blocks until the process ends, times out, or is cancelled. On timeout or
        cancellation the process is asked to stop first (SIGTERM) and only then
        killed, so JMeter can flush the results it has already collected —
        partial results from a 20-minute run are worth far more than a clean
        kill.

        Raises:
            JMeterProcessError: JMeter could not be started at all.
        """
        workspace_path = self._prepare_workspace(workspace, jmx_xml)
        command = self._build_command(workspace_path)

        self._logger.info(
            "Starting JMeter for operation '%s' (timeout=%.0fs): %s",
            operation_id,
            timeout_seconds,
            " ".join(command),
        )

        try:
            process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
                command,
                cwd=str(workspace_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except (OSError, ValueError) as exc:
            raise JMeterProcessError(
                f"Could not start JMeter ('{self._binary}'): {exc}"
            ) from exc

        with self._lock:
            self._processes[operation_id] = process

        timed_out = False
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._logger.warning(
                "JMeter for operation '%s' exceeded %.0fs — terminating",
                operation_id,
                timeout_seconds,
            )
            self._stop(process)
        finally:
            with self._lock:
                self._processes.pop(operation_id, None)
                cancelled = operation_id in self._cancelled
                self._cancelled.discard(operation_id)

        return JMeterRunOutcome(
            exit_code=process.returncode if process.returncode is not None else -1,
            timed_out=timed_out,
            cancelled=cancelled,
            workspace=str(workspace_path),
        )

    def cancel(self, operation_id: str) -> bool:
        """Stop the run for *operation_id*. Returns whether one was running.

        Safe to call for an operation that already finished or never started —
        cancellation racing with completion is normal, not an error.
        """
        with self._lock:
            process = self._processes.get(operation_id)
            if process is None:
                return False
            self._cancelled.add(operation_id)

        self._logger.info("Cancelling JMeter run for operation '%s'", operation_id)
        self._stop(process)
        return True

    # ── Internals ────────────────────────────────────────────────────────

    def _stop(self, process: subprocess.Popen) -> None:
        """SIGTERM, wait out the grace period, then SIGKILL.

        Signals the whole process group: JMeter's launcher spawns a JVM child,
        and terminating only the launcher would leave the JVM generating load
        against the target — the worst possible orphan for a load engine.
        """
        for send_signal, label in ((signal.SIGTERM, "SIGTERM"), (signal.SIGKILL, "SIGKILL")):
            if process.poll() is not None:
                return
            try:
                self._signal_group(process, send_signal)
            except OSError as exc:  # pragma: no cover - process already reaped
                self._logger.debug("Could not send %s: %s", label, exc)
                return
            try:
                process.wait(timeout=self._grace)
                return
            except subprocess.TimeoutExpired:
                self._logger.warning(
                    "JMeter did not exit after %s — escalating", label
                )

    @staticmethod
    def _signal_group(process: subprocess.Popen, send_signal: int) -> None:
        """Signal the process group started by ``start_new_session=True``."""
        import os  # noqa: PLC0415

        os.killpg(os.getpgid(process.pid), send_signal)

    def _prepare_workspace(self, workspace: str, jmx_xml: str) -> Path:
        """Create a clean workspace containing the plan to execute.

        The path is resolved to an absolute one **before** anything else uses
        it, and that is load-bearing rather than tidiness: :meth:`run` launches
        JMeter with ``cwd`` set to this directory while passing the same path in
        argv. A relative workspace — which is what ``jmeter_workspace_dir``
        ("./public/report/jmeter/detail-report") produces — would then be
        resolved a second time against that cwd, so JMeter looks for
        ``<workspace>/<workspace>/plan.jmx`` and exits 1 before running a single
        sample. Resolving once here fixes it for every argument at the source.
        """
        path = Path(workspace).resolve()
        try:
            # JMeter refuses to write its HTML dashboard into a non-empty
            # directory, so a re-run of the same operation starts clean.
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)
            (path / self.PLAN_FILE).write_text(jmx_xml, encoding="utf-8")
        except OSError as exc:
            raise JMeterProcessError(
                f"Could not prepare the JMeter workspace at '{workspace}': {exc}"
            ) from exc
        return path

    def _build_command(self, workspace: Path) -> list:
        return [
            self._binary,
            "-n",
            "-t",
            str(workspace / self.PLAN_FILE),
            "-l",
            str(workspace / self.RESULTS_FILE),
            "-e",
            "-o",
            str(workspace / self.REPORT_DIR),
            "-j",
            str(workspace / self.ENGINE_LOG),
        ]
