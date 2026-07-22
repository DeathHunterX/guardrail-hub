"""Unit tests for the engine-neutral seam (ADR-0010 §2.4 / §4.4, D5).

Two things matter here and nothing else:

1. The neutral DTOs and the ``PerformanceRunner`` protocol behave as specified.
2. **Seam purity** — the engine package names no engine specifics and imports
   nothing engine-specific. This is the guard that keeps "the engine is
   replaceable" true: if a JMeter-ism ever leaks into this package, adding
   k6/Gatling later would require changing the seam. The test fails loudly if it
   does.
"""

import ast
import pkgutil
import unittest
from pathlib import Path
from threading import Event

import app.services.performance.engine as engine_pkg
from app.services.performance.engine import (
    Artifact,
    ArtifactKind,
    ArtifactSet,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    PerformanceRunner,
)


class _FakeRunner:
    """Minimal structural implementation of the protocol (no real engine)."""

    def run(self, request: ExecutionRequest, cancel: Event) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            duration_seconds=0.0,
            artifacts=ArtifactSet(),
        )


class EngineSeamDtoTests(unittest.TestCase):
    def test_artifact_set_filters_by_kind(self):
        results = Artifact(ArtifactKind.RESULTS, Path("/w/op/results.out"))
        report = Artifact(ArtifactKind.REPORT, Path("/w/op/report/index.html"))
        artifacts = ArtifactSet((results, report))

        self.assertEqual(artifacts.of_kind(ArtifactKind.RESULTS), (results,))
        self.assertEqual(artifacts.of_kind(ArtifactKind.REPORT), (report,))
        self.assertEqual(artifacts.of_kind(ArtifactKind.LOG), ())

    def test_execution_result_defaults_to_empty_artifact_set(self):
        result = ExecutionResult(
            status=ExecutionStatus.FAILED, exit_code=1, duration_seconds=1.5
        )
        self.assertEqual(result.artifacts.artifacts, ())
        self.assertIsNone(result.error)

    def test_request_is_engine_neutral_shape(self):
        request = ExecutionRequest(
            operation_id="op-1",
            plan_path=Path("/w/op/plan"),
            output_dir=Path("/w/op/out"),
            timeout_seconds=30.0,
        )
        self.assertEqual(request.operation_id, "op-1")
        self.assertEqual(request.timeout_seconds, 30.0)


class PerformanceRunnerProtocolTests(unittest.TestCase):
    def test_fake_runner_satisfies_protocol(self):
        # runtime_checkable protocol: a structural implementation qualifies
        # without inheritance — the property k6/Gatling adapters will rely on.
        self.assertIsInstance(_FakeRunner(), PerformanceRunner)

    def test_fake_runner_returns_neutral_result(self):
        result = _FakeRunner().run(
            ExecutionRequest("op-1", Path("/w/plan"), Path("/w/out")), Event()
        )
        self.assertEqual(result.status, ExecutionStatus.COMPLETED)


class SeamPurityTests(unittest.TestCase):
    """The engine package must name no engine in its API and import no adapter.

    The guard is over *code* — imports and the public contract surface — not
    prose: the docstrings deliberately cite JMeter/k6/Gatling as examples to
    explain the neutrality, which is good documentation, not coupling.
    """

    _FORBIDDEN = ("jmeter", "jmx", "jtl", "k6", "gatling", "locust")

    def _engine_module_paths(self):
        pkg_dir = Path(engine_pkg.__file__).parent
        for module in pkgutil.iter_modules([str(pkg_dir)]):
            yield pkg_dir / f"{module.name}.py"
        yield Path(engine_pkg.__file__)  # the package __init__

    def _imported_module_names(self):
        """Every module name imported by the engine package (via AST)."""
        for path in self._engine_module_paths():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        yield alias.name
                elif isinstance(node, ast.ImportFrom):
                    yield node.module or ""

    def test_engine_package_imports_no_concrete_adapter(self):
        # Real imports only (ignores docstrings/comments): nothing under an
        # integrations adapter, and no engine-named module.
        for name in self._imported_module_names():
            self.assertNotIn(
                "integrations",
                name,
                msg=f"engine seam imports an adapter module: {name}",
            )
            for token in self._FORBIDDEN:
                self.assertNotIn(token, name.lower())

    def test_public_api_and_vocabulary_are_engine_neutral(self):
        # The exported symbols and the enum values are the contract surface —
        # none may name an engine (that is what keeps engines replaceable).
        surface = list(engine_pkg.__all__)
        surface += [m.value for m in ArtifactKind] + [m.value for m in ExecutionStatus]
        for name in surface:
            for token in self._FORBIDDEN:
                self.assertNotIn(
                    token,
                    name.lower(),
                    msg=f"engine-specific token '{token}' in public surface '{name}'",
                )


if __name__ == "__main__":
    unittest.main()
