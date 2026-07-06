---
id: standards/coding/backend-naming
title: Backend Naming Conventions
version: 1.0.0
status: Active
owner: backend-owner
category: coding
scope: Python identifier and file naming in mcp-server
severity_default: blocking
applies_to: [mcp-server/app/**/*.py]
enforced_by: []
depends_on: []
validated_against: []
---

# Backend Naming Conventions

> Distilled from [intelligence/conventions.md](../../intelligence/conventions.md). Status `Review` pending M4 activation.

## Scope
Python files and identifiers under `mcp-server/app/`.

## Rule Definitions
- **R1** File names are `snake_case` (`owasp_zap_router.py`, `api_scanner.py`).
- **R2** Class names are `PascalCase`.
- **R3** Tool-specific classes use `<Tool><Role>` (`ZapApiScanService`, `ZapClient`, `OwaspZapPool`); generic infrastructure uses `<Role>` (`PostgresDAO`, `Settings`, `MCPLogger`).
- **R4** Tool-specific Pydantic models are prefixed with the tool name (`ZapApiTarget`, `ZapScanResult`, `ZapInteractiveScanRequest`).

## Mandatory Rules
R1–R4 are all Mandatory (blocking).

## Optional Recommendations
Prefer full words over abbreviations except for established domain acronyms (ZAP, MCP, DAO).

## Exceptions
Vendored/generated code (e.g. third-party SDK stubs) is exempt — it is not hand-authored in this repo.

## Anti-patterns
- A file named `apiScanner.py` or `APIScanner.py` (not snake_case).
- A ZAP-specific model named `ScanResult` instead of `ZapScanResult`, colliding with a future tool's result type.
- A generic class force-fitted with a tool prefix (`ZapSettings` when it is really the app-wide `Settings`).

## Examples
The ZAP schemas under `mcp-server/app/schemas/tools/owasp_zap/` (`ZapApiTarget`, `ZapScanResult`, …) are the reference pattern — see [intelligence/conventions.md](../../intelligence/conventions.md).
