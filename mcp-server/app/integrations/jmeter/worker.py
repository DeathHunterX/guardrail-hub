"""JMeterWorker — the execution host.

**What Worker owns:** accepting one assignment at a time, running the JMeter
process for it via :class:`JMeterProcessRunner`, tracking that run's local state,
and answering when the server asks. Plus its own registration and heartbeat
against the server.

**What Worker does not own — and this is the load-bearing part:** it never
persists operation state, never parses the JTL, never interprets a result, and
never makes a lifecycle decision. It reports *what happened locally*; deciding
what that means for the Operation belongs to ``JMeterRuntime``
(``architecture/jmeter-engine/runtime-responsibility.md`` §3). A worker that
wrote to the Operations table would be a second lifecycle owner, and the whole
point of the boundary is that there is exactly one.

That boundary holds at two levels, and it is worth being precise about which:

* **By imports** — this class reaches no DAO and no ``OperationService``, and
  neither does anything it imports.
* **By deployment** — ``docker/jmeter/Dockerfile`` copies only the trees the
  agent actually imports, so ``app/dao/`` and ``app/services/`` are not in the
  worker image at all. ``tests/integrations/jmeter/test_jmeter_worker_isolation.py``
  fails if the import closure ever grows past that allowlist, which is what
  keeps the Dockerfile's copy list honest.

The worker is long-lived (so heartbeats mean something); the JMeter process it
launches per operation is short-lived. Registration and heartbeat are not here
either — they are the container's sidecar script, exactly as for a ZAP worker.
"""

import threading
from typing import Dict, Optional

from app.core.mcp_logger import MCPLogger
from app.integrations.jmeter.process import (
    JMeterProcessError,
    JMeterProcessRunner,
    JMeterRunOutcome,
)
from app.schemas.tools.jmeter.worker_assignment import (
    JMeterAssignmentAck,
    JMeterAssignmentRequest,
    JMeterExecutionState,
    JMeterExecutionStateReport,
)


