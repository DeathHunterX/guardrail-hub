"""Unit tests for registry exception classes and structured reports."""

import unittest

from app.intelligence.exceptions.llm import LLMConfigurationError
from app.intelligence.registry.exceptions import (
    LoadIssue,
    LoadReport,
    RegistryLoadError,
    RegistryValidationError,
    ValidationIssue,
    ValidationReport,
)


class LoadReportTests(unittest.TestCase):
    """Tests for the structured LoadReport."""

    def test_empty_report_is_ok(self):
        report = LoadReport()
        self.assertTrue(report.ok)
        self.assertEqual(report.count, 0)

    def test_non_empty_report_is_not_ok(self):
        report = LoadReport(
            issues=(
                LoadIssue(
                    file_path="providers.yaml",
                    position="providers[0].connection.base_url",
                    message="required field missing",
                ),
            )
        )
        self.assertFalse(report.ok)
        self.assertEqual(report.count, 1)
        # __str__ includes a useful diagnostic.
        rendered = str(report)
        self.assertIn("providers.yaml", rendered)
        self.assertIn("providers[0].connection.base_url", rendered)
        self.assertIn("required field missing", rendered)


class ValidationReportTests(unittest.TestCase):
    """Tests for the structured ValidationReport."""

    def test_empty_report_is_ok(self):
        report = ValidationReport()
        self.assertTrue(report.ok)
        self.assertEqual(report.count, 0)

    def test_with_issues(self):
        report = ValidationReport(
            issues=(
                ValidationIssue(
                    entity_type="model",
                    entity_id="orphan",
                    field="provider_id",
                    message="references unknown provider 'ghost'",
                ),
            )
        )
        self.assertFalse(report.ok)
        self.assertEqual(report.count, 1)


class ExceptionTests(unittest.TestCase):
    """The new exceptions are subclasses of LLMConfigurationError."""

    def test_registry_load_error_is_llm_config_error(self):
        self.assertTrue(
            issubclass(RegistryLoadError, LLMConfigurationError)
        )

    def test_registry_validation_error_is_llm_config_error(self):
        self.assertTrue(
            issubclass(RegistryValidationError, LLMConfigurationError)
        )

    def test_load_error_carries_report(self):
        report = LoadReport(
            issues=(
                LoadIssue(
                    file_path="x.yaml",
                    position="(root)",
                    message="file not found",
                ),
            )
        )
        error = RegistryLoadError(report)
        self.assertIs(error.report, report)
        # __str__ comes from Exception; verify it includes the diagnostic.
        self.assertIn("file not found", str(error))

    def test_validation_error_carries_report(self):
        report = ValidationReport(
            issues=(
                ValidationIssue(
                    entity_type="model",
                    entity_id="orphan",
                    field="provider_id",
                    message="references unknown provider 'ghost'",
                ),
            )
        )
        error = RegistryValidationError(report)
        self.assertIs(error.report, report)
        self.assertIn("orphan", str(error))


if __name__ == "__main__":
    unittest.main()