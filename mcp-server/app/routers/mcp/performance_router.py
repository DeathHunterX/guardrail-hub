"""Performance-engine MCP tools — exposed as FastAPI POST endpoints.

Mirrors the ZAP tool router: each endpoint becomes an MCP tool via fastapi-mcp,
with the docstring as the tool description and the request model as the input
schema. The service is assembled by the composition root and injected via
``Depends`` — this router constructs nothing and reads no ``Settings``.

C3.5 exposes only ``generate_performance_plan``: validate an uploaded plan and
store it, returning its reference. It does not enqueue an operation, execute
anything, invoke the dispatcher, or involve any LLM / analysis.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.integrations.jmeter.jmx_validator import JmxValidationError
from app.schemas.performance.execute_tool import ExecutePerformanceTestRequest
from app.schemas.performance.plan_tool import GeneratePerformancePlanRequest
from app.services.performance.execute_tool import PlanAlreadyExecutedError
from app.services.performance.worker_api import PlanNotFoundError

performance_router = APIRouter(prefix="/performance", tags=["Performance"])


def get_performance_plan_service():
    """Provide the composition-root plan service (overridable in tests)."""
    from app.bootstrap import build_performance_plan_service  # noqa: PLC0415

    return build_performance_plan_service()


def get_performance_execute_service():
    """Provide the composition-root execute service (overridable in tests)."""
    from app.bootstrap import build_performance_execute_service  # noqa: PLC0415

    return build_performance_execute_service()


@performance_router.post(
    "/generate_plan",
    operation_id="generate_performance_plan",
    summary="Validate and store a JMeter performance test plan",
)
def generate_performance_plan(
    request: GeneratePerformancePlanRequest,
    service=Depends(get_performance_plan_service),
):
    """Validate a JMeter test plan and store it, returning its plan reference.

    The plan (`.jmx` XML) is checked against the safe-component allow-list —
    scripting and native-execution elements (BeanShell, JSR223, Java Sampler, OS
    Process) are rejected — then the validated bytes are persisted. The returned
    `plan_id` references the stored plan; nothing is executed and no operation is
    queued. An unsafe or malformed plan is rejected with the validator's message
    and nothing is stored.
    """
    try:
        plan_id = service.generate_plan(request.plan, request.timeout_seconds)
        return {
            "result": {
                "plan_id": plan_id,
                "status": "validated",
                "message": (
                    f"Plan validated and stored with plan_id: {plan_id}. "
                    "It was not executed."
                ),
            }
        }
    except JmxValidationError as e:
        # Plan rejected by validation -> client error at the HTTP boundary.
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating performance plan: \n{str(e)}",
        ) from e


@performance_router.post(
    "/execute_test",
    operation_id="execute_performance_test",
    summary="Enqueue a JMeter performance test for a stored plan",
)
def execute_performance_test(
    request: ExecutePerformanceTestRequest,
    service=Depends(get_performance_execute_service),
):
    """Enqueue an execution of a previously generated plan and return its operation id.

    Pass the `plan_id` returned by `generate_performance_plan`. The stored,
    already-validated plan is enqueued as a QUEUED Performance operation; the
    background dispatcher assigns it to a worker, which pulls and runs it. This
    tool does not execute anything itself — poll the returned `operation_id` for
    status and the report. A plan can be executed once (its reference becomes the
    operation id); an unknown plan is a 404 and an already-executed plan a 409.
    """
    try:
        operation_id = service.execute(request.plan_id)
        return {
            "result": {
                "operation_id": operation_id,
                "status": "queued",
                "message": (
                    f"Performance test queued with operation_id: {operation_id}. "
                    "It will start as soon as a worker is available."
                ),
            }
        }
    except PlanNotFoundError as e:
        raise HTTPException(
            status_code=404, detail=f"No stored plan for plan_id: {request.plan_id}"
        ) from e
    except PlanAlreadyExecutedError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error queuing performance test: \n{str(e)}",
        ) from e
