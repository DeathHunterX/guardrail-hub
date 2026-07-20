---
id: standards/architecture/backend-layering
title: Backend Directory-by-Responsibility Layering
version: 1.1.0
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
- **R1** Code is organized by architectural role, not by feature: `routers/`, `services/`, `integrations/`, `dao/`, `schemas/`, `helpers/`, `constants/`, with `core/` as the shared base and **`domain/` as the innermost role** (added in 1.1.0 by [Decision 0007](../../decisions/0007-domain-layer-justification.md), the Decision-level change the Exceptions clause below reserves for a new role).
- **R2** Within `routers/`, `schemas/`, `services/`, sub-partition by audience (`public/`, `mcp/`, `internal/`) or by tool (`tools/<tool>/`). `domain/` is partitioned by **business capability** (`findings/`, `lifecycle/`), never by audience, tool, or Python construct.
- **R3** A new tool integration follows the ZAP layout exactly: `schemas/tools/<tool>/`, `services/tools/<tool>/`, `integrations/<tool>/`, `routers/mcp/<tool>_router.py`. A new tool never adds a `domain/tools/<tool>/` — tool-specific models are wire formats belonging to that tool's adapter ([domain-layer](domain-layer.md) D5).
- **R4** Dependency direction is one-directional: `routers → services → integrations|dao → domain`; lower layers never import higher ones. **`domain/` is innermost and imports nothing from `app/` outside itself**; every other layer, including infrastructure, may depend on it. The Domain half of this rule is stated in full and mechanically enforced by [domain-layer](domain-layer.md) D3.

## Mandatory Rules
R1, R3, R4 are Mandatory (blocking). R2 is Mandatory where an audience/tool split already exists in the touched area.

## Optional Recommendations
Co-locate a tool's constants under `constants/` rather than inlining magic values in the service.

## Exceptions
None. A genuinely new architectural role (not one of the listed layers) is a Decision-level change, not an ad-hoc new top-level folder. `domain/` was added by exactly that route ([Decision 0007](../../decisions/0007-domain-layer-justification.md)) and is the worked precedent for how a future role must be introduced: evidence of present duplication, an ADR, then a version bump here.

## Anti-patterns
- Business logic placed directly in a `routers/` handler instead of a `services/` unit.
- A new tool's files scattered across the tree instead of following the `tools/<tool>/` layout (e.g. a JMeter client dropped in `helpers/` instead of `integrations/jmeter/`).
- A `dao/` module importing from `services/` (dependency inversion).
- A `domain/` module importing from `services/`, `core/`, `schemas/`, `dao/`, or `integrations/` — the inversion R4 forbids at the innermost layer (caught by `aios arch`).
- Adding a new top-level role because a concept "doesn't fit anywhere", instead of raising a Decision.

## Examples
The OWASP ZAP integration is the reference: `schemas/tools/owasp_zap/`, `services/tools/owasp_zap/`, `integrations/owasp_zap/`, `routers/mcp/owasp_zap_router.py` — see [intelligence/module-map.md](../../intelligence/module-map.md).
