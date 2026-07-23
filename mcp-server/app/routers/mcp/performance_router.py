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
from app.schemas.performance.plan_tool import GeneratePerformancePlanRequest

performance_router = APIRouter(prefix="/performance", tags=["Performance"])


def get_performance_plan_service():
    """Provide the composition-root plan service (overridable in tests)."""
    from app.bootstrap import build_performance_plan_service  # noqa: PLC0415

    return build_performance_plan_service()


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
