"""The JMeter PlanValidator adapter delegates to JMX whitelist validation."""

import unittest

from app.integrations.jmeter.jmx_validator import JmxValidationError
from app.integrations.jmeter.plan_validator import JmxPlanValidator


class JmxPlanValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = JmxPlanValidator()

    def test_accepts_a_safe_plan(self):
        self.validator.validate(
            '<jmeterTestPlan><hashTree>'
            '<ThreadGroup testclass="ThreadGroup"/>'
            "</hashTree></jmeterTestPlan>"
        )  # must not raise

    def test_rejects_a_scripting_plan(self):
        with self.assertRaises(JmxValidationError):
            self.validator.validate(
                '<jmeterTestPlan><hashTree>'
                '<JSR223Sampler testclass="JSR223Sampler"/>'
                "</hashTree></jmeterTestPlan>"
            )


if __name__ == "__main__":
    unittest.main()
