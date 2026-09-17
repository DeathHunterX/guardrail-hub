# Maintenance Strategy

## Purpose

Keep `.ai/intelligence/` accurate without mechanically inventing architectural conclusions or accepting stale prose as truth.

## Scope

The twelve Intelligence documents, their declared source paths and their shared CI gate.

## AI Usage Guidance

Run `python .ai/tools/aios.py check`. A drift failure means the affected document must be re-read against its declared sources and corrected before its baseline is updated.

## Main Content

### Model

`.ai/intelligence/scripts/sources.json` maps each document to the repository paths that support its claims. `check_drift.py` computes a content hash for those sources and compares it with the last reviewed baseline.

Directory hashes use Git's view of the repository:

- tracked files, including a sentinel for tracked files deleted in the working tree;
- untracked files that are not ignored by repository ignore rules;
- no ignored virtual environments, logs, caches, build outputs or machine-global ignore configuration.

This makes a baseline portable between developer machines and CI while still detecting meaningful additions, removals and edits. If Git metadata is unavailable, the script uses a filesystem fallback so the diagnostic remains usable, but the repository CI path always runs from a Git checkout.

Content hashing is checkout-portable: files Git treats as text have CRLF
sequences canonicalized to LF before hashing, while binary files retain their
exact bytes. The checker still reads the working tree, so substantive
uncommitted edits remain visible; a newline-only checkout conversion does not.

The hash only identifies which prose may be stale. It cannot decide whether a capability is implemented, planned, safe or correctly described. That judgment remains a human/AI re-review.

### Commands

```bash
python .ai/tools/aios.py intelligence-drift
python .ai/tools/aios.py check

# Only after re-reviewing the named document:
python .ai/intelligence/scripts/check_drift.py --update api-map.md

# Only after re-reviewing all twelve documents:
python .ai/intelligence/scripts/check_drift.py --update
```

`aios check` treats drift as a failure. [`.github/workflows/aios-check.yml`](../../.github/workflows/aios-check.yml) runs that gate for pull requests and pushes to `main`. Repository administrators must configure branch protection/rulesets to require its `AIOS Check` status; a workflow file cannot enforce that setting by itself.

### Update procedure

1. Run `python .ai/tools/aios.py intelligence-drift` and note every flagged document.
2. Re-read each document and all source paths declared for it in `sources.json`.
3. Correct facts and the document's `Last Updated` entry. Cross-check related documents when a fact spans several maps.
4. Run `check_drift.py --update <document>` only for documents actually reviewed.
5. Update the manifest's top-level verification commit/date when completing a coordinated full review.
6. Run `python .ai/tools/aios.py check` and the drift regression tests before merge.

Never resolve CI by running `--update` without reviewing the flagged content. That converts detected staleness into an approved falsehood.

### Changing scope

When a new subsystem affects an existing document, extend that document's `sources` entry. When a genuinely new type of current-state question is needed, add a document using the standard sections, register it in `sources.json`, and add it to [README.md](README.md). Prefer extending an existing map over creating overlapping truth.

## Related Documents

[README.md](README.md) · [deployment-map.md](deployment-map.md) · [`.ai/tools/README.md`](../tools/README.md)

## Last Updated

2026-09-17 — Canonical text hashing across LF and CRLF checkouts.
