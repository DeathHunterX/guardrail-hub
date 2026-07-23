from typing import Optional

from pydantic import BaseModel, Field


class RunJmeterTestRequest(BaseModel):
    """A request to run an existing Apache JMeter test plan by file path."""

    jmx_file: str = Field(
        ...,
        description=(
            "Path to an existing Apache JMeter .jmx test plan, as you would pass "
            "to `jmeter -n -t <file>`. The server reads and validates the file, "
            "then runs it. The path must be readable by the server."
        ),
        examples=["/jmeter/test-plans/checkout-load.jmx"],
    )

    timeout_seconds: Optional[float] = Field(
        None,
        description=(
            "Optional hard time limit for the run; the worker terminates the test "
            "if it exceeds this. Omit for no explicit limit."
        ),
        examples=[600.0],
    )
