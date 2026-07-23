"""Input schema for the ``execute_performance_test`` MCP tool (ADR-0010 §4.12 / C3.6).

The tool takes the reference returned by ``generate_performance_plan`` and enqueues
a Performance operation for that stored, already-validated plan. It carries no
plan content and no execution knobs — the plan (and its timeout) were fixed at
generation time.
"""

from pydantic import BaseModel, Field


class ExecutePerformanceTestRequest(BaseModel):
    """A request to enqueue an execution of a previously generated plan."""

    plan_id: str = Field(
        ...,
        description=(
            "The plan reference returned by generate_performance_plan. The stored "
            "plan is enqueued for execution; the plan itself is not re-sent."
        ),
        examples=["1e75a7c1-b5ed-4d8a-b9dc-63ee06247215"],
    )
