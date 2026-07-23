"""Adapts the JMX whitelist validator to the neutral ``PlanValidator`` port.

The Runtime depends on ``PlanValidator`` (a protocol), never on the JMeter
validator directly. This thin adapter is what lets the concrete JMX validation
satisfy that port, keeping the engine specifics on this side of the seam.
"""

from __future__ import annotations

from app.integrations.jmeter.jmx_validator import validate_jmx


class JmxPlanValidator:
    """``PlanValidator`` implementation backed by JMX whitelist validation."""

    def validate(self, plan: bytes | str) -> None:
        validate_jmx(plan)
