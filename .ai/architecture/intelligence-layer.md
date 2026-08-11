# Intelligence Layer — Architecture Overview

> The canonical entry point for understanding the Intelligence Layer.
> This document connects the existing ADRs, Standards, and Playbooks
> into a coherent map. It introduces no new decisions.

---

## 1. Purpose

### Why the Intelligence Layer exists

The Intelligence Layer is the bounded context that owns **how to find, talk
to, and execute against LLM providers and models**. It is the seam between
the MCP server's request surface and the heterogeneous set of provider SDKs
and HTTP APIs that actually generate completions.

Without this layer, every route that needed an LLM would import a specific
provider SDK, every configuration change would require a code change, and
N providers would mean N incompatible code paths. The Intelligence Layer
exists to enforce a single abstraction over all of them.

### Scope

- Provider discovery, registration, and lifecycle (Ollama, OpenAI-compatible
  endpoints, AWS Bedrock, future providers).
- Model discovery, capability indexing, and routing selection.
- Capability-based interface contracts — chat, embedding, vision, speech,
  rerank, health.
- Self-hosted-first routing policy encoded as configuration.
- Public exception hierarchy for LLM failures.

### Non-goals

- **Not a Domain layer.** It governs mechanics of provider interaction; it
  does not encode product business meaning. The Domain layer does not import
  Intelligence; Intelligence does not crawl up the layering.
- **Not part of the MCP tool surface.** Tools consume the layer through the
  `LLMService` public interface; tools do not reach into adapter code.
- **Not a wrapper over a single provider.** The abstraction allows the same
  code to talk to N providers and the same provider to be retried,
  load-balanced, and health-checked through one mechanism.
- **Not a persistence layer.** Runtime state (health, circuit-breaker state,
  request counters) lives in memory and is reset on restart. Registries are
  YAML-as-source-of-truth and are never written back to at runtime.

---

## 2. Bounded Contexts

The Intelligence Layer is decomposed into five bounded contexts. Each has a
single responsibility and a unidirectional dependency relationship to the
others.

| Context | Responsibility | Phase |
|---|---|---|
| **Registry** | Static metadata for providers and models; loading, validation, catalog construction | Implemented |
| **Provider Runtime** | Provider instance construction, lifecycle, and singleton ownership | Implemented |
| **Inference** | Request routing, request orchestration, and provider invocation | Skeleton |
| **Conversation** | Message history, multi-turn state, audit, and export control | Deferred |
| **Health** | Provider availability monitoring, circuit breakers, observability | Deferred |

### Registry

The innermost context. Owns the immutable records (`ProviderRecord`,
`ModelRecord`), the loaders, the validator, and the `ModelCatalog` query
layer. The catalog is **not storage** — it is an in-memory view rebuilt from
the validated records at startup.

### Provider Runtime

Sits one layer out from Registry. Owns `ProviderFactory` (constructor
registry), `ProviderManager` (singleton owner, lifecycle), and the concrete
adapters. The catalog is the single source of truth for what is initialised;
no other bootstrap path exists.

### Inference

The outer context and the only public entry point. Composes Registry and
Provider Runtime. Owns `LLMService`, `Router`, `RoutingStrategy`, and
`RoutingPolicy`. The MCP server's application code touches this context only.

### Conversation

A separate bounded context because conversation carries a different
ownership model (persistence, audit, redaction) than Inference. Deferred
to a future phase. The package exists so the layering is visible; the
implementation is not present.

### Health

A separate bounded context for monitoring provider availability, circuit
breakers, and the cascade-containment protocol. Deferred. Same visibility-
without-implementation principle as Conversation.

---

## 3. Dependency Direction

### Clean Architecture

The layer is organised as four concentric rings. A dependency arrow points
**inward only**.

- **Entities** (innermost): provider records, model records, capability
  types, deployment types. Pure value objects.
- **Use Cases** (next ring): loaders, validators, catalog builder, router,
  service interface. Orchestration of the entities.
- **Interface Adapters** (next ring): provider port interfaces, factory,
  manager.
