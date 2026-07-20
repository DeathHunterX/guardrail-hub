# Tools — `aios` CLI

The AIOS deterministic-tooling entry point. Everything the AIOS can check or generate *mechanically* — validation, link checking, index generation, impact analysis, ceiling linting — is a subcommand of one CLI, so CI and any AI need remember only one command. Built in Roadmap M2 ([Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)).

## This Is Not an AIOS Module

Infrastructure, like [schema/](../schema/README.md) and [milestones/](../milestones/README.md): no Agent-facing contract, not Router-addressable, absent from the [Module Index](../README.md#module-index).

## The Principle It Serves

> Automation is responsible for determinism.

Every check here is deterministic — no LLM judgment. This is the boundary from [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md): reasoning is the AI's job, truth is the repository's, and *anything verifiable* is Automation's. From M2 onward these checks run **only** through this CLI — manual verification (used out of necessity through M0–M1) is no longer sanctioned (dogfooding principle, Decision 0001 M2 addendum).

## Usage

```
python .ai/tools/aios.py <command>
```

| Command | Does | Exit |
|---|---|---|
| `validate` | Every unit's frontmatter vs. its schema (via [schema-map.json](schema-map.json)); the `id`==path invariant; **references resolve** (H1 — every `depends_on`/`standards_enforced`/`validated_against` target is a real unit); **no `validated_against` version drift** (H3); **no Agent `decision_authority` overlap** (H2). | nonzero on any error |
| `links` | Every relative markdown link under `.ai/` resolves. | nonzero on any broken link |
| `index [--dry-run]` | (Re)generates `<module>/<category>/INDEX.md` from unit frontmatter. Never hand-edit an INDEX. | 0 |
| `impact <id> [--change major\|minor\|patch]` | Reverse-dependency walk + Impact Report per [governance rules](../governance/README.md#impact-analysis). | 0 |
| `lint` | Line-count ceiling (150) on routing files (MANIFEST/ROUTER/INDEX). | nonzero if any over |
| `arch` | Domain-layer boundary enforcement: scans `mcp-server/app/domain/**` for imports violating [domain-layer](../standards/architecture/domain-layer.md) **D2** (framework/transport/infrastructure) and **D3** (any dependency outside Domain). | nonzero if any violation |
| `check` | `validate` + `links` + `lint` + `arch` as one CI gate. | nonzero on any failure |
| `selftest` | Proves the impact + validation engines on synthetic fixtures. | nonzero on any failure |

`--root <path>` overrides the `.ai/` root (default: this script's own `.ai/`); `selftest` uses it to exercise the engine against temp fixtures. `arch` is the one subcommand that reads the **product** tree rather than `.ai/` — it resolves the repository root as the `.ai/` parent, because the rule it enforces is about application code. Its scanned paths are `DOMAIN_ROOTS` in the CLI; a second Domain root (a future subsystem) is added there.

## Why Standard-Library Only (no `pyyaml`, no `jsonschema`)

Per [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)'s dependency principle, evaluated and decided at M2:

- **Frontmatter** is a deliberately simple documented subset (flat scalars + inline `[a, b]` lists) — safely parsed with the standard library. The simplicity is itself a feature; frontmatter is meant to be machine-trivial.
- **Schema validation** uses only a small, fixed JSON-Schema feature set (`type`, `required`, `properties`, `enum`, `pattern`, `allOf`, `$ref`, `items`, `minItems`, `minLength`, `additionalProperties`). A ~150-line validator covers it exactly.
- **The safety catch:** the validator **fails loud** on any schema keyword it does not implement (raises `SchemaError`, exit 3) rather than silently skipping it — so an unsupported construct is a hard error, never a false "valid." `selftest` additionally asserts every *shipped* schema stays within the supported set, so M3's first real unit cannot crash on an unexercised keyword.
- **Benefit vs. cost:** zero dependencies means the tooling runs on any Python 3 with no venv/pip and no supply-chain surface — a real virtue for a security platform's own governance tooling. `jsonschema`/`pyyaml` are adopted only if schema complexity later outgrows this validator (benefit > cost re-evaluated then), not preemptively.

## For CI

`python .ai/tools/aios.py check` is the single gate. It is intended to run non-blocking until the product repository gains CI (see [intelligence/deployment-map.md](../intelligence/deployment-map.md)), then as a required check. `impact` runs per-PR when a unit's version changes.
