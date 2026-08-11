# Playbook — Add a Provider

> Operational guide for adding a new LLM provider to the Intelligence Layer. Authority: [Decision 0014](../../decisions/0014-provider-and-routing-architecture.md). Standards: [provider-registry](../../standards/architecture/provider-registry.md), [provider-lifecycle](../../standards/architecture/provider-lifecycle.md), [routing](../../standards/architecture/routing.md).

## Prerequisites

- [ ] The provider has an SDK or HTTP API that exposes chat, embedding, vision, speech, or rerank capability.
- [ ] The provider's SDK version is pinned in the project's dependency list.
- [ ] The `provider_id` is unique — no other provider uses it.
- [ ] The provider's `provider_type` exists in the `ProviderType` enum (or is added as part of this change).
- [ ] The provider's `DeploymentType` is decided (cloud, self-hosted, proxy, local).
- [ ] The provider's credentials are available in the deployment environment.

## Procedure

### Step 1 — Add the provider record to `providers.yaml`

**Governed by:** [provider-registry](../../standards/architecture/provider-registry.md) PR-1, PR-4, PR-6.

- Add a single entry under `providers:` with the chosen `provider_id`.
- Set `provider_type` to the enum value.
- Set `deployment` to the chosen deployment type.
- Set `enabled: true` if the provider is active in this deployment.
- Set `priority` to influence the routing strategy's preference.
- Set `auth` and `connection` to the provider-specific configuration.

**Check:** The YAML parses cleanly via the loader. The validator accepts the record.

### Step 2 — Implement the provider adapter

**Governed by:** [provider-lifecycle](../../standards/architecture/provider-lifecycle.md) PL-8, base port requirement.

- Create a new module under `mcp-server/app/intelligence/providers/<provider_id>/`.
- The module implements `BaseProvider` and the relevant capability ports (`ChatCapable`, `EmbeddingCapable`, …).
- The module imports the provider SDK **only** inside the adapter module.
- The constructor accepts a `ProviderRecord` and stores the connection / auth configuration.
- The `validate_configuration()` method performs a structural check (and a cheap probe if available).

**Check:** The adapter compiles; the SDK import is restricted to the adapter module.

### Step 3 — Translate SDK exceptions to the LLM exception hierarchy

**Governed by:** [routing](../../standards/architecture/routing.md) RT-6.

- Every method that calls the provider SDK MUST catch SDK exceptions and raise the corresponding `LLMException` subclass.
- The mapping table is documented in the standard; the adapter follows it.

**Check:** No raw SDK exception is re-raised. The routing layer never sees a vendor-specific exception.

### Step 4 — Register the constructor and capabilities in `ProviderFactory`

**Governed by:** [provider-lifecycle](../../standards/architecture/provider-lifecycle.md) PL-5, PL-8.

- Register the constructor at the composition root: `factory.register(provider_type.value, ProviderClass)`.
- Register the capabilities: `factory.register_capabilities(provider_type.value, frozenset({Capability.CHAT, …}))`.

**Check:** The factory knows the provider's type, constructor, and declared capabilities.

### Step 5 — Update the catalog

**Governed by:** [registry-runtime](../../standards/architecture/registry-runtime.md) RR-1, RR-3.

- The catalog is rebuilt automatically at startup. No manual change is required.
- For hot-reload (when implemented), the registry hot-reload triggers a catalog rebuild.

**Check:** Restart the application; the catalog lists the new provider.

### Step 6 — Add at least one model for the provider

**Governed by:** [model-registry](../../standards/architecture/model-registry.md) MR-3.

- Add at least one model record to `models.yaml` referencing the new `provider_id`.
- Or use the [add-model playbook](add-model.md) as a follow-up.

**Check:** A request that requires the provider's capability can be routed.

### Step 7 — Update the composition root

**Governed by:** [provider-lifecycle](../../standards/architecture/provider-lifecycle.md) PL-1, [service-package-design](../../standards/architecture/service-package-design.md) R4 / E1 (Composition Root Exception).

- Wire the provider's constructor and capability registration in `bootstrap.py`.
- The startup must construct the provider; the validation must succeed.

**Check:** The application starts. The provider instance is in the manager's map.

## Validation Checklist

- [ ] `providers.yaml` parses without errors.
- [ ] The validator reports no `ValidationError` for the new record.
- [ ] The adapter's `validate_configuration()` returns no error.
- [ ] The factory lists the provider's `provider_type` and capabilities.
- [ ] The catalog lists the provider under the expected `provider_id`.
- [ ] The manager reports the provider as `healthy` (or as `unhealthy` if the validation fails).
- [ ] `aios check` passes.
- [ ] `aios arch` reports no dependency violation.

## Common Mistakes

- **Importing the provider SDK outside the adapter module.** The SDK import MUST be isolated. The factory, manager, and routing layer MUST NOT import SDKs.
- **Returning a raw SDK exception.** The adapter translates; the routing layer does not see vendor exceptions.
- **Defining a `ProviderRecord` in code instead of YAML.** Two definitions is the same drift class [Decision 0008](../../decisions/0008-domain-ubiquitous-language.md) ¶ 2.1 warns against.
- **Forgetting to register capabilities.** The factory's constructor registration is not enough; the capabilities registration is what the routing candidate selection uses.
- **Constructing the provider per request.** The provider is constructed once at startup; per-request construction is a layering violation.
- **Leaving the provider's `enabled` flag at `false` unintentionally.** The provider is in the catalog but not routable.

## Required Tests

- **Unit tests for the provider adapter.** The adapter's methods against a mocked SDK; the exception translation; the `validate_configuration()` success and failure paths.
- **Unit tests for the factory registration.** The factory knows the provider's type, constructor, and capabilities.
- **Integration tests for the catalog.** The catalog includes the new provider after a registry load.
- **Integration tests for the lifecycle.** The manager constructs the provider at startup; the singleton invariant holds.

## Files Typically Modified

- `mcp-server/app/intelligence/providers/<provider_id>/__init__.py` (new)
- `mcp-server/app/intelligence/providers/<provider_id>/<provider_id>_client.py` (new)
- `mcp-server/app/intelligence/providers/<provider_id>/config.py` (new, optional)
- `mcp-server/app/intelligence/providers/<provider_id>/tests/` (new)
- `mcp-server/config/providers.yaml`
- `mcp-server/app/intelligence/bootstrap.py` (registration in the factory)
- `mcp-server/app/intelligence/registry/providers.yaml` (or wherever the registry YAML lives)
- `mcp-server/requirements.txt` (if the SDK is not already pinned)

## ADR References

- [Decision 0013](../../decisions/0013-intelligence-layer-architecture.md) — the Intelligence Layer bounded contexts
- [Decision 0014](../../decisions/0014-provider-and-routing-architecture.md) — the Provider Registry, Factory, and Manager architecture
- [Decision 0016](../../decisions/0016-inference-policy.md) — the routing policy that includes the new provider
