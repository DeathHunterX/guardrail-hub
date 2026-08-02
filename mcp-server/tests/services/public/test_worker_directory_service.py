"""The cross-engine worker view: projection, availability, ordering, isolation.

Built with the real ``ZapWorkerInfo`` / ``JMeterWorkerInfo`` models rather than
stand-ins, so the projection is exercised against the shapes the registries
actually hold — the whole risk in an aggregation layer is drifting from its
sources, and a fake worker object would hide exactly that.
"""

import unittest
from datetime import datetime, timezone

from app.schemas.tools.jmeter.worker import JMeterWorkerInfo, JMeterWorkerState
from app.schemas.tools.owasp_zap.worker import ZapWorkerInfo, ZapWorkerLifecycleState
from app.services.public.worker_directory_service import WorkerDirectoryService

_T = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _zap(worker_id, hostname="zap-a", state=ZapWorkerLifecycleState.ACTIVE, op_id=None):
    return ZapWorkerInfo(
        worker_id=worker_id, hostname=hostname, endpoint=f"http://{hostname}:8080",
        port=8080, state=state, op_id=op_id, last_heartbeat=_T, registered_at=_T,
    )


def _jmeter(worker_id, hostname="jm-a", state=JMeterWorkerState.ACTIVE, op_id=None):
    return JMeterWorkerInfo(
        worker_id=worker_id, hostname=hostname, endpoint=f"http://{hostname}:8090",
        port=8090, state=state, op_id=op_id, last_heartbeat=_T,
    )


class _FakeRegistry:
    """Stands in for a real registry, and records any attempt to write to it."""

    def __init__(self, workers):
        self._workers = list(workers)
        self.mutations = []

    def list_all(self):
        # The real registries hand back a snapshot; mirror that.
        return list(self._workers)

    def __getattr__(self, name):
        def _recorder(*args, **kwargs):
            self.mutations.append(name)
        return _recorder

    @property
    def workers(self):
        return self._workers


def _service(zap_workers=(), jmeter_workers=()):
    zap, jmeter = _FakeRegistry(zap_workers), _FakeRegistry(jmeter_workers)
    return WorkerDirectoryService((("zap", zap), ("jmeter", jmeter))), zap, jmeter


class AggregationTests(unittest.TestCase):
    def test_both_registries_appear_in_one_list(self):
        service, _, _ = _service([_zap("zap-1")], [_jmeter("jm-1")])
        workers = service.list_workers()

        self.assertEqual(2, len(workers))
        self.assertEqual({"zap-1", "jm-1"}, {w.worker_id for w in workers})

    def test_each_worker_carries_its_engine(self):
        service, _, _ = _service([_zap("zap-1")], [_jmeter("jm-1")])
        by_id = {w.worker_id: w for w in service.list_workers()}

        self.assertEqual("zap", by_id["zap-1"].worker_type)
        self.assertEqual("jmeter", by_id["jm-1"].worker_type)

    def test_the_projection_copies_the_connection_details(self):
        service, _, _ = _service([_zap("zap-1", hostname="zap-a")])
        worker = service.list_workers()[0]

        self.assertEqual("zap-a", worker.hostname)
        self.assertEqual("http://zap-a:8080", worker.endpoint)
        self.assertEqual(8080, worker.port)
        self.assertEqual(_T, worker.last_heartbeat)

    def test_adding_an_engine_is_one_more_pair(self):
        # "Future worker types must be easy to append": no registration, no
        # subclass — a third tuple, and it shows up.
        third = _FakeRegistry([_jmeter("k6-1", hostname="k6-a")])
        service = WorkerDirectoryService((("k6", third),))

        self.assertEqual(["k6"], [w.worker_type for w in service.list_workers()])


