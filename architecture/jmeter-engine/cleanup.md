# JMeter Engine — Repository Cleanup

Status: **Executed (§1) + Recommended (§2)** — 2026-07-28.
Resolves: adjustment **A5** of the [architecture validation report](architecture-review.md).

Context: a generic "Performance engine" branch was merged and then fully reverted (`01c4d00`, `1bf9e3d`, `762e1c5`). The reverts removed the source files but left the directories behind, holding nothing but orphaned `__pycache__`. Empty scaffold folders violate [ADR-0005](../../.ai/decisions/0005-architecture-hardening-refactor.md)'s no-empty-scaffold rule, and — more practically — an empty `app/integrations/jmeter/` on the import path is exactly the kind of thing that shadows or silently confuses the *real* package Phase 1 is about to create.

---

## 1. Removed (trivial and verified safe)

| Removed | Was |
|---|---|
| `mcp-server/app/services/performance/` (incl. `engine/`, `redaction/`, `runtime/`, `worker/`) | Reverted Performance service package |
| `mcp-server/app/schemas/performance/` | Reverted Performance schemas |
| `mcp-server/app/integrations/performance/` | Reverted Performance integration |
| `mcp-server/app/integrations/jmeter/` | Reverted JMeter runner/validators |
| `mcp-server/app/schemas/tools/jmeter/` | Reverted JMeter wire formats |
| `mcp-server/app/services/tools/jmeter/` | Empty (not even a `__pycache__`) |
| `mcp-server/app/workers/` | Reverted `performance_worker` |

Safety established before removal, and re-verified after:

- **No source files.** Every path contained `__pycache__/*.pyc` only (`app/services/tools/jmeter/` and `app/workers/` contained no `.py` at all).
- **Untracked by git.** `git ls-files` returns nothing for any of them — `__pycache__/` is gitignored, so these existed on disk only. Removing them changes no commit and produces no diff.
- **Referenced by nothing.** A repo-wide grep across `app/`, `tests/`, `docker/`, `docker-compose.yml`, `pyproject.toml` and `.env.example` for `performance`, `app.workers`, and the three `jmeter` module paths returns zero hits.
- **No orphaned `__pycache__` remains** anywhere under `app/` (checked: every surviving `__pycache__` sits beside real `.py` files).

Worth recording: this is the **second** removal of two of these paths. [ADR-0005](../../.ai/decisions/0005-architecture-hardening-refactor.md) already deleted `app/integrations/jmeter` and `app/services/tools/jmeter` as empty scaffold on 2026-07-10; the reverted Performance branch recreated them. That is the strongest available argument for the rule the repository already has — a directory appears when it has contents, and Phase 1 creates these for the third and final time *with code in them*.

Phase 1 recreates `app/integrations/jmeter/`, `app/schemas/tools/jmeter/`, and `app/services/tools/jmeter/` as real packages with real content — which is the point: a directory appears when it has something in it.

## 2. Recommended, not executed

These are judgment calls or touch tracked files, so they are raised rather than done.

| Item | Recommendation | Why not executed |
|---|---|---|
| `jmeter-engine-architecture-review.md` at repo root | **Done 2026-08-01** — moved to `architecture/jmeter-engine/architecture-review.md` | `architecture/README.md` states one subfolder per subsystem; a loose design doc at the repo root is the convention this directory exists to prevent. The move waited until it could be made with its five inbound links in the same commit, which is what happened: `README.md`, `cleanup.md` (this file), `queue-isolation.md`, `result-contract.md` and `runtime-responsibility.md` now reference it as a sibling. `aios check` re-validated every link afterwards |
| `mcp-server/README.md` (0 bytes, tracked) | Fill or delete | Tracked and empty. An empty tracked README is the file equivalent of an empty scaffold folder. Deleting it is a real commit and a maintainer's call |
| `mcp-server/requirements.txt` (0 bytes, tracked) | Delete | The project uses `uv` (`pyproject.toml` + `uv.lock`). An empty `requirements.txt` invites someone to `pip install -r` it and conclude there are no dependencies. Tracked, so it is a maintainer's call |
| `mcp-server/.pytest_cache/`, `.venv/` | Leave | Gitignored local tooling state, not revert remnants |
| `mcp-server/{data,logs,reports,public}/` | Leave | Gitignored runtime output directories, in active use |
| `mcp-server/.env` | Out of scope — verify separately | Gitignored and correctly untracked. Flagged only so it is not assumed reviewed |

## 3. Not cleanup — a governance item

[ADR-0009](../../.ai/decisions/0009-execution-capability.md) is still **Proposed** and requires backend-owner ratification. That is a human decision, not a repository operation. See [README](README.md) §4.
