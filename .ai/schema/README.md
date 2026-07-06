# Schema

The canonical, machine-readable definition of what every AIOS unit's frontmatter must contain. One base schema plus one extension per unit type. Created in Roadmap M1 ([Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)); consumed by the M2 schema-validator script.

## This Is Not an AIOS Module

Like [milestones/](../milestones/README.md), this is infrastructure, not a module: no Agent-facing contract, not Router-addressable, absent from the [Module Index](../README.md#module-index). It is the *shape* every module's units conform to, referenced by every module contract — not itself a unit-bearing module. Creating it is implementation of already-frozen v1.0 conventions (the frontmatter fields were fixed during the Namespace/Dependency/Versioning and Governance design), so it required no new RFC.

## The Operating Principle It Serves

> Repository is responsible for truth. Automation is responsible for determinism.

Frontmatter is where a unit's machine-checkable truth lives — its address, version, dependencies, lifecycle state. Because it's declared as data (not prose), Automation can validate it, generate indexes from it, compute reverse-dependencies from it, and run Impact Analysis on it — none of which requires an AI to read and interpret. Prose belongs in the markdown body; anything a script must act on belongs in frontmatter.

## Files

| Schema | Applies to | Key added fields |
|---|---|---|
| [base.schema.json](base.schema.json) | Every unit, every module | `id`, `title`, `version`, `status`, `owner`, `category`, `depends_on`, `validated_against`, `supersedes` |
| [standard.schema.json](standard.schema.json) | `standards/` units | `scope`, `applies_to`, `severity_default`, `enforced_by` |
| [agent.schema.json](agent.schema.json) | `agents/<domain>/` units | `domain`, `decision_authority`, `knowledge_sources`, `skills_used`, `standards_enforced`, … |
| [guardrail.schema.json](guardrail.schema.json) | `guardrails/` units | `scope`, `checkpoint`, `enforcement` (and `status` without `Stale`) |

Extension schemas exist only for the three unit types the M3 vertical slice (Backend) will author — Standard, Agent, Guardrail — per [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md)'s "don't build ahead of need." The base schema already applies to *every* unit type; the remaining extensions (Knowledge, Skill, Workflow, Template, Playbook, …) are authored when their module first gets a real unit, following the pattern below.

## The `id` = path Rule

A unit's `id` MUST equal its file path under `.ai/` without the extension. A file at `standards/security/no-plaintext-secrets.md` has `id: standards/security/no-plaintext-secrets`. This is what makes the namespace a checkable contract rather than a convention: the M2 link-checker can confirm every `depends_on`/`validated_against`/reference resolves to a real file, and a rename that breaks a reference fails a check instead of silently rotting.

## Authoring a New Extension Schema (pattern for future module types)

1. Create `schema/<type>.schema.json` with `"allOf": [{ "$ref": "base.schema.json" }]`.
2. Constrain `category` to that module's declared category set (the enum in its README).
3. Add only *machine-actionable* fields — things a script or the Router consumes. Prose contract fields stay in the markdown body; don't duplicate them here.
4. Register the new schema in the Files table above.
5. Adding an extension schema for a not-yet-touched module type is itself subject to "don't build ahead of need" — do it when the first real unit of that type is authored, not before.

## How M2 Will Consume This

The M2 schema-validator resolves each unit's module → picks the matching `<type>.schema.json` (falling back to `base.schema.json` for types without an extension yet) → validates the unit's parsed YAML frontmatter against it. Standard JSON-Schema validation (Python `jsonschema`, matching the existing `.ai/intelligence/scripts/` Python precedent). This file set is the data; the validator is the code — authored in separate milestones on purpose.

## Lifecycle

The schema set is Constitution-adjacent: a change to `base.schema.json` affects every unit in the system, so it carries the same blast radius as a Kernel/Router change and goes through a full [RFC](../governance/README.md#rfc-process). Adding a new *extension* schema for a new module type is additive and does not require an RFC (it constrains only that module's own units).
