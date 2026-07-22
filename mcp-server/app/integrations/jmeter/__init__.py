"""JMeter engine adapter — the concrete engine behind the Performance seam.

Everything JMeter-specific lives here (ADR-0010 §4.1): plan validation today,
the ``PerformanceRunner`` implementation (CLI args + subprocess + process
group) as it lands. The engine-neutral capability in ``app/services/performance``
depends on the seam, never on this package.
"""

from app.integrations.jmeter.jmeter_runner import JMeterRunner
from app.integrations.jmeter.jmx_validator import JmxValidationError, validate_jmx

__all__ = [
    "JMeterRunner",
    "JmxValidationError",
    "validate_jmx",
]