- **Frameworks & Drivers** (outermost): concrete provider adapters
  (Ollama, OpenAI-compatible, Bedrock). This is the only ring that imports
  provider SDKs.

### Hexagonal Architecture (Ports & Adapters)

The capability surface is defined by **ports** — capability interfaces that
provider implementations satisfy. The rest of the layer programs **only** to
the ports, never to a concrete provider. One port per capability
(`ChatCapable`, `EmbeddingCapable`, `VisionCapable`, `SpeechCapable`,
`RerankCapable`, `HealthCheckable`), plus a small `BaseProvider` for the
interface every provider implements regardless of capability mix-in.

Ports are owned by the Intelligence Layer because they are LLM-specific
contracts. They do not belong in a platform-wide `core/` module.

### Allowed imports

| From | May import |
|---|---|
| Entities (records, types) | Nothing inside Intelligence |
| Loaders, Validator, Builder | Entities |
| Ports | Entities |
| ProviderFactory | Entities, Ports |
| ProviderManager, Adapters, BaseProviderRuntime | Entities, Ports, Registry (catalog) |
| Router, Strategies, Policies | Entities, Ports, Registry (catalog) |
| LLMService | Router, ProviderManager, Catalog |
| Health context | Entities, Ports, Registry, Provider Runtime |
| Conversation context | Entities, LLMService |

### Forbidden imports

These arrows MUST NOT exist:

- Registry → Provider Runtime, Inference, Conversation, Health.
- Ports → Provider Runtime, Inference, Registry loaders.
- Providers → Inference, Runtime.
- Adapters → other adapters, Registry loaders, factories.
- Inference → Conversation context.
- Anything inside Intelligence → MCP server, tools, or platform `core/`.

A Registry change MUST NOT require an Inference change to validate. The
cycle is the same layering violation the broader project records for the
domain rule; it is enforced here through package placement.

---

## 4. Startup Sequence

The bootstrap order is fixed and unidirectional. Each step produces input
for the next; no step depends on a later step.

1. **Configuration (YAML)** — registry files contain raw provider and model
   records. The catalog-builder standard and the provider/model registries'
   standards document the schema.
2. **`RegistryLoader`** — parses YAML into raw records and delegates to the
   specialised loaders.
3. **`ProviderLoader`** and **`ModelLoader`** — parse configuration data
   into typed records; emit load errors for syntax and type issues.
4. **`RegistryValidator`** — semantic validation; cross-references between
   models and providers; emits structured validation errors.
5. **`CatalogBuilder`** — orchestrates loading and validation; registers
   validated records into the in-memory `ModelCatalog`.
6. **`ModelCatalog.freeze()`** — the catalog becomes read-only.
7. **`RegistryRuntime`** — the process-lifetime owner of the frozen catalog.
8. **`ProviderFactory`** — empty constructor registry. `register_all_adapters()`
   registers OllamaAdapter, OpenAICompatibleAdapter, BedrockAdapter along
   with their declared `Capability` sets.
9. **`ProviderManager`** — owns singleton instances. `await manager.start()`
   creates each provider via the factory, validates configuration, and
   marks each provider ready. Failures at this step are fail-fast: every
   failing provider is reported and startup aborts.
10. **`LLMService`** — constructed with `ProviderManager`, `ModelCatalog`,
    optional `Router`, optional default `RoutingStrategy`.

After this sequence, the application is in steady state. No component is
constructed per request; all are process-lifetime.

---

## 5. Request Flow

A request moves through the layer in the order below. The same sequence
applies to `chat`, `embed`, `vision`, and other capability-typed
operations.

1. **Client** — the MCP route or service consumer calls
   `LLMService.chat(messages, model=..., provider=..., **options)`.
2. **`LLMService`** — accepts the request. Currently the public surface
   delegates; routing and execution are described below.
3. **`Router`** — given a capability and optional model/provider hint,
   produces a `RoutingDecision` (provider_id, model_id).
4. **`RoutingStrategy`** — the router's pluggable selector. The strategy
   queries the catalog for candidates filtered by capability, then sorts
   by `DeploymentPreference` (self-hosted > local > proxy > cloud) and
   model priority. Future strategies (cost-aware, health-aware) plug in
   here without changing the router.
