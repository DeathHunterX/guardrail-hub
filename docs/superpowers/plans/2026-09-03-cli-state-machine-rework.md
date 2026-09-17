# Guardrail Hub CLI State-Machine Rework Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with tests before implementation. No commit is authorized for this work.

**Goal:** Replace the linear credential bootstrap command with the approved setup state machine and safe configuration commands.

**Architecture:** Keep provider topology in `llm.yaml` behind `config`; keep setup scoped to existing records, credential storage, and provider readiness. Extend the existing setup package with small state/result types, use the registry loader/builder for semantic validation, and create one adapter at a time for connection probes.

**Tech Stack:** Python 3.12, argparse, unittest, PyYAML, httpx, boto3.

**Spec:** User-approved CLI contract in this task.

## Global Constraints

- Never accept, render, log, persist in YAML, or pass an API key through argv.
- Preserve the current CredentialStore, Windows Credential Manager, Compose host provisioner, and read-only runtime backends.
- Setup never changes provider/model topology or routing priority.
- `config apply` is interactive-only and atomically replaces only the canonical `llm.yaml` after strict and semantic validation.

### Task 1: Establish shared configuration validation and strict candidate validation

**Files:** `mcp-server/app/intelligence/registry/loaders/llm_config_loader.py`, new focused CLI/config tests.

- [ ] Add failing tests proving unknown fields and literal `auth.api_key` are rejected for candidate validation.
- [ ] Implement a small allow-list validation layer for the supported YAML structure.
- [ ] Run the focused loader tests.

### Task 2: Add provider inspection and connection testing

**Files:** `mcp-server/app/intelligence/setup/*`, provider adapter modules, setup tests.

- [ ] Add failing tests for secret-free credential/connection status and candidate-before-persist behavior.
- [ ] Add a provider-scoped tester that uses factory → attach credential → initialize → validate → start → probe → close.
- [ ] Implement inexpensive probes for Ollama and OpenAI-compatible adapters and an explicit unsupported result where no reliable probe exists.
- [ ] Run focused setup/provider tests.

### Task 3: Replace the CLI parser and implement config commands

**Files:** `mcp-server/app/cli.py`, new config/CLI tests.

- [ ] Add failing parser and config command tests.
- [ ] Implement the approved parser, safe `show`, strict `validate`, semantic diff, confirmation, and atomic `apply`.
- [ ] Run focused CLI/config tests.

### Task 4: Implement interactive setup state machine and environment detection

**Files:** `mcp-server/app/cli.py`, `mcp-server/app/intelligence/setup/*`, CLI tests.

- [ ] Add failing tests for dashboard filtering, shortcuts, no-change exit, changed-session rescan, and old-credential preservation.
- [ ] Implement environment selection, dashboard/menu state loop, and provider-scoped actions.
- [ ] Run focused CLI/setup tests.

### Task 5: Update operator documentation and verify regression coverage

**Files:** `mcp-server/README.md`, affected test files.

- [ ] Replace obsolete `--config`, `--target`, validation-only, and restart-oriented instructions.
- [ ] Run the intelligence/CLI suite, Phase 5 security suites, AIOS checks, and real no-secret smoke commands.
