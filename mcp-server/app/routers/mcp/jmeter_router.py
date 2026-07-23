"""
JMeter MCP tools — exposed as FastAPI POST endpoints.

Each endpoint becomes an MCP tool via fastapi-mcp; the function docstring is the
tool description shown in an MCP client's catalog, and the request model (with
its field descriptions and example) is the tool's input schema. Endpoints are
thin submit adapters: they validate the request and enqueue a ``QUEUED``
operation, then the generic background dispatcher assigns it to a warm worker
that runs the test. No endpoint runs JMeter inline — the tool returns an
``operation_id`` to poll via ``GET /api/history/get-result``.
"""
from fastapi import APIRouter, HTTPException

from app.integrations.jmeter.jmx_validator import JmxValidationError
from app.schemas.tools.jmeter.run_test import RunJmeterTestRequest
from app.services.tools.jmeter.run_service import JmeterRunService, JmxFileNotFoundError

jmeter_router = APIRouter(prefix="/jmeter", tags=["JMeter"])


@jmeter_router.post(
    "/run_test",
    operation_id="run_jmeter_test",
    summary="Run an existing Apache JMeter .jmx test plan",
)
def run_jmeter_test(request: RunJmeterTestRequest):
    """Run an existing Apache JMeter test plan (`.jmx`) by file path.

    This is the direct analogue of `jmeter -n -t <file>`: pass the path to a
    `.jmx` file you already have (built in Apache JMeter). The server reads and
    validates it, then queues the run and returns an `operation_id` to poll for
    status and the report. Running the same file again simply starts another run.

    Input: `jmx_file` (path) and optional `timeout_seconds`. Returns
    `{operation_id, status, message}`; poll the operation for the report.
    """
    try:
        rs = JmeterRunService().run(request)
        return {"result": rs}
    except JmxFileNotFoundError as e:
        # Missing plan file -> not-found at the HTTP boundary.
        raise HTTPException(status_code=404, detail=str(e)) from e
    except JmxValidationError as e:
        # Plan rejected by validation -> client error at the HTTP boundary.
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error running JMeter test: \n{str(e)}"
        ) from e
