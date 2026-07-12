"""Regression guard for the ZapApiScanService singleton constructor contract.

Startup injects the shared OperationService via ``ZapApiScanService(operation_service=...)``.
Because the class defines a custom ``__new__``, that method receives the
constructor's keyword arguments and MUST tolerate them — otherwise every boot
raises ``TypeError: __new__() got an unexpected keyword argument`` inside the
startup sequence and the container crash-loops.

The full scanner import pulls FastAPI/zaproxy (absent from the unit sandbox), so
the AST check below runs everywhere; the runtime check runs wherever the app's
own dependencies are installed.
"""

import ast
import inspect
import pathlib
import unittest

import pytest

_API_SCANNER = (
    pathlib.Path(__file__).resolve().parents[4]
    / "app" / "services" / "tools" / "owasp_zap" / "api_scanner.py"
)


def _new_signature_accepts_varargs(source: str) -> bool:
    """Return True iff ZapApiScanService.__new__ accepts *args or **kwargs."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ZapApiScanService":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__new__":
                    return bool(item.args.vararg or item.args.kwarg)
    raise AssertionError("ZapApiScanService.__new__ not found")


class SingletonConstructorContractTests(unittest.TestCase):
    def test_new_accepts_constructor_arguments(self):
        source = _API_SCANNER.read_text(encoding="utf-8")
        self.assertTrue(
            _new_signature_accepts_varargs(source),
            "ZapApiScanService.__new__ must accept *args/**kwargs so startup can "
            "construct it with operation_service=... without a TypeError.",
        )

    def test_new_tolerates_kwargs_at_runtime(self):
        # Runs only where the scanner's own dependencies are installed.
        pytest.importorskip("fastapi")
        from app.services.tools.owasp_zap.api_scanner import ZapApiScanService

        # Call __new__ directly with the injected kwarg — this is the exact call
        # that used to raise, isolated from __init__ (no DAO/config needed).
        instance = ZapApiScanService.__new__(
            ZapApiScanService, operation_service=object()
        )
        self.assertIsInstance(instance, ZapApiScanService)
        self.assertIn("operation_service", inspect.signature(ZapApiScanService.__init__).parameters)


if __name__ == "__main__":
    unittest.main()
