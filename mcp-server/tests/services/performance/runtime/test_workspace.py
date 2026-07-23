"""Unit tests for the per-operation Workspace lifecycle (ADR-0010 INV2/INV5)."""

import tempfile
import unittest
from pathlib import Path

from app.services.performance.runtime import (
    InvalidOperationIdError,
    WorkspaceManager,
)


class WorkspaceCreateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.manager = WorkspaceManager(self.base)

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_makes_isolated_empty_tree(self):
        ws = self.manager.create("op-1")
        self.assertTrue(ws.root.is_dir())
        self.assertTrue(ws.output_dir.is_dir())
        self.assertTrue(ws.logs_dir.is_dir())
        # output and logs start empty; plan is a not-yet-written file path
        self.assertEqual(list(ws.output_dir.iterdir()), [])
        self.assertEqual(list(ws.logs_dir.iterdir()), [])
        self.assertFalse(ws.plan_path.exists())

    def test_distinct_operations_get_distinct_roots(self):
        a = self.manager.create("op-a")
        b = self.manager.create("op-b")
        self.assertNotEqual(a.root, b.root)  # INV2: no sharing across operations

    def test_create_clears_stale_remnant(self):
        first = self.manager.create("op-1")
        (first.output_dir / "leftover.txt").write_text("stale")
        # Re-creating the same id must yield a fresh, empty workspace (INV2).
        second = self.manager.create("op-1")
        self.assertEqual(list(second.output_dir.iterdir()), [])

    def test_rejects_traversal_operation_ids(self):
        for bad in ("../escape", "a/b", "a\\b", ".."):
            with self.assertRaises(InvalidOperationIdError):
                self.manager.create(bad)


class WorkspaceCleanupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.manager = WorkspaceManager(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_cleanup_is_idempotent(self):
        ws = self.manager.create("op-1")
        self.manager.cleanup(ws)
        self.assertFalse(ws.root.exists())
        self.manager.cleanup(ws)  # second call must not raise

    def test_context_manager_cleans_up_on_success(self):
        with self.manager.workspace("op-1") as ws:
            (ws.output_dir / "results").write_text("data")
            root = ws.root
            self.assertTrue(root.exists())
        # After the block (i.e. after a would-be persist), the tree is gone.
        self.assertFalse(root.exists())

    def test_context_manager_cleans_up_on_failure(self):
        root_holder = {}

        class _Boom(RuntimeError):
            pass

        with self.assertRaises(_Boom):
            with self.manager.workspace("op-1") as ws:
                root_holder["root"] = ws.root
                self.assertTrue(ws.root.exists())
                raise _Boom("execution or persistence failed")
        # INV5: cleanup still ran on the failure path.
        self.assertFalse(root_holder["root"].exists())


if __name__ == "__main__":
    unittest.main()
