"""JMeterRuntime — the per-operation orchestrator.

**Naming.** Two things in this repository are called "runtime", distinguished by
layer, and this is the application-logic one:

* ``services/tools/<tool>/execution/runtime.py`` — per-operation orchestration
  (this file).
* ``integrations/<tool>/runtime.py`` — process-wide singletons (registry,
  scheduler, pool manager), as ``integrations/owasp_zap/runtime.py`` is.

**What Runtime owns:** the ordered pipeline below, and *all* lifecycle
persistence for its operation. It is the sole caller of ``OperationService`` for
JMeter operations — with one deliberate exception, the Dispatcher's own
``fail()`` for an operation it could never hand off.

**What Runtime does not own:** spawning or signalling an OS process (Worker),
turning a JTL into numbers (Parser), deciding whether those numbers are good
(Analyzer), or choosing which worker runs the job (Dispatcher).

The pipeline::

    Generate (optional) -> Validate -> Execute -> Parse -> Persist

Generation is skipped when the caller supplied their own plan. **Validation is
not skippable either way** — a supplied plan is checked by the same validator as
a generated one, because validation is where target authorization (Guardrail G4)
is enforced and a caller-supplied plan is exactly the case that needs it most.

Parse is a no-op today: the parser lands in Phase 4. Persist therefore records
what execution actually knows — where the artifacts are, which worker ran it,
when, under what load profile — and leaves ``summary``/``metrics`` unset rather
than fabricating sample counts nobody measured.
"""

import time
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.core.mcp_logger import MCPLogger
from app.integrations.jmeter.process import JMeterProcessRunner
from app.integrations.jmeter.worker_client import JMeterWorkerCommunicationError
from app.schemas.tools.jmeter.jmeter_test_result import (
    JMeterArtifacts,
    JMeterExecutionMetadata,
    JMeterTestResult,
)
from app.schemas.tools.jmeter.run_jmeter_test import JMeterTestRequest
from app.schemas.tools.jmeter.worker import JMeterWorkerInfo
from app.schemas.tools.jmeter.worker_assignment import (
    JMeterAssignmentRequest,
    JMeterExecutionState,
)
from app.services.operations.operation_service import OperationService
from app.services.tools.jmeter.plan import (
    JMeterPlanGenerator,
    JMeterPlanValidationError,
    JMeterPlanValidator,
)


