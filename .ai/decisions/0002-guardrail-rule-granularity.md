# 0002 — Guardrail Rule Granularity

Status: **Accepted**
Owner: Loi Phan
Date: 2026-07-06

---

## Context

M1 ([milestones/M1](../milestones/M1-schema-and-skeleton.md)) flagged an open question and assigned it to M3: are individual guardrail rules addressable units of their own, or entries within a container file? It surfaced because `guardrails/core.md` (the Tier G file loaded every session) was created as one file, while `guardrail.schema.json` describes an *individual rule* (with `checkpoint`/`enforcement`). The two models can't both be right without a decision.

A technical constraint sharpens the choice: the stdlib frontmatter parser adopted in M2 ([Decision 0001](0001-aios-bootstrap-roadmap.md) dependency principle) accepts only a flat scalar-and-inline-list subset — **no nested YAML**. So per-rule machine-readable metadata (a list of `{checkpoint, enforcement}` objects) cannot live in a single file's frontmatter without either abandoning the stdlib parser or splitting rules into separate files.

## Decision

**Core guardrails live as structured sections in the body of `guardrails/core.md`. `core.md` is a single unit** (`id: guardrails/core`), validated against `base.schema.json`, and **versioned as a set** — a change to any core rule bumps the one unit's version.

- Core rules are *not* individually addressable units. Each rule is a documented section (prohibition, applicable checkpoint(s), block-vs-escalate, a concrete violation example) in prose, not per-rule frontmatter.
- `guardrail.schema.json` (with `checkpoint`/`enforcement`) is reserved for **domain guardrails** — future `guardrails/<domain>/<rule>.md` files, which *are* per-file units because they are loaded selectively, not always-together.
- `tools/schema-map.json`'s existing `guardrails/core.md → base` mapping is therefore correct and stays; `guardrails/**/*.md → guardrail` covers future domain rules.

## Rationale

- **Individual addressability buys nothing for core rules.** The reason units are individually addressable is to avoid loading unrelated things together. Core guardrails are Tier G — *always* loaded together, every session, by definition. Per-rule addressing would add structure with no retrieval benefit.
- **No Constitution churn, no premature RFC.** `core.md` stays the single Tier G file exactly as `kernel/README.md` and `kernel/boot/README.md` already specify. The alternative (a `guardrails/core/` directory) would require editing those Kernel documents — a Constitution-tier change needing a full RFC, and the RFC process itself isn't exercised until M4. Avoiding that is a real, not cosmetic, saving.
- **Impact analysis still works correctly.** `aios impact` flags every Agent on any `guardrails/*` change (a guardrail affects all dispatch). Set-level versioning of `core.md` matches this exactly — there is no case where you'd want to flag agents for "core rule 3 changed" but not "core rule 4 changed," because all core rules bind all agents.
- **Respects the stdlib decision.** Keeps frontmatter within the flat subset; no pressure to adopt a YAML library.

## Alternatives Rejected

| Alternative | Why rejected |
|---|---|
| Each core rule its own file under `guardrails/core/` | Requires Tier G to load a directory → editing Kernel spec → premature RFC (M4 territory) for no retrieval benefit, since core rules always load together anyway. |
| Per-rule metadata as nested YAML in `core.md` frontmatter | Breaks the stdlib flat-frontmatter subset; would force adopting a YAML library, contradicting the M2 dependency decision. |
| Drop `guardrail.schema.json` entirely, validate everything as base | Loses the machine-readable `checkpoint`/`enforcement` model for *domain* guardrails, where per-file granularity genuinely helps. Keeping it reserved for domains costs nothing now. |

## Consequences

- M3 authors core rules as sections in `core.md`, bumping its single version.
- The first domain guardrail (M5-era) is the first real use of `guardrail.schema.json`; if that reveals the per-file model needs adjustment, it's a new decision then — this one governs core only.
- This resolves the M1/M2 open question; future references to "the guardrail granularity question" resolve here.

## Related Documents
[`.ai/guardrails/README.md`](../guardrails/README.md) · [`.ai/schema/README.md`](../schema/README.md) · [Decision 0001](0001-aios-bootstrap-roadmap.md) · [milestones/M1](../milestones/M1-schema-and-skeleton.md)
