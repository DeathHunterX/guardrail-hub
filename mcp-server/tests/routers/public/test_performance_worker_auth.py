"""C3.3 — worker authentication boundary (ADR-0010 §4.9)."""

import inspect
import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.integrations.performance.registry import PerformanceWorkerRegistry
from app.routers.public.performance_worker_auth import build_worker_token_auth
from app.routers.public.performance_worker_router import build_performance_worker_router
from app.services.performance.worker_api import PlanNotFoundError, WorkerCoordinator

_TOKEN = "test-worker-token"


class _FakePlanStore:
    def get(self, operation_id):
        raise PlanNotFoundError(operation_id)


class _FakeReportStore:
    def __init__(self):
        self.saved = []

    def save(self, report):
        self.saved.append(report)


class _FakeSink:
    def complete(self, operation_id):
        pass

    def fail(self, operation_id, error):
        pass

    def cancel(self, operation_id):
        pass


class WorkerTokenAuthDependencyTests(unittest.TestCase):
    def setUp(self):
        self.dep = build_worker_token_auth(_TOKEN)

    def test_valid_token_passes(self):
        self.assertIsNone(self.dep(f"Bearer {_TOKEN}"))

    def test_missing_header_is_401(self):
        with self.assertRaises(HTTPException) as ctx:
            self.dep(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_invalid_token_is_401(self):
        with self.assertRaises(HTTPException) as ctx:
            self.dep("Bearer wrong-token")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_non_bearer_scheme_is_401(self):
        with self.assertRaises(HTTPException):
            self.dep(f"Basic {_TOKEN}")


class RouterAuthBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.registry = PerformanceWorkerRegistry()
        self.reports = _FakeReportStore()
        coordinator = WorkerCoordinator(
            registry=self.registry,
            plans=_FakePlanStore(),
            reports=self.reports,
            operations=_FakeSink(),
        )
        app = FastAPI()
        app.include_router(
            build_performance_worker_router(
                coordinator, auth_dependency=build_worker_token_auth(_TOKEN)
            )
        )
        self.client = TestClient(app)

    def _register(self, headers):
        return self.client.post(
            "/performance/workers/register",
            json={"worker_id": "w", "hostname": "w", "version": "1.0"},
            headers=headers,
        )

    def test_missing_token_rejected_at_boundary(self):
        self.assertEqual(self._register(headers={}).status_code, 401)
        self.assertIsNone(self.registry.get("w"))  # never reached the coordinator

    def test_invalid_token_rejected_at_boundary(self):
        resp = self._register(headers={"Authorization": "Bearer nope"})
        self.assertEqual(resp.status_code, 401)
        self.assertIsNone(self.registry.get("w"))

    def test_valid_token_reaches_coordinator_unchanged(self):
        resp = self._register(headers={"Authorization": f"Bearer {_TOKEN}"})
        self.assertEqual(resp.status_code, 200)
        # Coordinator ran its normal logic after auth: the worker is registered.
        self.assertIsNotNone(self.registry.get("w"))
        self.assertEqual(resp.json()["worker_id"], "w")


class CoordinatorIsUnawareOfAuthTests(unittest.TestCase):
    def test_coordinator_signature_has_no_auth(self):
        params = list(inspect.signature(WorkerCoordinator.__init__).parameters)
        self.assertNotIn("auth_dependency", params)
        self.assertFalse(any("token" in p or "auth" in p for p in params))

    def test_router_without_auth_dependency_still_builds(self):
        # Backward-compatible: the one-arg factory call (no auth) still works.
        coordinator = WorkerCoordinator(
            registry=PerformanceWorkerRegistry(),
            plans=_FakePlanStore(),
            reports=_FakeReportStore(),
            operations=_FakeSink(),
        )
        router = build_performance_worker_router(coordinator)
        self.assertEqual(len(router.routes), 4)


if __name__ == "__main__":
    unittest.main()
