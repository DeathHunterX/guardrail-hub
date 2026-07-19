"""Unit tests for the pure scenario-workflow logic (no ZAP / network)."""

import unittest

from app.schemas.tools.owasp_zap.common import ZapTokenType
from app.schemas.tools.owasp_zap.scan_api_scenario import ScenarioStep
from app.services.tools.owasp_zap.scenario.context import (
    ScenarioContext,
    ScenarioStepError,
    dotted_get,
    resolve_execution_order,
)


def _step(name, url="https://api/x", method="GET", **kw):
    return ScenarioStep(name=name, target_url=url, method=method, **kw)


class DottedGetTests(unittest.TestCase):
    def test_reads_nested_dict_and_list(self):
        data = {"data": {"access_token": {"token": "abc"}}, "items": [{"id": 7}]}
        self.assertEqual(dotted_get(data, "data.access_token.token"), "abc")
        self.assertEqual(dotted_get(data, "items.0.id"), 7)

    def test_missing_path_returns_none(self):
        self.assertIsNone(dotted_get({"a": 1}, "a.b.c"))
        self.assertIsNone(dotted_get(None, "x"))


class ExecutionOrderTests(unittest.TestCase):
    def test_authored_order_when_no_dependencies(self):
        steps = [_step("a"), _step("b"), _step("c")]
        self.assertEqual([s.name for s in resolve_execution_order(steps)], ["a", "b", "c"])

    def test_dependencies_are_honoured(self):
        steps = [_step("checkout", depends_on=["login"]), _step("login")]
        self.assertEqual(
            [s.name for s in resolve_execution_order(steps)], ["login", "checkout"]
        )

    def test_unknown_dependency_raises(self):
        with self.assertRaises(ScenarioStepError):
            resolve_execution_order([_step("a", depends_on=["missing"])])

    def test_cycle_raises(self):
        steps = [_step("a", depends_on=["b"]), _step("b", depends_on=["a"])]
        with self.assertRaises(ScenarioStepError):
            resolve_execution_order(steps)


class ScenarioContextTests(unittest.TestCase):
    def test_extract_and_placeholder_substitution(self):
        ctx = ScenarioContext()
        login = _step("login", method="POST", extract={"uid": "data.id"})
        ctx.capture(login, {"data": {"id": 42}})
        step = _step("profile", url="https://api/users/${uid}")
        resolved = ctx.resolve_step(step)
        self.assertEqual(resolved.url, "https://api/users/42")

    def test_jwt_propagation_from_token_field(self):
        ctx = ScenarioContext()
        login = ScenarioStep(
            name="login",
            target_url="https://api/login",
            method="POST",
            token_field="data.access_token",
            token_type=ZapTokenType.JWT,
        )
        ctx.capture(login, {"data": {"access_token": "jwt-123"}})
        self.assertEqual(ctx.token, "jwt-123")
        # Subsequent step (no explicit token) inherits the captured token.
        nxt = ctx.resolve_step(_step("profile"))
        self.assertEqual(nxt.token, "jwt-123")
        self.assertEqual(nxt.token_type, ZapTokenType.JWT)

    def test_cookie_propagation(self):
        ctx = ScenarioContext()
        login = ScenarioStep(
            name="login", target_url="https://api/login", method="POST",
            cookie_field="data.session",
        )
        ctx.capture(login, {"data": {"session": "sid=xyz"}}, set_cookies={"csrf": "tok"})
        resolved = ctx.resolve_step(_step("next"))
        self.assertIn("sid=xyz", resolved.cookie)
        self.assertIn("csrf=tok", resolved.cookie)

    def test_explicit_step_token_overrides_context(self):
        ctx = ScenarioContext()
        ctx.token = "old"
        step = ScenarioStep(
            name="x", target_url="https://api/x", method="GET", token="explicit"
        )
        self.assertEqual(ctx.resolve_step(step).token, "explicit")


if __name__ == "__main__":
    unittest.main()
