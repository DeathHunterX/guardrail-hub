# Add an Intelligence Provider

> **Draft working guide.** The Intelligence-specific ADRs and Standards named in earlier drafts were never authored, so this is not an Active Blueprint and grants no independent implementation authority. Use it with the Active Backend Standards and confirm every path against current source.

## Purpose

Describe the current extension points for a new LLM provider without reviving the removed split `providers.yaml`/`models.yaml` configuration.

## Current extension path

1. Add the provider kind to `app/intelligence/registry/types/provider.py` when it is genuinely new. Reuse an existing type for another deployment of the same protocol.
2. Implement an adapter under `app/intelligence/providers/adapters/`. It must implement `BaseProviderRuntime` and only the capability ports it actually supports.
3. Translate vendor/HTTP/SDK failures into the shared exception hierarchy in `app/intelligence/exceptions.py`; do not leak vendor exceptions past the adapter.
4. Register the constructor and declared capabilities in `providers/adapters/__init__.py::register_all_adapters`.
5. Add provider and model records to the single canonical configuration, `mcp-server/config/llm.yaml`. Provider capabilities are derived from its models by the loader.
6. Keep secrets out of `llm.yaml`. Declare the authentication mechanism/reference and deliver the value through the credential backend/store selected at startup.
7. Add tests for loader/validator behavior, factory registration, adapter lifecycle/capabilities, real request translation at the HTTP/SDK boundary, and ProviderManager startup/shutdown behavior.
8. Run the relevant backend tests and `python .ai/tools/aios.py check`.

## Required invariants

- `provider_id` is a unique logical deployment identifier; provider type identifies the adapter protocol/vendor family.
- `model_id` is Guardrail Hub's logical routing identifier; `deployment_name` is the provider-facing identifier.
- Declared capabilities must match methods actually implemented by the adapter.
- Disabled providers do not require credentials at startup.
- Secret values never appear in registry configuration, logs, exceptions, fixtures or committed environment files.
- Concrete adapter wiring remains in the provider factory/composition path, not in HTTP or MCP routers.
- Adding one provider must not require changing unrelated adapters or inference consumers.

## Validation checklist

- [ ] Unified `llm.yaml` loads and validates.
- [ ] The provider factory creates the adapter for the new provider type.
- [ ] Provider startup resolves credentials without exposing their values.
- [ ] Every advertised capability succeeds through the shared port contract.
- [ ] Authentication, timeout, unavailable, validation and provider failures map to shared exceptions.
- [ ] Existing provider and routing tests remain green.
- [ ] Intelligence maps are re-reviewed and their drift baselines updated if their declared sources changed.

## Governance gap

Before promoting this file to an Active Blueprint, author and ratify the provider-registry/lifecycle/routing rules it relies on, give the unit valid Blueprint frontmatter, route it through Review, and replace this gap statement with real references. Planned ADR numbers 0013–0016 are not repository records and must not be cited as authority.

## Related Documents

[Intelligence architecture draft](../../architecture/intelligence-layer.md) · [service-package-design](../../standards/architecture/service-package-design.md) · [backend-layering](../../standards/architecture/backend-layering.md)

## Last Updated

2026-08-28 — aligned with unified `llm.yaml`, current adapter registration and credential delivery.