class JMeterRuntime:
    """Runs one JMeter operation end to end."""

    def __init__(
        self,
        operation_service: OperationService,
        pool_manager=None,
        generator: Optional[JMeterPlanGenerator] = None,
        validator: Optional[JMeterPlanValidator] = None,
        config=None,
        logger: Optional[MCPLogger] = None,
    ) -> None:
        """
        Args:
            operation_service: Lifecycle transitions and result persistence.
            pool_manager: Supplies the client for the assigned worker and takes
                the worker back when the run ends. Defaults to the process-wide
                JMeter pool.
            generator: JMX builder; injectable for tests.
            validator: Plan validator; injectable for tests.
            config: Settings object; defaults to ``app.core.config.settings``.
            logger: Optional logger; one is created if omitted.
        """
        if config is None:
            from app.core.config import settings as config  # noqa: PLC0415
        if pool_manager is None:
            from app.integrations.jmeter.runtime import (  # noqa: PLC0415
                pool_manager as default_pool_manager,
            )

            pool_manager = default_pool_manager

        self._operation_service = operation_service
        self._pool_manager = pool_manager
        self._generator = generator or JMeterPlanGenerator()
        self._validator = validator or JMeterPlanValidator()
        self._config = config
        self._logger = logger or MCPLogger("JMeterRuntime")

    # ── Entry point ──────────────────────────────────────────────────────

    def run(
        self,
        operation_id: str,
        request: JMeterTestRequest,
        worker: JMeterWorkerInfo,
    ) -> None:
        """Execute *operation_id* on the already-assigned *worker*.

        Called by the Dispatcher only after the pool assigned *worker* — this
        method does no scheduling of its own. It never raises: every outcome is
        recorded as a lifecycle transition, and the worker is released on every
        path, including the ones nobody planned for.
        """
        started_at = datetime.now(timezone.utc)
        try:
            self._operation_service.start(operation_id)

            jmx_plan = self._generate_plan(operation_id, request)
            self._validate_plan(jmx_plan, request)

            workspace = self._execute_on_worker(operation_id, request, jmx_plan, worker)
            summary, metrics = self._parse_results(workspace)

            self._persist_result(
                operation_id=operation_id,
                request=request,
                worker=worker,
                workspace=workspace,
                started_at=started_at,
                summary=summary,
                metrics=metrics,
            )
        except JMeterPlanValidationError as exc:
            # Refusing to run is the correct outcome, not an internal error.
            self._logger.warning(
                "Operation '%s' rejected by plan validation: %s", operation_id, exc
            )
            self._operation_service.fail(operation_id, str(exc))
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.error("Operation '%s' failed: %s", operation_id, exc)
            self._operation_service.fail(operation_id, str(exc))
        finally:
            self._pool_manager.release_worker(worker.worker_id, operation_id)

    # ── Pipeline phases ──────────────────────────────────────────────────

    def _generate_plan(self, operation_id: str, request: JMeterTestRequest) -> str:
        """Phase 1 — build a JMX plan, unless the caller supplied one.

        A supplied plan is passed straight through to validation. It is *not*
        merged with the generated one and the load-profile fields are not
        applied to it: silently editing someone's test plan would make the thing
        that runs differ from the thing they wrote and reviewed.

        Raises:
            JMeterPlanValidationError: A plan was supplied but the server does
                not accept supplied plans.
        """
        if request.jmx_plan is None:
            return self._generator.generate(operation_id, request)

        if not self._config.jmeter_allow_supplied_plan:
            raise JMeterPlanValidationError(
                "This server does not accept caller-supplied JMeter test plans. "
                "Omit jmx_plan and the plan will be generated from the load "
                "profile instead."
            )

        self._logger.info(
            "Operation '%s' supplied its own test plan — generation skipped",
            operation_id,
        )
        return request.jmx_plan

    def _validate_plan(self, jmx_plan: str, request: JMeterTestRequest) -> None:
        """Phase 2 — the single G4 enforcement point, before anything executes.

        Runs for generated and supplied plans alike, and before a worker is
        engaged, so an unauthorized target never generates traffic.
        """
        self._validator.validate(jmx_plan, request)

    def _execute_on_worker(
        self,
        operation_id: str,
        request: JMeterTestRequest,
        jmx_plan: str,
        worker: JMeterWorkerInfo,
    ) -> str:
        """Phase 3 — hand the plan to *worker*, wait, return its workspace.

        Owns none of the subprocess mechanics; that is the Worker's. What it
        owns is the waiting: polling the worker's reported state and translating
        it into operation progress until the run reaches a terminal state.

        Raises:
            RuntimeError: The worker declined, lost the run, or reported failure.
        """
        client = self._pool_manager.get_client(worker)
        ack = client.send_assignment(
            JMeterAssignmentRequest(
                operation_id=operation_id, request=request, jmx_plan=jmx_plan
            )
        )
        if not ack.accepted:
            raise RuntimeError(
                f"Worker '{worker.worker_id}' declined the assignment: "
                f"{ack.message or 'no reason given'}"
            )

        self._operation_service.report_progress(
            operation_id,
            stage="running",
            progress=10,
            worker_id=worker.worker_id,
        )
        return self._await_completion(operation_id, request, worker, client)

    def _await_completion(self, operation_id, request, worker, client) -> str:
        """Poll the worker until its run reaches a terminal state."""
        poll_interval = self._config.jmeter_execution_poll_interval_seconds
        # The worker enforces the real timeout; this is the Runtime's own
        # backstop for a worker that accepts a run and then goes quiet without
        # its heartbeat expiring. Generous on purpose — it must never fire
        # before the worker's own limit.
        deadline = time.monotonic() + min(
            request.ramp_up_seconds + request.hold_seconds + 900,
            self._config.jmeter_max_run_seconds + 900,
        )

        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            try:
                report = client.fetch_execution_state(operation_id)
            except JMeterWorkerCommunicationError as exc:
                # A blip while a load test runs is expected — the worker is
                # saturated by design. Keep polling; the heartbeat sweep is what
                # decides a worker is actually gone.
                self._logger.debug(
                    "Could not read state for '%s' (retrying): %s", operation_id, exc
                )
                continue

            if report.state == JMeterExecutionState.SUCCEEDED:
                if not report.workspace:
                    raise RuntimeError(
                        "The worker reported success but named no workspace, so "
                        "the run produced nothing that can be read back."
                    )
                return report.workspace
            if report.state == JMeterExecutionState.FAILED:
                raise RuntimeError(report.message or "The JMeter run failed.")
            if report.state == JMeterExecutionState.UNKNOWN:
                raise RuntimeError(
                    f"Worker '{worker.worker_id}' has no record of this run — it "
                    "most likely restarted mid-execution."
                )

        raise RuntimeError(
            f"Worker '{worker.worker_id}' did not report a terminal state before "
            "the runtime deadline."
        )

    @staticmethod
    def _parse_results(workspace: str) -> Tuple[None, None]:
        """Phase 4 — turn the JTL into numbers.

        Not implemented: the parser is the next milestone. Returning ``None`` for
        both sections is deliberate and honest — the result contract makes them
        optional precisely so this phase can persist what it knows without
        inventing sample counts it never measured.
        """
        return None, None

    def _persist_result(
        self,
        *,
        operation_id: str,
        request: JMeterTestRequest,
        worker: JMeterWorkerInfo,
        workspace: str,
        started_at: datetime,
        summary,
        metrics,
    ) -> None:
        """Phase 5 — assemble the result contract and complete the operation.

        No ``findings=`` is passed to ``complete()``: a load test has no
        severity breakdown (ADR-0010), and the notification layer already
        handles its absence.
        """
        result = JMeterTestResult(
            operation_id=operation_id,
            summary=summary,
            metrics=metrics,
            artifacts=self._artifacts_for(workspace),
            metadata=JMeterExecutionMetadata(
                worker_id=worker.worker_id,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                thread_count=request.thread_count,
                ramp_up_seconds=request.ramp_up_seconds,
                hold_seconds=request.hold_seconds,
            ),
        )
        self._operation_service.complete(
            operation_id, result=result.model_dump(mode="json", by_alias=True)
        )
        self._logger.info("Operation '%s' completed", operation_id)

    # ── Artifacts ────────────────────────────────────────────────────────

    @staticmethod
    def _artifacts_for(workspace: str) -> JMeterArtifacts:
        """Map a run workspace onto the public URLs its files are served at.

        The worker writes into the same ``./public/report/jmeter/detail-report``
        tree the server serves from, so there is no upload step — see
        docker-compose.yml.

        ponytail: shared-volume artifact handoff, which ties worker and server
        to one filesystem. If workers ever run off-host, replace this with an
        artifact upload from the worker; the result contract does not change.
        """
        base = "/public" + workspace.split("/public", 1)[-1] if "/public" in workspace else None
        if base is None:
            # Workspace outside the served tree (a test, or a misconfigured
            # deployment): record no links rather than fabricate broken ones.
            return JMeterArtifacts()
        return JMeterArtifacts(
            view_report=f"{base}/{JMeterProcessRunner.REPORT_DIR}/index.html",
            results_data=f"{base}/{JMeterProcessRunner.RESULTS_FILE}",
            test_plan=f"{base}/{JMeterProcessRunner.PLAN_FILE}",
            engine_log=f"{base}/{JMeterProcessRunner.ENGINE_LOG}",
        )
