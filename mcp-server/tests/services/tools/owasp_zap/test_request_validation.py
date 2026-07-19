"""Request-time validation: fail fast with actionable messages (no ZAP needed)."""

import unittest

from pydantic import ValidationError

from app.schemas.tools.owasp_zap.api_scan import ZapApiScanRequest
from app.schemas.tools.owasp_zap.scan_api_scenario import (
    ScenarioStep,
    ZapApiScenarioScanRequest,
)
from app.schemas.tools.owasp_zap.scan_api_suite import ZapApiSuiteScanRequest


def _step(name, url="https://api.example.com/x", method="GET", **kw):
    return {"name": name, "target_url": url, "method": method, **kw}


class UrlValidationTests(unittest.TestCase):
    def test_absolute_url_accepted(self):
        ZapApiScanRequest.model_validate(
            {"report_group": "p", "target_url": "https://api.example.com/x", "method": "GET"}
        )

    def test_missing_scheme_rejected_with_message(self):
        with self.assertRaises(ValidationError) as ctx:
            ZapApiScanRequest.model_validate(
                {"report_group": "p", "target_url": "api.example.com/x", "method": "GET"}
            )
        self.assertIn("absolute", str(ctx.exception).lower())

    def test_templated_scenario_url_is_allowed(self):
        # ${var} placeholders are resolved at replay time, not rejected up-front.
        ScenarioStep(**_step("s", url="https://api.example.com/users/${uid}"))


class AuthValidationTests(unittest.TestCase):
    def test_token_prefix_without_token_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            ZapApiScanRequest.model_validate(
                {"report_group": "p", "target_url": "https://api/x", "method": "GET",
                 "token_prefix": "Bearer"}
            )
        self.assertIn("token_prefix", str(ctx.exception))


class ScenarioValidationTests(unittest.TestCase):
    def test_duplicate_step_names_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            ZapApiScenarioScanRequest(report_group="p", steps=[_step("a"), _step("a")])
        self.assertIn("unique", str(ctx.exception).lower())

    def test_unknown_dependency_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            ZapApiScenarioScanRequest(
                report_group="p", steps=[_step("a", depends_on=["missing"])]
            )
        self.assertIn("unknown step 'missing'", str(ctx.exception))

    def test_circular_dependency_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            ZapApiScenarioScanRequest(
                report_group="p",
                steps=[_step("a", depends_on=["b"]), _step("b", depends_on=["a"])],
            )
        self.assertIn("Circular", str(ctx.exception))

    def test_duplicate_capture_variables_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            ZapApiScenarioScanRequest(
                report_group="p",
                steps=[
                    _step("a", extract={"tok": "data.t"}),
                    _step("b", extract={"tok": "data.t"}),
                ],
            )
        self.assertIn("captured by more than one step", str(ctx.exception))


class SuiteValidationTests(unittest.TestCase):
    def test_valid_suite_accepted(self):
        ZapApiSuiteScanRequest(
            report_group="p", application_name="App",
            categories=[{"name": "Auth", "openapi_spec": {"paths": {"/login": {"post": {}}}}}],
        )

    def test_duplicate_category_names_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            ZapApiSuiteScanRequest(
                report_group="p", application_name="App",
                categories=[
                    {"name": "Auth", "openapi_spec": {"paths": {"/a": {"get": {}}}}},
                    {"name": "Auth", "openapi_spec": {"paths": {"/b": {"get": {}}}}},
                ],
            )
        self.assertIn("Duplicate category", str(ctx.exception))

    def test_empty_paths_rejected_with_actionable_message(self):
        with self.assertRaises(ValidationError) as ctx:
            ZapApiSuiteScanRequest(
                report_group="p", application_name="App",
                categories=[{"name": "Empty", "openapi_spec": {"paths": {}}}],
            )
        self.assertIn("zero endpoints", str(ctx.exception))

    def test_malformed_spec_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            ZapApiSuiteScanRequest(
                report_group="p", application_name="App",
                categories=[{"name": "Bad", "openapi_spec": ":not-yaml: [", "base_url": "https://h"}],
            )
        self.assertIn("Bad", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


class SuiteNameAliasTests(unittest.TestCase):
    """suite_name is canonical; application_name remains an accepted alias."""

    def _cat(self):
        return {"name": "Auth", "openapi_spec": {"paths": {"/login": {"post": {}}}}}

    def test_canonical_suite_name(self):
        r = ZapApiSuiteScanRequest.model_validate(
            {"report_group": "p", "suite_name": "My Scan", "categories": [self._cat()]}
        )
        self.assertEqual(r.suite_name, "My Scan")

    def test_legacy_application_name_alias_accepted(self):
        r = ZapApiSuiteScanRequest.model_validate(
            {"report_group": "p", "application_name": "My Scan", "categories": [self._cat()]}
        )
        self.assertEqual(r.suite_name, "My Scan")

    def test_serialization_emits_suite_name(self):
        r = ZapApiSuiteScanRequest.model_validate(
            {"report_group": "p", "application_name": "My Scan", "categories": [self._cat()]}
        )
        dumped = r.model_dump(mode="json", by_alias=True)
        self.assertIn("suite_name", dumped)
        self.assertNotIn("application_name", dumped)
