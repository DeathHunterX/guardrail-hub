"""JMeter MCP tools — exposed as FastAPI POST endpoints.

JMeter-first public API: one tool runs an existing ``.jmx`` test plan by path,
mirroring how a tester uses Apache JMeter (`jmeter -n -t <file>`). The service is
assembled by the composition root and injected via ``Depends`` — this router
constructs nothing and reads no ``Settings``. Internal engine concepts (stored
plans, the queue, operation metadata, internal ids) stay internal.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.integrations.jmeter.jmx_validator import JmxValidationError
from app.schemas.jmeter.run_test import RunJmeterTestRequest
from app.services.jmeter.run_service import JmxFileNotFoundError

jmeter_router = APIRouter(prefix="/jmeter", tags=["JMeter"])


def get_jmeter_test_service():
    """Provide the composition-root JMeter test service (overridable in tests)."""
    from app.bootstrap import build_jmeter_test_service  # noqa: PLC0415

    return build_jmeter_test_service()


@jmeter_router.post(
    "/run_test",
    operation_id="run_jmeter_test",
    summary="Run an existing Apache JMeter .jmx test plan",
)
def run_jmeter_test(
    request: RunJmeterTestRequest,
    service=Depends(get_jmeter_test_service),
):
    """Run an existing Apache JMeter test plan (`.jmx`) by file path.

    This is the direct analogue of `jmeter -n -t <file>`: pass the path to a
    `.jmx` file you already have (built in Apache JMeter). The server reads and
    validates it, then queues the run and returns an `operation_id` to poll for
    status and the report (via `get-result`). Running the same file again simply
    starts another run. A missing file is a 404; a plan that fails validation is
    a 400.
    """
    try:
        operation_id = service.run(request.jmx_file, request.timeout_seconds)
        return {
            "result": {
                "operation_id": operation_id,
                "status": "queued",
                "message": (
                    f"JMeter test queued with operation_id: {operation_id}. "
                    "It will start as soon as a worker is available."
                ),
            }
        }
    except JmxFileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except JmxValidationError as e:
        # Plan rejected by validation -> client error at the HTTP boundary.
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error running JMeter test: \n{str(e)}",
        ) from e
