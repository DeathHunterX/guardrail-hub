"""Unit tests for OpenAPI endpoint expansion (pure)."""

import json
import unittest

from app.services.tools.owasp_zap.suite.openapi import extract_endpoints


_SPEC = {
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/login": {"post": {"summary": "login"}},
        "/users": {"get": {}, "post": {}},
        "/ping": {"x-ignored": {}, "parameters": []},
    },
}


class ExtractEndpointsTests(unittest.TestCase):
    def test_expands_methods_and_uses_server_base_url(self):
        eps = extract_endpoints(_SPEC)
        pairs = sorted((e.method, e.url) for e in eps)
        self.assertIn(("POST", "https://api.example.com/login"), pairs)
        self.assertIn(("GET", "https://api.example.com/users"), pairs)
        self.assertIn(("POST", "https://api.example.com/users"), pairs)
        self.assertEqual(len(eps), 3)  # non-method keys ignored

    def test_explicit_base_url_overrides_servers(self):
        eps = extract_endpoints(_SPEC, base_url="https://staging/")
        self.assertTrue(all(e.url.startswith("https://staging/") for e in eps))

    def test_method_filter(self):
        eps = extract_endpoints(_SPEC, methods=["GET"])
        self.assertEqual([e.method for e in eps], ["GET"])

    def test_accepts_json_string(self):
        eps = extract_endpoints(json.dumps(_SPEC))
        self.assertEqual(len(eps), 3)

    def test_accepts_yaml_string(self):
        yaml_spec = "paths:\n  /a:\n    get: {}\n"
        eps = extract_endpoints(yaml_spec, base_url="https://h")
        self.assertEqual([(e.method, e.url) for e in eps], [("GET", "https://h/a")])


if __name__ == "__main__":
    unittest.main()