5. **`RoutingPolicy`** — cross-cutting middleware around the strategy call
   (rate limit, retry, cache, metrics). The policy is the place for
   behavioural concerns; the strategy is the place for selection.
6. **`ProviderManager`** — looks up the singleton for the chosen
   `provider_id`. Same instance is returned on every lookup; the provider
   SDK's connection pool and internal state are preserved across requests.
7. **Provider Adapter** — implements the capability port. Reads its
   configuration from the `ProviderRecord`, forwards the request through
   its provider-specific client.
8. **Provider API** — the network call to the provider's chat / embed /
   vision endpoint.

Failure boundaries:
- Adapter-level failures are translated into the Intelligence-layer
  exception hierarchy (`LLMProviderError`, `LLMAuthenticationError`,
  `LLMRateLimitedError`, `LLMTimeoutError`, `LLMUnavailableError`,
  `LLMConfigurationError`, `LLMValidationError`, `LLMModelNotFoundError`)
  before any layer above sees them.
- Service-level failures from routing (no candidate, no provider started)
  are surfaced as `LLMProviderError` or `LLMModelNotFoundError`.

---

## 6. Extension Points

### Add provider

1. Subclass `BaseProviderRuntime` and the relevant capability ports.
2. Implement `initialize()`, `validate_configuration()`, `start()`,
   `close()`.
3. Register the constructor and declared capabilities in
   `register_all_adapters()` so the factory recognises the provider type.
4. Add a `ProviderRecord` and matching `ModelRecord`s to the YAML
   configuration.

Governing playbook: [add-provider](../playbooks/intelligence/add-provider.md)

### Add capability

Capability addition follows the closed-set rule: a new capability is a
triple of three coordinated changes.

1. New `Capability` enum member in `registry/types/capability.py`.
2. New port file (e.g. `ports/function_calling.py`) inheriting the
   capability contract pattern.
3. Provider implementations of the new port (one or more adapters).

Governing playbook: [add-capability](../playbooks/intelligence/add-capability.md)

### Add routing strategy

1. Subclass `RoutingStrategy` in `inference/strategies/`.
2. Implement `name`, `select(candidates, context)`, and
   `get_candidates(context, **kwargs)`.
3. Wire the strategy at the composition root when constructing `Router`
   or `LLMService`.

Governing playbook: [add-routing-strategy](../playbooks/intelligence/add-routing-strategy.md)

### Add policy

Policies are composition-root concerns, not router concerns. Wire a
`RoutingPolicy` at `LLMService` construction (rate limit, retry, cache,
metrics). The policy wraps the strategy call; conflation is forbidden.

---

## 7. Documentation Map

### Bounded contexts and their governing ADRs

| Context | Governing ADRs |
|---|---|
| Intelligence Layer (overall shape) | [0013 — Intelligence Layer Architecture](../decisions/0013-intelligence-layer-architecture.md) |
| Registry (provider + model + catalog) | [0014 — Provider & Routing Architecture](../decisions/0014-provider-and-routing-architecture.md) |
| Provider Runtime (lifecycle, ports) | [0014 — Provider & Routing Architecture](../decisions/0014-provider-and-routing-architecture.md) |
| Inference (router, strategy, policy) | [0014](../decisions/0014-provider-and-routing-architecture.md), [0016 — Inference Policy](../decisions/0016-inference-policy.md) |
| Health | [0015 — Inference Runtime](../decisions/0015-inference-runtime.md) |
| Conversation | (deferred — no dedicated ADR yet) |

### Standards

Standards capture the **how** of each implementation. This overview links
the contexts to the standards that govern them.

| Context / concern | Standard |
|---|---|
| Overall layer constraints | [backend-layering](../standards/architecture/backend-layering.md) |
| Package design rules | [service-package-design](../standards/architecture/service-package-design.md) |
| Registry runtime | [registry-runtime](../standards/architecture/registry-runtime.md) |
| Provider records | [provider-registry](../standards/architecture/provider-registry.md) |
| Model records | [model-registry](../standards/architecture/model-registry.md) |
| Provider lifecycle | [provider-lifecycle](../standards/architecture/provider-lifecycle.md) |
| Routing | [routing](../standards/architecture/routing.md) |
| Conversation (later) | [conversation](../standards/architecture/conversation.md) |
| Health (later) | [health-monitor](../standards/architecture/health-monitor.md) |

