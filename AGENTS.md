# Guardrail Hub — AI entry point

This repository is governed by an **AI Operating System (AIOS)** under [`.ai/`](.ai/README.md). This file is the canonical, tool-agnostic adapter (the cross-vendor `AGENTS.md` standard); tool-specific files (`CLAUDE.md`, `.cursorrules`, …) import it rather than restating it. Do not duplicate AIOS content into tool configs — point to it.

## Which lane is your task? (decide first, load accordingly)

**Product Lane — ordinary code work in `mcp-server/`, `web/`, `mobile/` (most tasks).** Do *not* read `.ai/foundation/`, the full `.ai/kernel/`, `.ai/router/README.md`, or `.ai/agents/README.md` for these — that is meta-only. Instead:
1. Load [`.ai/guardrails/core.md`](.ai/guardrails/core.md) — Tier G, always, non-negotiable.
2. Load [`.ai/router/MANIFEST.md`](.ai/router/MANIFEST.md) — Tier 0. Classify the task into a Domain.
3. Follow that Domain's Router (e.g. [`.ai/agents/backend/ROUTER.md`](.ai/agents/backend/ROUTER.md)); load the Agent contract + the Standards it names (via each category's `INDEX.md`) — and nothing more.
4. Ground concrete facts in [`.ai/intelligence/`](.ai/intelligence/README.md) (what actually exists in the code today vs. what's only planned).

**Meta Lane — authoring/altering the AIOS itself** (a new Standard, Agent, guardrail, or `.ai/` structure): load the Constitution — [`.ai/foundation/`](.ai/foundation/vision.md), [`.ai/kernel/`](.ai/kernel/README.md), [`.ai/router/README.md`](.ai/router/README.md), [`.ai/agents/README.md`](.ai/agents/README.md).

**First contact — never seen this repo:** read [`.ai/foundation/bootstrap.md`](.ai/foundation/bootstrap.md) once, then use the lanes above.

## When sources conflict (priority, highest first)
Guardrails → Standards → Decisions → Intelligence/Knowledge → Examples → Playbooks/Templates → Memory. Specificity breaks ties within a rank; a safety-relevant gap escalates to a human rather than being guessed.

## Verify by tooling, never by hand
Every mechanical check runs through one CLI: `python .ai/tools/aios.py check` (validate + links + lint). See [`.ai/tools/README.md`](.ai/tools/README.md). Do not hand-verify what the CLI can check.

## Product reality
`mcp-server/` is the only substantially-built subsystem (a FastAPI MCP server exposing OWASP ZAP). `web/` is a marketing page; `mobile/`, `api/` are near-empty scaffolds. Treat README-described features as targets, not existing code — confirm against [`.ai/intelligence/system-overview.md`](.ai/intelligence/system-overview.md).
