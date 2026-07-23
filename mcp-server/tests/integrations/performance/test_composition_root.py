"""C3.4 — composition root + lifecycle, and Gates A/C/D/E (ADR-0010 §4.10-§4.12).

Verifies the wiring assembles one shared singleton graph, that construction /
Settings / composition-root imports stay inside the composition root, that the
OperationStatusSink conforms, and that router mounting + dispatcher lifecycle are
wired. All mechanical.
"""

import ast
import dataclasses
import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace

import app.bootstrap as bootstrap
from app.integrations.performance import wiring

# ── Module sets ──────────────────────────────────────────────────────────────
_APP = Path("app")
_COMPOSITION_ROOT_FILES = {
    "app/integrations/performance/wiring.py",
    "app/bootstrap.py",
    "app/core/startup.py",
    "app/main.py",
}
_SUBSYSTEM_ROOTS = (
    "app/services/performance",
    "app/integrations/performance",
    "app/integrations/jmeter",
)
_SUBSYSTEM_EXTRA = (
    "app/routers/public/performance_worker_router.py",
    "app/routers/public/performance_worker_auth.py",
)
# The five subsystem objects that must be constructed only in the composition root.
_SUBSYSTEM_CLASSES = frozenset(
    {
        "PerformanceWorkerRegistry",
        "PerformancePoolManager",
        "PerformanceDispatcher",
        "WorkerCoordinator",
        "RoundRobinScheduler",  # import-origin-aware (shared name with ZAP)
    }
)
_PERF_ORIGIN_PREFIXES = ("app.integrations.performance", "app.services.performance")


def _iter_app_files():
    for py in _APP.rglob("*.py"):
        if "__pycache__" not in str(py):
            yield py


def _subsystem_files():
    for py in _iter_app_files():
        rel = str(py).replace("\\", "/")
        in_roots = any(rel.startswith(r) for r in _SUBSYSTEM_ROOTS)
        if (in_roots or rel in _SUBSYSTEM_EXTRA) and rel not in _COMPOSITION_ROOT_FILES:
            yield py


def _imported_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


class GateA_SingletonIdentity(unittest.TestCase):
    def test_registry_scheduler_pool_dispatcher_coordinator_are_shared(self):
        ops = bootstrap.build_performance_operation_service(object())
        coordinator = bootstrap.build_performance_coordinator(ops)
        dispatcher = bootstrap.build_performance_dispatcher(dao=object(), operation_service=ops)
        pool = bootstrap.get_performance_pool_manager()

        # One registry, shared by coordinator, pool, and (via pool) dispatcher.
        self.assertIs(coordinator._registry, wiring.registry)
        self.assertIs(pool._registry, wiring.registry)
        self.assertIs(dispatcher._pool_manager, pool)
        # Pool + scheduler are single instances (cached).
        self.assertIs(bootstrap.get_performance_pool_manager(), pool)
        self.assertIs(pool._scheduler, bootstrap.get_performance_pool_manager()._scheduler)


class GateC_ConstructionPurity(unittest.TestCase):
    def _perf_construction_sites(self):
        sites = []
        for py in _iter_app_files():
            tree = ast.parse(py.read_text(encoding="utf-8"))
            origin = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for a in node.names:
                        if a.name in _SUBSYSTEM_CLASSES:
                            origin[a.asname or a.name] = node.module
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    name = node.func.id
                    src = origin.get(name)
                    if name in _SUBSYSTEM_CLASSES and src and src.startswith(_PERF_ORIGIN_PREFIXES):
                        sites.append((str(py).replace("\\", "/"), name))
        return sites

    def test_constructed_only_in_composition_root(self):
        for file, name in self._perf_construction_sites():
            self.assertIn(
                file,
                _COMPOSITION_ROOT_FILES,
                msg=f"{name} constructed outside the composition root: {file}",
            )


class GateD_DependencyDirection(unittest.TestCase):
    _FORBIDDEN = (
        "app.integrations.performance.wiring",
        "app.bootstrap",
        "app.core.startup",
        "app.main",
    )

    def test_subsystem_never_imports_the_composition_root(self):
        for py in _subsystem_files():
            for mod in _imported_modules(ast.parse(py.read_text(encoding="utf-8"))):
                for forbidden in self._FORBIDDEN:
                    self.assertNotEqual(
                        mod, forbidden, msg=f"{py} imports composition root {forbidden}"
                    )


class GateE_ConfigurationOwnership(unittest.TestCase):
    def test_subsystem_never_reads_settings(self):
        for py in _subsystem_files():
            for mod in _imported_modules(ast.parse(py.read_text(encoding="utf-8"))):
                self.assertFalse(
                    mod == "app.core.config" or mod.startswith("app.core.config."),
                    msg=f"{py} reads Settings (app.core.config) — must be injected",
                )


class OperationStatusSinkConformance(unittest.TestCase):
    def test_operation_service_satisfies_the_sink(self):
        from app.services.operations.operation_service import OperationService

        self.assertTrue(callable(getattr(OperationService, "complete", None)))
        self.assertTrue(callable(getattr(OperationService, "fail", None)))
        self.assertTrue(callable(getattr(OperationService, "cancel", None)))
        self.assertIn("operation_id", inspect.signature(OperationService.complete).parameters)
        self.assertIn("error", inspect.signature(OperationService.fail).parameters)


class RouterMounting(unittest.TestCase):
    def test_no_db_returns_no_router(self):
        cfg = SimpleNamespace(database_provider="NONE")
        self.assertIsNone(bootstrap.build_performance_worker_router_from_settings(config=cfg))

    def test_router_built_and_mounted_when_db_configured(self):
        from app.core.config import settings

        if settings.database_provider == "NONE":
            self.skipTest("no DB configured in this environment")
        router = bootstrap.build_performance_worker_router_from_settings(config=settings)
        self.assertIsNotNone(router)
        self.assertEqual(len(router.routes), 4)
        import app.main as m

        self.assertIsNotNone(getattr(m, "_performance_worker_router", None))


class _FakeDao:
    def get_queued_operations(self, types=None):
        return []


class DispatcherLifecycle(unittest.TestCase):
    def test_start_stop_is_idempotent(self):
        ops = bootstrap.build_performance_operation_service(object())
        dispatcher = bootstrap.build_performance_dispatcher(
            dao=_FakeDao(), operation_service=ops
        )
        dispatcher.start()
        dispatcher.start()  # idempotent
        dispatcher.stop()

    def test_startup_result_carries_the_performance_dispatcher(self):
        from app.core.startup import StartupResult

        fields = {f.name for f in dataclasses.fields(StartupResult)}
        self.assertIn("performance_dispatcher", fields)


if __name__ == "__main__":
    unittest.main()