### Playbooks

Playbooks are the **how to add X** procedures. Each extension point in
§6 cites its playbook; the full set is:

- [add-provider](../playbooks/intelligence/add-provider.md)
- [add-model](../playbooks/intelligence/add-model.md)
- [add-capability](../playbooks/intelligence/add-capability.md)
- [add-routing-strategy](../playbooks/intelligence/add-routing-strategy.md)
- [migrate-registry](../playbooks/intelligence/migrate-registry.md)

---

## 8. Current Phase Status

### Implemented

- All five bounded contexts exist as packages. Registry, Provider Runtime,
  and Inference contexts have real implementations; Conversation and Health
  contexts exist as package stubs only.
- `RegistryLoader`, `ProviderLoader`, `ModelLoader`, `RegistryValidator`,
  and `CatalogBuilder` parse and validate YAML, construct the in-memory
  `ModelCatalog`, and freeze the catalog at the end of the sequence.
- `RegistryRuntime` owns the frozen catalog for the process lifetime.
- Capability types (`Capability`), deployment types (`DeploymentType`),
  provider types (`ProviderType`), and model types (`ModelType`) are
  defined as immutable enums.
- The six capability ports (`ChatCapable`, `EmbeddingCapable`,
  `VisionCapable`, `SpeechCapable`, `RerankCapable`, `HealthCheckable`)
  are defined; `BaseProvider` is the common façade.
- `ProviderFactory` registers constructors and capability sets.
- `ProviderManager` owns provider instances (singleton per `provider_id`),
  validates configuration at startup, and fails fast on any provider
  failure.
- Three adapters are implemented: `OllamaAdapter`,
  `OpenAICompatibleAdapter`, `BedrockAdapter`. All implement
  `BaseProviderRuntime` (lifecycle contract) and the chat + embedding
  capability ports. Inference methods are placeholders.
- The exception hierarchy covers configuration, provider, authentication,
  rate-limit, timeout, unavailable, validation, and model-not-found
  errors. Adapter-level SDK exceptions are chained into this hierarchy.
- The stable public surface is defined in `app/intelligence/__init__.py`:
  `LLMService`, `RegistryRuntime`, `ProviderFactory`, `ProviderManager`,
  `LLMError`.

### Intentionally deferred to Phase 4 and beyond

- **Inference execution.** `LLMService.chat()`, `chat_stream()`, `embed()`,
  `vision()` are placeholder methods that raise `NotImplementedError`.
  The router selects; the adapter receives a request; the request is not
  yet sent over the network.
- **HTTP client integration.** Adapters accept configuration and resolve
  environment variables but do not yet construct and use a real HTTP
  client.
- **Streaming.** `chat_stream()` is a placeholder; no streaming response
  pathway is in place.
- **Routing runtime.** `Router.route()` and `RoutingStrategy.select()`
  are placeholder returns. The selection algorithm is defined; the
  execution is not.
- **Health Runtime.** No health cache, no circuit breaker, no scheduled
  probe. The `HealthCheckable` port exists; no consumer calls it.
- **Conversation.** No message history, no persistence, no state
  machine. The bounded context exists as a package stub.
- **Cost-aware, privacy-aware, health-aware routing strategies.** Only
  the Priority Strategy (deployment preference + model priority) is
  scoped. Future strategies plug in at the composition root.
- **Composite routing policies.** Rate-limit, retry, cache, and metrics
  policies are individual placeholders; a `CompositePolicy` chain is
  future work.
- **Hot-reload.** Registry YAML changes do not reconcile mid-process.
  The hot-reload protocol is a future consideration; not part of any
  current ADR.

### What this document does NOT contain

This overview does not restate the rationale recorded in the ADRs, the
schema details recorded in the Standards, or the step-by-step extension
procedures recorded in the Playbooks. Each of those documents is the
single source of truth for its concern; this overview only connects them.
