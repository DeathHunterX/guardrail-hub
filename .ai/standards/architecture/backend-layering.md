---
id: standards/architecture/backend-layering
title: Backend Directory-by-Responsibility Layering
version: 1.0.0
status: Active
owner: backend-owner
category: architecture
scope: mcp-server backend module organization
severity_default: blocking
applies_to: [mcp-server/app/**]
enforced_by: []
depends_on: []
validated_against: []
---

# Backend Directory-by-Responsibility Layering

> Distilled from observed conventions in [intelligence/conventions.md](../../intelligence/conventions.md) and [intelligence/module-map.md](../../intelligence/module-map.md). Status `Review` pending M4 activation.

## Scope
Applies to all code under `mcp-server/app/`. Does not govern `web/`, `mobile/`, or non-code assets.

## Rule Definitions
- **R1** Code is organized by architectural role, not by feature: `routers/`, `services/`, `integrations/`, `dao/`, `schemas/`, `helpers/`, `constants/`, with `core/` as the shared base.
- **R2** Within `routers/`, `schemas/`, `services/`, sub-partition by audience (`public/`, `mcp/`, `internal/`) or by tool (`tools/<tool>/`).
- **R3** A new tool integration follows the ZAP layout exactly: `schemas/tools/<tool>/`, `services/tools/<tool>/`, `integrations/<tool>/`, `routers/mcp/<tool>_router.py`.
- **R4** Dependency direction is one-directional: `routers → services → integrations|dao`; lower layers never import higher ones.

## Mandatory Rules
R1, R3, R4 are Mandatory (blocking). R2 is Mandatory where an audience/tool split already exists in the touched area.

## Optional Recommendations
Co-locate a tool's constants under `constants/` rather than inlining magic values in the service.

## Exceptions
None. A genuinely new architectural role (not one of the listed layers) is a Decision-level change, not an ad-hoc new top-level folder.

## Anti-patterns
- Business logic placed directly in a `routers/` handler instead of a `services/` unit.
- A new tool's files scattered across the tree instead of following the `tools/<tool>/` layout (e.g. a JMeter client dropped in `helpers/` instead of `integrations/jmeter/`).
- A `dao/` module importing from `services/` (dependency inversion).

## Examples
The OWASP ZAP integration is the reference: `schemas/tools/owasp_zap/`, `services/tools/owasp_zap/`, `integrations/owasp_zap/`, `routers/mcp/owasp_zap_router.py` — see [intelligence/module-map.md](../../intelligence/module-map.md).
