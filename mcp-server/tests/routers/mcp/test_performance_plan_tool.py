"""C3.5 — the ``generate_performance_plan`` MCP tool (ADR-0010 §5).

Covers the tool's whole contract: validate via the JMX validator, persist through
the plan store, return the reference — and prove it enqueues nothing, executes
nothing, and touches no dispatcher / operation machinery. The real
``JmxPlanValidator`` is used so rejection messages are the real ones; the store is
an in-memory fake so nothing hits disk.
"""

import ast
import unittest
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrations.jmeter.jmx_validator import JmxValidationError
from app.integrations.jmeter.plan_validator import JmxPlanValidator
from app.routers.mcp.performance_router import (
    get_performance_plan_service,
    performance_router,
)
from app.services.performance.plan_tool import PerformancePlanService

_VALID_PLAN = "<jmeterTestPlan><hashTree/></jmeterTestPlan>"
_SCRIPTING_PLAN = (
    '<jmeterTestPlan><hashTree>'
    '<BeanShellSampler testclass="BeanShellSampler"/>'
    '</hashTree></jmeterTestPlan>'
)
_UNKNOWN_PLAN = (
    '<jmeterTestPlan><hashTree>'
    '<EvilSampler testclass="EvilSampler"/>'
    '</hashTree></jmeterTestPlan>'
)


class _FakePlanStore:
    """Records what was persisted (server-side ``put``); no disk, no ``get`` need."""

    def __init__(self):
        self.puts = []  # list[(operation_id, plan_bytes, timeout_seconds)]

    def put(self, operation_id: str, plan: bytes, timeout_seconds: Optional[float] = None) -> None:
        self.puts.append((operation_id, plan, timeout_seconds))


class PlanServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = _FakePlanStore()
        self.service = PerformancePlanService(JmxPlanValidator(), self.store)

    def test_valid_plan_is_stored_and_reference_returned(self):
        plan_id = self.service.generate_plan(_VALID_PLAN, timeout_seconds=300.0)
        self.assertEqual(len(self.store.puts), 1)
        op_id, data, timeout = self.store.puts[0]
        self.assertEqual(op_id, plan_id)  # returned reference is the storage key
        self.assertEqual(data, _VALID_PLAN.encode())  # persisted as bytes
        self.assertEqual(timeout, 300.0)

    def test_reference_is_unique_per_call(self):
        a = self.service.generate_plan(_VALID_PLAN)
        b = self.service.generate_plan(_VALID_PLAN)
        self.assertNotEqual(a, b)

    def test_scripting_plan_rejected_and_nothing_stored(self):
        with self.assertRaises(JmxValidationError):
            self.service.generate_plan(_SCRIPTING_PLAN)
        self.assertEqual(self.store.puts, [])  # validate BEFORE persist

    def test_unknown_component_rejected_and_nothing_stored(self):
        with self.assertRaises(JmxValidationError):
            self.service.generate_plan(_UNKNOWN_PLAN)
        self.assertEqual(self.store.puts, [])


class ToolEndpointTests(unittest.TestCase):
    def setUp(self):
        self.store = _FakePlanStore()
        service = PerformancePlanService(JmxPlanValidator(), self.store)
        app = FastAPI()
        app.include_router(performance_router)
        app.dependency_overrides[get_performance_plan_service] = lambda: service
        self.client = TestClient(app)

    def _post(self, plan):
        return self.client.post("/performance/generate_plan", json={"plan": plan})

    def test_valid_plan_returns_reference(self):
        resp = self._post(_VALID_PLAN)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()["result"]
        self.assertEqual(body["status"], "validated")
        self.assertEqual(body["plan_id"], self.store.puts[0][0])

    def test_invalid_plan_is_400_with_validator_message(self):
        resp = self._post(_SCRIPTING_PLAN)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("scripting", resp.json()["detail"].lower())
        self.assertEqual(self.store.puts, [])  # nothing stored on rejection

    def test_missing_plan_field_is_422(self):
        resp = self.client.post("/performance/generate_plan", json={})
        self.assertEqual(resp.status_code, 422)


class ScopeGuardTests(unittest.TestCase):
    """Structural proof the tool neither enqueues nor executes: it imports no
    operation / dispatcher / DAO machinery."""

    _FORBIDDEN = (
        "operation_service",
        "operation_dao",
        "get_operation_dao",
        "dispatcher",
        "pool",
    )

    def _imports(self, rel_path):
        tree = ast.parse(Path(rel_path).read_text(encoding="utf-8"))
        mods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
        return mods

    def test_service_and_router_have_no_execution_imports(self):
        for rel in (
            "app/services/performance/plan_tool.py",
            "app/routers/mcp/performance_router.py",
        ):
            for mod in self._imports(rel):
                for forbidden in self._FORBIDDEN:
                    self.assertNotIn(
                        forbidden, mod, msg=f"{rel} imports execution machinery: {mod}"
                    )

    def test_service_reads_no_settings(self):
        # Gate E: the subsystem service never reads Settings.
        for mod in self._imports("app/services/performance/plan_tool.py"):
            self.assertFalse(mod == "app.core.config" or mod.startswith("app.core.config."))


if __name__ == "__main__":
    unittest.main()
