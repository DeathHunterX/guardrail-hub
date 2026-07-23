"""Input schema for the ``generate_performance_plan`` MCP tool (ADR-0010 §5 / C3.5).

The plan arrives as JMeter ``.jmx`` XML text — a program JMeter would execute,
so it is treated as untrusted and validated before it is ever stored (INV3).
This model is the tool's input schema (fastapi-mcp derives it from the request
type); it carries no engine-execution or analysis concern.
"""

from typing import Optional

from pydantic import BaseModel, Field


class GeneratePerformancePlanRequest(BaseModel):
    """A JMeter test plan submitted for whitelist validation and storage."""

    plan: str = Field(
        ...,
        description=(
            "The JMeter test plan as .jmx XML text. It is validated against the "
            "safe-component allow-list (scripting / native-execution elements are "
            "rejected) before being stored. It is not executed."
        ),
        examples=['<jmeterTestPlan version="1.2">...</jmeterTestPlan>'],
    )

    timeout_seconds: Optional[float] = Field(
        None,
        description=(
            "Optional execution bound stored alongside the plan for a later run. "
            "Storing it here does not start anything."
        ),
        examples=[300.0],
    )
