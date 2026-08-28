#!/usr/bin/env python3
"""
Drift checker for .ai/intelligence/ documents.

Each intelligence document declares, in sources.json, which repository paths
it was written from. This script hashes the current state of those paths and
compares it to the hash recorded the last time the document was verified.
It does NOT regenerate documents — the "implemented vs. planned" judgment
calls in these docs require a human or an AI assistant to re-read the source
and re-reason about it, not a mechanical diff. This script only tells you
WHICH documents need that re-review, so you never have to re-verify all
twelve just because one file changed.

Usage (run from anywhere; paths are resolved relative to this script):
    python check_drift.py            # report which documents have drifted
    python check_drift.py --update   # after re-reviewing, record new baseline hashes
    python check_drift.py --update system-overview.md   # update just one document
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]  # .ai/intelligence/scripts -> .ai/intelligence -> .ai -> repo root
MANIFEST_PATH = SCRIPT_DIR / "sources.json"


def _git_visible_files(path: Path, repo_root: Path) -> list[Path] | None:
    """Return tracked and non-ignored untracked files below *path*.

    ``None`` means Git metadata is unavailable and the caller should use the
    filesystem fallback. Deleted tracked files are retained so removal changes
    the hash.
    """
    try:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None
    result = subprocess.run(
        [
            "git", "-c", "core.quotePath=false", "-c", "core.excludesFile=",
            "ls-files", "-z",
            "--cached", "--others", "--exclude-per-directory=.gitignore", "--", rel,
        ],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    names = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    return [repo_root / name for name in sorted(set(names) - {""})]


def hash_path(path: Path, *, repo_root: Path = REPO_ROOT) -> str:
    """Hash a file or a directory's Git-visible files and their contents.

    Ignored artifacts such as virtual environments, logs and build output do
    not invalidate shared baselines. Missing paths use a fixed sentinel.
    """
    h = hashlib.sha256()
    if not path.exists():
        h.update(b"__MISSING__")
        return h.hexdigest()
    if path.is_file():
        h.update(path.read_bytes())
        return h.hexdigest()
    files = _git_visible_files(path, repo_root)
    if files is None:
        files = sorted(
            p for p in path.rglob("*")
            if p.is_file() and SCRIPT_DIR not in p.parents
        )
    for f in files:
        h.update(f.relative_to(path).as_posix().encode("utf-8"))
        h.update(f.read_bytes() if f.is_file() else b"__MISSING__")
    return h.hexdigest()


def compute_doc_hash(source_paths: list[str]) -> str:
    h = hashlib.sha256()
    for rel in sorted(source_paths):
        h.update(rel.encode("utf-8"))
        h.update(hash_path(REPO_ROOT / rel).encode("utf-8"))
    return h.hexdigest()


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = sys.argv[1:]
    update_mode = "--update" in args
    if update_mode:
        args.remove("--update")
    target_doc = args[0] if args else None

    manifest = load_manifest()
    documents = manifest["documents"]

    if target_doc and target_doc not in documents:
        print(f"Unknown document: {target_doc}. Known: {', '.join(documents)}")
        return 2

    drifted = []
    no_baseline = []
    for doc_name, entry in documents.items():
        if target_doc and doc_name != target_doc:
            continue
        current_hash = compute_doc_hash(entry["sources"])
        if update_mode:
            entry["hash"] = current_hash
            print(f"[updated]  {doc_name}")
        elif entry.get("hash") is None:
            no_baseline.append(doc_name)
            print(f"[no baseline] {doc_name} - run with --update to set one")
        elif entry["hash"] != current_hash:
            drifted.append(doc_name)
            print(f"[DRIFTED]  {doc_name} - sources changed since last verification: {', '.join(entry['sources'])}")
        else:
            print(f"[ok]       {doc_name}")

    if update_mode:
        save_manifest(manifest)
        return 0

    if drifted or no_baseline:
        if drifted:
            print(f"\n{len(drifted)} document(s) need re-review: {', '.join(drifted)}")
        if no_baseline:
            print(f"{len(no_baseline)} document(s) have no baseline yet: {', '.join(no_baseline)}")
        print("See MAINTENANCE.md for the update procedure.")
        return 1

    print("\nAll checked documents match their last-verified source state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
