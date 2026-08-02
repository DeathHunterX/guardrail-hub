"""JMX generation and validation.

Validation is the Guardrail G4 enforcement point, so most of these are refusal
tests: the interesting behaviour is what does *not* get to run.
"""

import unittest
from xml.etree import ElementTree

from app.schemas.tools.jmeter.run_jmeter_test import JMeterTestRequest
from app.services.tools.jmeter.plan import (
    JMeterPlanGenerator,
    JMeterPlanValidationError,
    JMeterPlanValidator,
)


def _request(**overrides) -> JMeterTestRequest:
    fields = {
        "target_url": "https://api.example.com/v1/orders",
        "thread_count": 50,
        "ramp_up_seconds": 30,
        "hold_seconds": 300,
    }
    fields.update(overrides)
    return JMeterTestRequest(**fields)


_FOREIGN_PLAN = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2">
  <hashTree>
    <HTTPSamplerProxy testname="evil">
      <stringProp name="HTTPSampler.domain">victim.example.net</stringProp>
    </HTTPSamplerProxy>
  </hashTree>
</jmeterTestPlan>
"""

_SCRIPTED_PLAN = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2">
  <hashTree>
    <HTTPSamplerProxy testname="ok">
      <stringProp name="HTTPSampler.domain">api.example.com</stringProp>
    </HTTPSamplerProxy>
    <JSR223Sampler testname="pwn">
      <stringProp name="script">Runtime.getRuntime().exec("id")</stringProp>
    </JSR223Sampler>
  </hashTree>
</jmeterTestPlan>
"""


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.generator = JMeterPlanGenerator()

    def test_generated_plan_is_well_formed_xml(self):
        root = ElementTree.fromstring(self.generator.generate("op-1", _request()))
        self.assertEqual("jmeterTestPlan", root.tag)

    def test_generated_plan_targets_exactly_the_requested_host(self):
        plan = self.generator.generate("op-1", _request())
        root = ElementTree.fromstring(plan)
        domains = [
            e.text
            for e in root.iter("stringProp")
            if e.get("name") == "HTTPSampler.domain"
        ]
        self.assertEqual(["api.example.com"], domains)

    def test_load_profile_reaches_the_thread_group(self):
        plan = self.generator.generate("op-1", _request(thread_count=7, ramp_up_seconds=3))
        root = ElementTree.fromstring(plan)
        props = {
            e.get("name"): e.text
            for e in root.iter("stringProp")
            if (e.get("name") or "").startswith("ThreadGroup.")
        }
        self.assertEqual("7", props["ThreadGroup.num_threads"])
        self.assertEqual("3", props["ThreadGroup.ramp_time"])
        # Duration is ramp-up plus hold: threads must still be running for the
        # whole hold window after the last one starts.
        self.assertEqual("303", props["ThreadGroup.duration"])

    def test_generated_plan_contains_no_scripting_elements(self):
        # The generated path's safety property: it cannot execute code, so it
        # does not depend on the validator's denylist.
        plan = self.generator.generate("op-1", _request())
        for forbidden in ("JSR223", "BeanShell", "OSProcess", "BSF"):
            self.assertNotIn(forbidden, plan)

    def test_generated_plan_passes_its_own_validation(self):
        request = _request()
        plan = self.generator.generate("op-1", request)
        JMeterPlanValidator().validate(plan, request)  # must not raise

    def test_special_characters_in_the_target_are_escaped(self):
        request = _request(target_url="https://api.example.com/search?q=a&b=c")
        plan = JMeterPlanGenerator().generate("op-1", request)
        self.assertNotIn("q=a&b=c", plan)
        self.assertIn("&amp;", plan)
        ElementTree.fromstring(plan)  # still parses


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.validator = JMeterPlanValidator()

    def test_empty_plan_is_rejected(self):
        with self.assertRaises(JMeterPlanValidationError):
            self.validator.validate("   ", _request())

    def test_malformed_xml_is_rejected(self):
        with self.assertRaises(JMeterPlanValidationError):
            self.validator.validate("<jmeterTestPlan><oops>", _request())

    def test_wrong_root_element_is_rejected(self):
        with self.assertRaises(JMeterPlanValidationError):
            self.validator.validate("<notAPlan/>", _request())

    def test_plan_without_a_sampler_is_rejected(self):
        with self.assertRaises(JMeterPlanValidationError):
            self.validator.validate(
                "<jmeterTestPlan><hashTree/></jmeterTestPlan>", _request()
            )

    def test_foreign_host_is_rejected(self):
        with self.assertRaises(JMeterPlanValidationError) as caught:
            self.validator.validate(_FOREIGN_PLAN, _request())
        self.assertIn("victim.example.net", str(caught.exception))

    def test_code_execution_elements_are_rejected(self):
        with self.assertRaises(JMeterPlanValidationError) as caught:
            self.validator.validate(_SCRIPTED_PLAN, _request())
        self.assertIn("JSR223Sampler", str(caught.exception))

    def test_sampler_without_an_explicit_domain_is_rejected(self):
        # An empty domain inherits from HTTP Request Defaults, which makes the
        # effective target unknowable from the sampler alone.
        plan = """<jmeterTestPlan><hashTree><HTTPSamplerProxy>
        <stringProp name="HTTPSampler.domain"></stringProp>
        </HTTPSamplerProxy></hashTree></jmeterTestPlan>"""
        with self.assertRaises(JMeterPlanValidationError):
            self.validator.validate(plan, _request())

    def test_host_comparison_ignores_case_and_port(self):
        plan = """<jmeterTestPlan><hashTree><HTTPSamplerProxy>
        <stringProp name="HTTPSampler.domain">API.Example.com</stringProp>
        </HTTPSamplerProxy></hashTree></jmeterTestPlan>"""
        self.validator.validate(plan, _request(target_url="https://api.example.com:8443/x"))


if __name__ == "__main__":
    unittest.main()
