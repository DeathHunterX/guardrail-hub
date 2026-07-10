# Guardrail Hub — Architecture Documentation

This directory holds design/architecture documentation for Guardrail Hub subsystems. It moved here from `docs/` on 2026-07-10 so `docs/` is free for the Docusaurus site (MCP server + API reference docs).

## Convention

One subfolder per subsystem, e.g. `architecture/<subsystem>/`. Each subfolder owns its own `README.md` as the entry point and links out to `.ai/` (guardrails, standards, decisions, intelligence) rather than restating it — the same pattern `architecture/chatops/README.md` follows.

No placeholder folders are created ahead of need — per the repo's existing anti-pattern rule against empty scaffold folders (see [`FOLDER-STRUCTURE-REFACTOR.md`](chatops/FOLDER-STRUCTURE-REFACTOR.md)), a subsystem gets a folder here when its design doc set is actually written, not before.

## Current subsystems

| Subfolder | Status | Entry point |
|---|---|---|
| [`chatops/`](chatops/README.md) | Design (not yet built) | [`chatops/README.md`](chatops/README.md) — related: [ADR 0004](../.ai/decisions/0004-chatops-platform-architecture.md) |

Planned future entries (not yet created): `mcp/`, `platform/`, `security/`, `integrations/` — add a subfolder here as each subsystem's architecture is actually designed.
