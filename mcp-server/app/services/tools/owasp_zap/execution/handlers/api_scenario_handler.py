"""``scan_api_scenario`` handler — adapts ZapApiScenarioService to the generic
execution contract.

A scenario is a worker-bound, single-session scan (one authenticated workflow
runs on one worker), so its :class:`ExecutionStrategy` is ``SEQUENTIAL`` and the
Dispatcher always passes a bound ``ZapWorkerContext``. The handler does no
scheduling — it delegates to the service, which submits the run to its thread
pool and releases the worker when done (mirroring scan_api).
"""

from app.schemas.tools.owasp_zap.scan_api_scenario import ZapApiScenarioScanRequest
from app.services.operations.operation_service import OperationService
from app.services.tools.owasp_zap.execution.execution_context import ExecutionContext
from app.services.tools.owasp_zap.execution.execution_strategy import ExecutionStrategy
from app.services.tools.owasp_zap.execution.handler import ZapOperation
from app.services.tools.owasp_zap.execution.operation_type import ZapOperationType
from app.services.tools.owasp_zap.execution.zap_worker_context import ZapWorkerContext
from app.services.tools.owasp_zap.scan_api_scenario import ZapApiScenarioService


class ApiScenarioHandler:
    """Adapts ``ZapApiScenarioService`` to the generic ``ZapOperationHandler``."""

    def __init__(self, service: ZapApiScenarioService) -> None:
        self._service = service

    def execute(
        self,
        operation_id: str,
        request: ZapApiScenarioScanRequest,
        context: ExecutionContext,
    ) -> None:
        if not isinstance(context, ZapWorkerContext):  # defensive: worker-bound always has a worker
            raise ValueError("ApiScenarioHandler.execute requires an assigned worker")
        self._service.run_assigned(operation_id, request, context.worker)


def build_api_scenario_operation(operation_service: OperationService) -> ZapOperation:
    """Build the registrable :class:`ZapOperation` for ``scan_api_scenario``."""
    service = ZapApiScenarioService(operation_service=operation_service)
    return ZapOperation(
        operation_type=ZapOperationType.API_SCENARIO,
        execution_strategy=ExecutionStrategy.SEQUENTIAL,
        request_model=ZapApiScenarioScanRequest,
        handler=ApiScenarioHandler(service),
    )
