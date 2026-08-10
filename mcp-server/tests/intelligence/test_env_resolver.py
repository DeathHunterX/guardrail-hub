"""Unit tests for the EnvironmentResolver — ${ENV_VAR} substitution."""

import os
import unittest

from app.intelligence.registry.resolver import EnvironmentResolver


class EnvironmentResolverStringTests(unittest.TestCase):
    """Tests for resolving a single string."""

    def setUp(self):
        self.resolver = EnvironmentResolver()

    def test_resolves_single_placeholder(self):
        env = {"MY_KEY": "abc123"}
        resolved, unresolved = self.resolver.resolve_string("${MY_KEY}", env=env)
        self.assertEqual(resolved, "abc123")
        self.assertEqual(unresolved, [])

    def test_resolves_placeholder_within_text(self):
        env = {"HOST": "localhost"}
        resolved, _ = self.resolver.resolve_string(
            "http://${HOST}:11434", env=env
        )
        self.assertEqual(resolved, "http://localhost:11434")

    def test_resolves_multiple_placeholders(self):
        env = {"A": "alpha", "B": "beta"}
        resolved, _ = self.resolver.resolve_string(
            "${A} and ${B}", env=env
        )
        self.assertEqual(resolved, "alpha and beta")

    def test_unresolved_placeholder_is_reported(self):
        env = {}
        resolved, unresolved = self.resolver.resolve_string(
            "value=${MISSING}", env=env
        )
        self.assertEqual(resolved, "value=${MISSING}")
        self.assertEqual(unresolved, ["MISSING"])

    def test_unresolved_names_are_unique(self):
        env = {}
        # Same missing var appears twice; reported once.
        _, unresolved = self.resolver.resolve_string(
            "${MISSING}-${MISSING}", env=env
        )
        self.assertEqual(unresolved, ["MISSING"])

    def test_empty_string(self):
        resolved, unresolved = self.resolver.resolve_string("", env={})
        self.assertEqual(resolved, "")
        self.assertEqual(unresolved, [])

    def test_no_placeholder(self):
        resolved, unresolved = self.resolver.resolve_string(
            "no placeholders here", env={}
        )
        self.assertEqual(resolved, "no placeholders here")
        self.assertEqual(unresolved, [])

    def test_partial_pattern_not_matched(self):
        env = {"X": "v"}
        # Single $ without braces is not a placeholder.
        resolved, _ = self.resolver.resolve_string("$X and ${X}", env=env)
        self.assertEqual(resolved, "$X and v")


class EnvironmentResolverRecursiveTests(unittest.TestCase):
    """Tests for resolving structured data recursively."""

    def setUp(self):
        self.resolver = EnvironmentResolver()

    def test_resolves_dict_recursively(self):
        env = {"BASE": "https://api.example.com", "KEY": "secret"}
        data = {
            "providers": [
                {
                    "connection": {"base_url": "${BASE}"},
                    "auth": {"api_key": "${KEY}"},
                }
            ]
        }
        resolved, unresolved = self.resolver.resolve(data, env=env)
        self.assertEqual(
            resolved["providers"][0]["connection"]["base_url"],
            "https://api.example.com",
        )
        self.assertEqual(
            resolved["providers"][0]["auth"]["api_key"],
            "secret",
        )
        self.assertEqual(unresolved, [])

    def test_resolves_nested_lists(self):
        env = {"X": "y"}
        data = {"headers": ["${X}", "literal", "${X}"]}
        resolved, _ = self.resolver.resolve(data, env=env)
        self.assertEqual(resolved["headers"], ["y", "literal", "y"])

    def test_unresolved_reports_position(self):
        env = {}
        data = {"providers": [{"auth": {"api_key": "${MISSING}"}}]}
        _, unresolved = self.resolver.resolve(data, env=env)
        self.assertEqual(len(unresolved), 1)
        position, name = unresolved[0]
        self.assertIn("providers", position)
        self.assertIn("auth", position)
        self.assertIn("api_key", position)
        self.assertEqual(name, "MISSING")

    def test_non_strings_pass_through(self):
        env = {}
        data = {
            "port": 11434,
            "enabled": True,
            "rate": 0.5,
            "extra": None,
        }
        resolved, unresolved = self.resolver.resolve(data, env=env)
        self.assertEqual(resolved["port"], 11434)
        self.assertIs(resolved["enabled"], True)
        self.assertEqual(resolved["rate"], 0.5)
        self.assertIsNone(resolved["extra"])
        self.assertEqual(unresolved, [])

    def test_default_uses_real_environment(self):
        # Without env=... argument, resolver falls back to os.environ.
        os.environ["REGISTRY_TEST_PLACEHOLDER"] = "from-real-env"
        try:
            resolved, _ = self.resolver.resolve_string(
                "${REGISTRY_TEST_PLACEHOLDER}"
            )
            self.assertEqual(resolved, "from-real-env")
        finally:
            del os.environ["REGISTRY_TEST_PLACEHOLDER"]


if __name__ == "__main__":
    unittest.main()