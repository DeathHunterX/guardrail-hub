"""Regression tests for Git-stable Intelligence drift checks."""

from __future__ import annotations

import importlib.util
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


drift = load_module(
    "intelligence_drift",
    REPO_ROOT / ".ai" / "intelligence" / "scripts" / "check_drift.py",
)
aios = load_module("aios_cli", REPO_ROOT / ".ai" / "tools" / "aios.py")


class GitVisibleHashTests(unittest.TestCase):
    """Catch drift hashes that change because of ignored local artifacts."""

    def test_directory_hash_uses_git_visible_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
            source = repo / "source"
            source.mkdir()
            tracked = source / "tracked.txt"
            tracked.write_text("v1", encoding="utf-8")
            subprocess.run(
                ["git", "-c", "core.excludesFile=", "add", ".gitignore", "source/tracked.txt"],
                cwd=repo,
                check=True,
            )

            baseline = drift.hash_path(source, repo_root=repo)

            ignored = source / "runtime.log"
            ignored.write_text("machine A", encoding="utf-8")
            self.assertEqual(baseline, drift.hash_path(source, repo_root=repo))

            visible = source / "new.txt"
            visible.write_text("new source", encoding="utf-8")
            self.assertNotEqual(baseline, drift.hash_path(source, repo_root=repo))

            visible.unlink()
            tracked.write_text("v2", encoding="utf-8")
            self.assertNotEqual(baseline, drift.hash_path(source, repo_root=repo))

    def test_machine_local_git_excludes_cannot_hide_source_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            source = repo / "source"
            source.mkdir()
            tracked = source / "tracked.txt"
            tracked.write_text("v1", encoding="utf-8")
            subprocess.run(
                ["git", "-c", "core.excludesFile=", "add", "source/tracked.txt"],
                cwd=repo,
                check=True,
            )
            baseline = drift.hash_path(source, repo_root=repo)

            (repo / ".git" / "info" / "exclude").write_text(
                "source/local-only.txt\n", encoding="utf-8"
            )
            (source / "local-only.txt").write_text("new source", encoding="utf-8")

            self.assertNotEqual(baseline, drift.hash_path(source, repo_root=repo))


class PortableContentHashTests(unittest.TestCase):
    """Prove source hashes describe content, not checkout newline policy."""

    def _init_repo(self, repo: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    def test_equivalent_lf_and_crlf_text_files_hash_identically(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            source = repo / "source.txt"
            source.write_bytes(b"line1\nline2\n")
            subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)

            baseline = drift.hash_path(source, repo_root=repo)
            source.write_bytes(b"line1\r\nline2\r\n")

            self.assertEqual(baseline, drift.hash_path(source, repo_root=repo))

    def test_real_text_edit_changes_the_hash_after_canonicalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            source = repo / "source.txt"
            source.write_bytes(b"line1\n")
            subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)

            baseline = drift.hash_path(source, repo_root=repo)
            source.write_bytes(b"line1 changed\r\n")

            self.assertNotEqual(baseline, drift.hash_path(source, repo_root=repo))

    def test_binary_content_is_not_newline_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            source = repo / "asset.bin"
            source.write_bytes(b"\x00binary\r\n")
            subprocess.run(["git", "add", "asset.bin"], cwd=repo, check=True)

            baseline = drift.hash_path(source, repo_root=repo)
            source.write_bytes(b"\x00binary\n")

            self.assertNotEqual(baseline, drift.hash_path(source, repo_root=repo))

    def test_directory_hash_is_identical_for_lf_and_crlf_representations(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._init_repo(repo)
            source = repo / "source"
            source.mkdir()
            (source / "one.txt").write_bytes(b"one\n")
            (source / "two.txt").write_bytes(b"two\n")
            subprocess.run(["git", "add", "source"], cwd=repo, check=True)

            baseline = drift.hash_path(source, repo_root=repo)
            (source / "one.txt").write_bytes(b"one\r\n")
            (source / "two.txt").write_bytes(b"two\r\n")

            self.assertEqual(baseline, drift.hash_path(source, repo_root=repo))


class AiosCheckTests(unittest.TestCase):
    """Catch accidental removal of Intelligence drift from the aggregate gate."""

    def test_check_runs_intelligence_drift_and_propagates_failure(self):
        root = REPO_ROOT / ".ai"
        with (
            patch.object(aios, "cmd_validate", return_value=0),
            patch.object(aios, "cmd_links", return_value=0),
            patch.object(aios, "cmd_lint", return_value=0),
            patch.object(aios, "cmd_arch", return_value=0),
            patch.object(aios, "cmd_intelligence_drift", return_value=1) as drift_check,
        ):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(1, aios.cmd_check(root))
            drift_check.assert_called_once_with(root, verbose=False)


if __name__ == "__main__":
    unittest.main()