class JMeterWorker:
    """One long-lived JMeter execution host, running at most one plan at a time."""

    def __init__(
        self,
        worker_id: str,
        workspace_root: str,
        runner: Optional[JMeterProcessRunner] = None,
        max_run_seconds: int = 7800,
        logger: Optional[MCPLogger] = None,
    ) -> None:
        """
        Args:
            worker_id: This worker's registered identity.
            workspace_root: Directory under which each run gets its own
                ``{operation_id}/`` workspace.
            runner: The subprocess adapter; injectable for tests.
            max_run_seconds: Ceiling applied to any single run.
            logger: Optional logger; one is created if omitted.
        """
        self._worker_id = worker_id
        self._workspace_root = workspace_root.rstrip("/")
        self._runner = runner or JMeterProcessRunner()
        self._max_run_seconds = max_run_seconds
        self._logger = logger or MCPLogger("JMeterWorker")

        self._reports: Dict[str, JMeterExecutionStateReport] = {}
        self._current_operation_id: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def worker_id(self) -> str:
        return self._worker_id

    # ── Assignment intake ────────────────────────────────────────────────

    def accept(self, assignment: JMeterAssignmentRequest) -> JMeterAssignmentAck:
        """Take *assignment* and start running it in the background.

        Returns immediately: a load test runs for minutes and the server's
        request must not be held open for it. The run's progress is read back
        through :meth:`report_for`.

        Declining is a normal answer, not an error. A worker already running an
        operation returns ``accepted=False`` and the server puts the operation
        back on the queue — which is why this never raises for a busy worker.
        """
        operation_id = assignment.operation_id

        with self._lock:
            if self._current_operation_id is not None:
                return JMeterAssignmentAck(
                    operation_id=operation_id,
                    worker_id=self._worker_id,
                    accepted=False,
                    message=(
                        f"Worker '{self._worker_id}' is already running operation "
                        f"'{self._current_operation_id}'."
                    ),
                )
            if assignment.jmx_plan is None:
                return JMeterAssignmentAck(
                    operation_id=operation_id,
                    worker_id=self._worker_id,
                    accepted=False,
                    message="The assignment carried no test plan to execute.",
                )
            self._current_operation_id = operation_id
            self._reports[operation_id] = self._report(
                operation_id, JMeterExecutionState.ACCEPTED, "Assignment accepted."
            )

        thread = threading.Thread(
            target=self._execute,
            args=(assignment,),
            name=f"jmeter-run-{operation_id[:8]}",
            daemon=True,
        )
        thread.start()

        return JMeterAssignmentAck(
            operation_id=operation_id, worker_id=self._worker_id, accepted=True
        )

    def report_for(self, operation_id: str) -> Optional[JMeterExecutionStateReport]:
        """The latest state of *operation_id*, or ``None`` if unknown here.

        ``None`` is meaningful: it means this worker has no record of the run —
        it restarted, or was never given it. The Runtime treats that as a state
        to handle, not as an error.
        """
        with self._lock:
            return self._reports.get(operation_id)

    def cancel(self, operation_id: str) -> bool:
        """Stop the run for *operation_id*. Returns whether one was running."""
        return self._runner.cancel(operation_id)

    # ── Execution ────────────────────────────────────────────────────────

    def _execute(self, assignment: JMeterAssignmentRequest) -> None:
        """Run one plan to completion and record the outcome. Never raises."""
        operation_id = assignment.operation_id
        workspace = f"{self._workspace_root}/{operation_id}"
        timeout = self._timeout_for(assignment)

        self._set_report(
            operation_id, JMeterExecutionState.RUNNING, "JMeter is running."
        )
        try:
            outcome = self._runner.run(
                operation_id=operation_id,
                workspace=workspace,
                jmx_xml=assignment.jmx_plan,
                timeout_seconds=timeout,
            )
            state, message = self._interpret(outcome, timeout)
            self._set_report(operation_id, state, message, workspace=outcome.workspace)
        except JMeterProcessError as exc:
            self._logger.error(
                "JMeter could not start for operation '%s': %s", operation_id, exc
            )
            self._set_report(operation_id, JMeterExecutionState.FAILED, str(exc))
        except Exception as exc:  # pylint: disable=broad-except
            # A worker thread dying silently would leave the Runtime polling a
            # state that never advances until its own timeout. Record it instead.
            self._logger.error(
                "Unexpected failure running operation '%s': %s", operation_id, exc
            )
            self._set_report(
                operation_id,
                JMeterExecutionState.FAILED,
                f"Unexpected worker failure: {exc}",
            )
        finally:
            with self._lock:
                if self._current_operation_id == operation_id:
                    self._current_operation_id = None

    def _timeout_for(self, assignment: JMeterAssignmentRequest) -> float:
        """Derive this run's timeout from the declared load profile.

        A load test states its own duration — ramp-up plus hold — so the ceiling
        can be that duration plus room for JMeter's own startup and report
        generation, rather than an arbitrary global limit. Clamped to
        ``max_run_seconds`` so a request can never ask for an unbounded run.
        """
        request = assignment.request
        declared = request.ramp_up_seconds + request.hold_seconds
        # JVM start, plan compile and HTML dashboard generation all sit outside
        # the declared window; 300s of headroom covers them on a loaded host.
        return float(min(declared + 300, self._max_run_seconds))

    @staticmethod
    def _interpret(outcome: JMeterRunOutcome, timeout: float) -> tuple:
        """Map a process outcome onto the reported execution state.

        Local mechanics only — "the process ended this way". What that means for
        the Operation is the Runtime's call.
        """
        if outcome.cancelled:
            return (
                JMeterExecutionState.FAILED,
                "The run was cancelled; partial results were kept.",
            )
        if outcome.timed_out:
            return (
                JMeterExecutionState.FAILED,
                f"The run exceeded its {timeout:.0f}s limit and was terminated; "
                "partial results were kept.",
            )
        if outcome.exit_code != 0:
            return (
                JMeterExecutionState.FAILED,
                f"JMeter exited with code {outcome.exit_code}.",
            )
        return (JMeterExecutionState.SUCCEEDED, "JMeter completed.")

    # ── State bookkeeping ────────────────────────────────────────────────

    def _set_report(
        self,
        operation_id: str,
        state: JMeterExecutionState,
        message: str,
        workspace: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._reports[operation_id] = self._report(
                operation_id, state, message, workspace
            )

    def _report(
        self,
        operation_id: str,
        state: JMeterExecutionState,
        message: str,
        workspace: Optional[str] = None,
    ) -> JMeterExecutionStateReport:
        return JMeterExecutionStateReport(
            operation_id=operation_id,
            worker_id=self._worker_id,
            state=state,
            message=message,
            workspace=workspace,
        )
