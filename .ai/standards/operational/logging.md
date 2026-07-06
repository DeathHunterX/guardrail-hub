---
id: standards/operational/logging
title: Logging via MCPLogger
version: 1.0.0
status: Active
owner: backend-owner
category: operational
scope: all logging emitted by mcp-server
severity_default: blocking
applies_to: [mcp-server/app/**/*.py]
enforced_by: []
depends_on: []
validated_against: []
---

# Logging via MCPLogger

> Distilled from [intelligence/conventions.md](../../intelligence/conventions.md). Status `Review` pending M4 activation.

## Scope
All log emission in `mcp-server/app/`.

## Rule Definitions
- **R1** All logging goes through `MCPLogger` (`app/core/mcp_logger.py`) — the app's single logging mechanism.
- **R2** Do not call Python's stdlib `logging` module directly, nor `print()`, for operational logging.
- **R3** Never log a resolved secret, token, or credential (this is where operational logging meets core guardrail [G1](../../guardrails/core.md)).

## Mandatory Rules
R1–R3 are all Mandatory (blocking). R3 additionally inherits Core Guardrail G1 and can never be waived.

## Optional Recommendations
Include a stable operation identifier in log context so a scan run can be traced end-to-end.

## Exceptions
Third-party libraries emitting their own logs are out of scope; configure them at the app edge rather than replacing `MCPLogger` internally.

## Anti-patterns
- `import logging; logging.getLogger(__name__).info(...)` inside a service — bypasses `MCPLogger`.
- `print(scan_result)` for debugging left in a handler.
- Logging a request body that contains an auth token.

## Examples
`MCPLogger` in `mcp-server/app/core/mcp_logger.py` is the sole sanctioned logger — see [intelligence/module-map.md](../../intelligence/module-map.md).
