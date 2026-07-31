"""The worker HTTP surface after `GET /workers` became cross-engine.

`GET /workers` used to return `list[ZapWorkerInfo]`. It now returns every
engine's workers. That is the one deliberate change, and it is the dangerous
kind: a caller gets 200 with a different body rather than a 404, so nothing
fails loudly. Everything else about the ZAP surface — in particular the four
paths a running worker's sidecar calls — has to keep working untouched, and
that is most of what this file asserts.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.public.jmeter_worker_router import jmeter_worker_router
from app.routers.public.worker_directory_router import worker_directory_router
from app.routers.public.zap_worker_router import (
    zap_worker_legacy_router,
    zap_worker_router,
)
from app.schemas.public.worker_directory import UnifiedWorkerInfo

_T = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(worker_directory_router)
    app.include_router(zap_worker_router)
    app.include_router(zap_worker_legacy_router)
    app.include_router(jmeter_worker_router)
    return TestClient(app)


def _unified(worker_id, worker_type, available=True, op_id=None):
    return UnifiedWorkerInfo(
        worker_type=worker_type, worker_id=worker_id, hostname=f"{worker_type}-host",
        endpoint=f"http://{worker_type}-host:8080", port=8080, state="active",
        op_id=op_id, available=available, last_heartbeat=_T,
    )


class UnifiedEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_it_returns_workers_from_every_engine(self):
        with patch(
            "app.routers.public.worker_directory_router._service"
        ) as service:
            service.list_workers.return_value = [
                _unified("j-1", "jmeter"), _unified("z-1", "zap", available=False, op_id="op-1")
            ]
            response = self.client.get("/workers")

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(["jmeter", "zap"], [w["worker_type"] for w in body])

    def test_each_entry_carries_type_and_availability(self):
        with patch("app.routers.public.worker_directory_router._service") as service:
            service.list_workers.return_value = [_unified("z-1", "zap", available=False, op_id="op-1")]
            worker = self.client.get("/workers").json()[0]

        self.assertEqual("zap", worker["worker_type"])
        self.assertFalse(worker["available"])
        self.assertEqual("op-1", worker["op_id"])
        self.assertEqual("active", worker["state"])

    def test_an_empty_pool_is_an_empty_list(self):
        with patch("app.routers.public.worker_directory_router._service") as service:
            service.list_workers.return_value = []
            response = self.client.get("/workers")

        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())


class LegacyZapSurfaceTests(unittest.TestCase):
    """The four paths docker/owasp_zap/register-worker.sh calls must not move."""

    def setUp(self):
        self.client = _client()

    def test_register_still_answers_on_the_legacy_prefix(self):
        with patch("app.routers.public.zap_worker_router._service") as service:
            service.register.return_value = type(
                "I", (), {"worker_id": "z-1", "hostname": "h", "endpoint": "http://h:8080",
                          "state": "active", "registered_at": _T}
            )()
            response = self.client.post(
                "/workers/register",
                json={"worker_id": "z-1", "hostname": "h", "endpoint": "http://h:8080", "port": 8080},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("z-1", response.json()["worker_id"])

    def test_heartbeat_still_answers_on_the_legacy_prefix(self):
        with patch("app.routers.public.zap_worker_router._service") as service:
            service.heartbeat.return_value = type(
                "I", (), {"worker_id": "z-1", "state": "active", "last_heartbeat": _T}
            )()
            response = self.client.post("/workers/heartbeat", json={"worker_id": "z-1"})

        self.assertEqual(200, response.status_code)

    def test_delete_still_answers_on_the_legacy_prefix(self):
        with patch("app.routers.public.zap_worker_router._service") as service:
            service.remove.return_value = None
            response = self.client.delete("/workers/z-1")

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["removed"])

    def test_drain_still_answers_on_the_legacy_prefix(self):
        with patch("app.routers.public.zap_worker_router._service") as service:
            service.drain.return_value = {
                "worker_id": "z-1", "hostname": "h", "endpoint": "http://h:8080",
                "port": 8080, "state": "draining", "op_id": None,
                "last_heartbeat": _T, "registered_at": _T,
            }
            response = self.client.post("/workers/z-1/drain")

        self.assertEqual(200, response.status_code)

    def test_the_zap_only_list_moved_to_its_own_prefix(self):
        with patch("app.routers.public.zap_worker_router._service") as service:
            service.list_workers.return_value = []
            response = self.client.get("/zap-workers")

        self.assertEqual(200, response.status_code)

    def test_the_write_paths_are_reachable_under_both_prefixes(self):
        # The canonical prefix is additive: the sidecar may migrate whenever, or
        # never, without a flag day.
        with patch("app.routers.public.zap_worker_router._service") as service:
            service.remove.return_value = None
            legacy = self.client.delete("/workers/z-1")
            canonical = self.client.delete("/zap-workers/z-1")

        self.assertEqual(200, legacy.status_code)
        self.assertEqual(200, canonical.status_code)


class JMeterSurfaceTests(unittest.TestCase):
    def test_the_jmeter_endpoints_are_untouched(self):
        client = _client()
        with patch("app.routers.public.jmeter_worker_router._service") as service:
            service.list_workers.return_value = []
            response = client.get("/jmeter-workers")

        self.assertEqual(200, response.status_code)


if __name__ == "__main__":
    unittest.main()
