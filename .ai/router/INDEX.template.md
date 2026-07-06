# Category Index — Template & Format Spec

> Not a live index. This is the canonical *format* every `<module>/<category>/INDEX.md` follows. Created in Roadmap M1 ([Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)); the M2 Index-generator script emits files in exactly this shape. No real `INDEX.md` files are hand-created in M1 — a category gets its `INDEX.md` when it gains its first unit (generated from that unit's frontmatter), per the [confirmed M1 scope](../milestones/M1-schema-and-skeleton.md).

## Why INDEX.md Is Generated, Not Hand-Written

An `INDEX.md` is a projection of the frontmatter of every unit in its category. Hand-maintaining it would duplicate truth that already lives in each unit — the exact drift failure Phase 0 forbids. So it is a **generated artifact**: the M2 Index-generator scans a category directory, reads each unit's frontmatter, and emits the table below. A human never edits an `INDEX.md` directly; they edit a unit, and regeneration updates the index. This is the [Router's "cache"](README.md#routing-cache) materialized.

## Canonical Format

Every generated `INDEX.md` has this structure:

```markdown
# Index — <module>/<category>

> Generated from unit frontmatter by the Index-generator. Do not edit by hand.
> Last generated: <date> · Units: <count>

| id | title | version | status | owner | depends_on |
|---|---|---|---|---|---|
| <id> | <title> | <version> | <status> | <owner> | <comma-separated ids or —> |
```

## Rules the Generator Enforces

- **One row per `Active`/`Draft`/`Review`/`Stale` unit.** `Deprecated` units appear in a separate collapsed section (still resolvable for migration notes, excluded from normal Router resolution). `Archived` units do not appear at all — they have been relocated out of the category directory (see [governance/README.md](../governance/README.md#migration--deprecation)).
- **Sorted by `id`.** Deterministic order so regeneration produces no spurious diffs.
- **Size ceiling ~150 lines.** If a category's index would exceed it, the category is sub-partitioned (e.g. `security/` → `security/auth/`, `security/network/`) and each sub-category gets its own `INDEX.md`, with the parent listing sub-categories instead of units — the recursive split from [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)'s scalability model.
- **`depends_on` shown as ids only**, never expanded — the index is addresses, never content, preserving lazy loading.