class AvailabilityTests(unittest.TestCase):
    def _available(self, worker):
        service, _, _ = _service([worker])
        return service.list_workers()[0].available

    def test_idle_and_active_is_available(self):
        self.assertTrue(self._available(_zap("w", op_id=None)))

    def test_busy_but_active_is_not_available(self):
        self.assertFalse(self._available(_zap("w", op_id="op-1")))

    def test_idle_but_draining_is_not_available(self):
        # Released mid-drain: idle, yet must never be given new work.
        self.assertFalse(
            self._available(_zap("w", state=ZapWorkerLifecycleState.DRAINING))
        )

    def test_idle_but_offline_is_not_available(self):
        self.assertFalse(
            self._available(_zap("w", state=ZapWorkerLifecycleState.OFFLINE))
        )

    def test_availability_is_computed_the_same_way_for_jmeter(self):
        self.assertTrue(self._available(_jmeter("w")))
        self.assertFalse(self._available(_jmeter("w", op_id="op-2")))
        self.assertFalse(
            self._available(_jmeter("w", state=JMeterWorkerState.DRAINING))
        )

    def test_op_id_and_state_are_still_reported_alongside_it(self):
        # Additive convenience: `available` summarises, it does not replace.
        service, _, _ = _service([_zap("w", op_id="op-9")])
        worker = service.list_workers()[0]

        self.assertEqual("op-9", worker.op_id)
        self.assertEqual("active", worker.state)
        self.assertFalse(worker.available)


class OrderingTests(unittest.TestCase):
    def test_sorted_by_type_then_hostname_then_id(self):
        service, _, _ = _service(
            [_zap("z-2", hostname="zap-b"), _zap("z-1", hostname="zap-a")],
            [_jmeter("j-2", hostname="jm-b"), _jmeter("j-1", hostname="jm-a")],
        )
        listed = [(w.worker_type, w.hostname, w.worker_id) for w in service.list_workers()]

        self.assertEqual(
            [("jmeter", "jm-a", "j-1"), ("jmeter", "jm-b", "j-2"),
             ("zap", "zap-a", "z-1"), ("zap", "zap-b", "z-2")],
            listed,
        )

    def test_workers_sharing_a_host_are_ordered_by_id(self):
        service, _, _ = _service(
            [_zap("z-b", hostname="same"), _zap("z-a", hostname="same")]
        )
        self.assertEqual(["z-a", "z-b"], [w.worker_id for w in service.list_workers()])

    def test_the_order_does_not_depend_on_registry_order(self):
        forwards, _, _ = _service([_zap("z-1"), _zap("z-2")], [_jmeter("j-1")])
        backwards, _, _ = _service([_zap("z-2"), _zap("z-1")], [_jmeter("j-1")])

        self.assertEqual(
            [w.worker_id for w in forwards.list_workers()],
            [w.worker_id for w in backwards.list_workers()],
        )


class EmptyRegistryTests(unittest.TestCase):
    def test_no_workers_anywhere_is_an_empty_list_not_an_error(self):
        service, _, _ = _service()
        self.assertEqual([], service.list_workers())

    def test_one_empty_engine_does_not_hide_the_other(self):
        service, _, _ = _service([], [_jmeter("j-1")])
        self.assertEqual(["j-1"], [w.worker_id for w in service.list_workers()])

        service, _, _ = _service([_zap("z-1")], [])
        self.assertEqual(["z-1"], [w.worker_id for w in service.list_workers()])


class ReadOnlyTests(unittest.TestCase):
    """The registries stay authoritative and untouched."""

    def test_aggregation_never_writes_to_a_registry(self):
        service, zap, jmeter = _service([_zap("z-1")], [_jmeter("j-1")])
        service.list_workers()

        self.assertEqual([], zap.mutations)
        self.assertEqual([], jmeter.mutations)

    def test_the_source_workers_are_not_modified(self):
        original_zap, original_jmeter = _zap("z-1", op_id="op-1"), _jmeter("j-1")
        before = (original_zap.model_dump(), original_jmeter.model_dump())
        service, _, _ = _service([original_zap], [original_jmeter])

        service.list_workers()

        self.assertEqual(before, (original_zap.model_dump(), original_jmeter.model_dump()))

    def test_the_returned_models_are_copies_not_views(self):
        source = _zap("z-1")
        service, _, _ = _service([source])

        service.list_workers()[0].worker_id = "tampered"

        self.assertEqual("z-1", source.worker_id)

    def test_repeated_reads_are_stable(self):
        service, _, _ = _service([_zap("z-1")], [_jmeter("j-1")])
        self.assertEqual(
            [w.model_dump() for w in service.list_workers()],
            [w.model_dump() for w in service.list_workers()],
        )


if __name__ == "__main__":
    unittest.main()
