"""Unit tests for JMX whitelist validation (ADR-0010 §5 S1 / INV3)."""

import unittest
from pathlib import Path

from app.integrations.jmeter.jmx_validator import JmxValidationError, validate_jmx

# The repo's own safe smoke-test plan (checked in under docker/jmeter/test-plans)
# must validate cleanly — it is the reference "known-good" plan.
_SMOKE_PLAN = (
    Path(__file__).resolve().parents[3]
    / "docker"
    / "jmeter"
    / "test-plans"
    / "smoke-test.jmx"
)


def _plan(*components: str) -> str:
    """Wrap component XML fragments in a minimal valid jmeterTestPlan."""
    body = "\n".join(components)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<jmeterTestPlan version="1.2"><hashTree>'
        f"{body}"
        "</hashTree></jmeterTestPlan>"
    )


class JmxValidatorAcceptsSafePlans(unittest.TestCase):
    def test_repo_smoke_plan_is_valid(self):
        validate_jmx(_SMOKE_PLAN.read_text(encoding="utf-8"))  # must not raise

    def test_safe_http_components_pass(self):
        validate_jmx(
            _plan(
                '<ThreadGroup testclass="ThreadGroup"/>',
                '<HTTPSamplerProxy testclass="HTTPSamplerProxy"/>',
                '<HeaderManager testclass="HeaderManager"/>',
                '<ResponseAssertion testclass="ResponseAssertion"/>',
                '<ConstantTimer testclass="ConstantTimer"/>',
            )
        )

    def test_accepts_bytes_input(self):
        validate_jmx(_SMOKE_PLAN.read_bytes())


class JmxValidatorRejectsScripting(unittest.TestCase):
    def _assert_scripting_rejected(self, component_xml: str):
        with self.assertRaises(JmxValidationError) as ctx:
            validate_jmx(_plan(component_xml))
        self.assertIn("scripting", str(ctx.exception).lower())

    def test_rejects_beanshell_sampler(self):
        self._assert_scripting_rejected('<BeanShellSampler testclass="BeanShellSampler"/>')

    def test_rejects_jsr223_postprocessor(self):
        self._assert_scripting_rejected('<JSR223PostProcessor testclass="JSR223PostProcessor"/>')

    def test_rejects_java_sampler(self):
        self._assert_scripting_rejected('<JavaSampler testclass="JavaSampler"/>')

    def test_rejects_os_process_sampler(self):
        # OS Process Sampler serializes as SystemSampler
        self._assert_scripting_rejected('<SystemSampler testclass="SystemSampler"/>')

    def test_rejects_beanshell_even_nested_in_safe_thread_group(self):
        with self.assertRaises(JmxValidationError):
            validate_jmx(
                _plan(
                    '<ThreadGroup testclass="ThreadGroup"/>',
                    '<hashTree><BeanShellPreProcessor testclass="BeanShellPreProcessor"/></hashTree>',
                )
            )


class JmxValidatorRejectsUnknownAndMalformed(unittest.TestCase):
    def test_unknown_component_rejected_by_default(self):
        with self.assertRaises(JmxValidationError) as ctx:
            validate_jmx(_plan('<TotallyMadeUpSampler testclass="TotallyMadeUpSampler"/>'))
        self.assertIn("allow-list", str(ctx.exception).lower())

    def test_non_jmeter_root_rejected(self):
        with self.assertRaises(JmxValidationError):
            validate_jmx("<notAPlan><child/></notAPlan>")

    def test_malformed_xml_rejected(self):
        with self.assertRaises(JmxValidationError):
            validate_jmx("<jmeterTestPlan><hashTree>")

    def test_entity_expansion_bomb_rejected_at_parse(self):
        # A billion-laughs style document must be refused by the hardened parser,
        # not expanded — JMX is untrusted input.
        bomb = (
            '<?xml version="1.0"?>'
            "<!DOCTYPE lolz [<!ENTITY lol \"lol\">"
            '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">]>'
            "<jmeterTestPlan><hashTree>&lol2;</hashTree></jmeterTestPlan>"
        )
        with self.assertRaises(JmxValidationError):
            validate_jmx(bomb)


if __name__ == "__main__":
    unittest.main()
