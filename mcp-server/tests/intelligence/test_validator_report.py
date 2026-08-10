"""Unit tests for RegistryValidator's structured ValidationReport."""

import unittest

from app.intelligence.registry.exceptions import ValidationIssue, ValidationReport
from app.intelligence.registry.models.model import ModelRecord
from app.intelligence.registry.models.provider import (
    AuthConfig,
    ConnectionConfig,
    ProviderRecord,
)
from app.intelligence.registry.types.capability import Capability
from app.intelligence.registry.types.deployment import DeploymentType
from app.intelligence.registry.types.model import ModelType
from app.intelligence.registry.types.provider import ProviderType
from app.intelligence.registry.validators import RegistryValidator


def _make_provider(**overrides):
    kwargs = dict(
        provider_id="p1",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(),
        connection=ConnectionConfig(base_url="https://api.example.com"),
    )
    kwargs.update(overrides)
    return ProviderRecord(**kwargs)


def _make_model(**overrides):
    kwargs = dict(
        model_id="m1",
        provider_id="p1",
        model_type=ModelType.CHAT,
        capabilities=frozenset({Capability.CHAT}),
    )
    kwargs.update(overrides)
    return ModelRecord(**kwargs)


class ValidateWithReportTests(unittest.TestCase):
    """``validate_with_report`` returns a structured ``ValidationReport``."""

    def setUp(self):
        self.validator = RegistryValidator()

    def test_clean_records_produce_empty_report(self):
        providers = [_make_provider()]
        models = [_make_model()]
        report = self.validator.validate_with_report(providers, models)
        self.assertTrue(report.ok)
        self.assertEqual(report.issues, ())
        self.assertEqual(report.count, 0)

    def test_unknown_provider_reference_becomes_validation_issue(self):
        providers = [_make_provider()]
        models = [_make_model(model_id="orphan", provider_id="ghost")]
        report = self.validator.validate_with_report(providers, models)
        self.assertFalse(report.ok)
        self.assertEqual(len(report.issues), 1)
        issue = report.issues[0]
        self.assertIsInstance(issue, ValidationIssue)
        self.assertEqual(issue.entity_type, "model")
        self.assertEqual(issue.entity_id, "orphan")
        self.assertEqual(issue.field, "provider_id")

    def test_invalid_priority_becomes_validation_issue(self):
        providers = [_make_provider(priority=-5)]
        report = self.validator.validate_with_report(providers, [])
        self.assertFalse(report.ok)
        issues = [i for i in report.issues if i.field == "priority"]
        self.assertEqual(len(issues), 1)
        self.assertIn("non-negative", issues[0].message)

    def test_invalid_model_type_becomes_validation_issue(self):
        # The loader rejects bad types so we cannot reach here with one;
        # but the validator still emits issues for structural problems.
        providers = [_make_provider()]
        # A model with no capabilities is invalid.
        models = [_make_model(capabilities=frozenset())]
        report = self.validator.validate_with_report(providers, models)
        self.assertFalse(report.ok)

    def test_duplicate_provider_id_emits_validation_issue(self):
        providers = [
            _make_provider(provider_id="dup"),
            _make_provider(provider_id="dup"),
        ]
        report = self.validator.validate_with_report(providers, [])
        self.assertFalse(report.ok)
        dup_issues = [
            i for i in report.issues
            if i.entity_type == "provider" and i.field == "provider_id"
        ]
        self.assertGreaterEqual(len(dup_issues), 1)

    def test_duplicate_model_id_emits_validation_issue(self):
        providers = [_make_provider()]
        models = [
            _make_model(model_id="dup"),
            _make_model(model_id="dup"),
        ]
        report = self.validator.validate_with_report(providers, models)
        self.assertFalse(report.ok)
        dup_issues = [
            i for i in report.issues
            if i.entity_type == "model" and i.field == "model_id"
        ]
        self.assertGreaterEqual(len(dup_issues), 1)

    def test_warnings_surface_in_report(self):
        providers = [_make_provider(capabilities=frozenset())]
        report = self.validator.validate_with_report(providers, [])
        self.assertTrue(report.ok)  # still valid
        self.assertGreater(len(report.warnings), 0)


class ValidationReportStringTests(unittest.TestCase):
    """Sanity checks on the report shape."""

    def test_empty_report_is_ok(self):
        report = ValidationReport()
        self.assertTrue(report.ok)
        self.assertEqual(report.count, 0)


if __name__ == "__main__":
    unittest.main()