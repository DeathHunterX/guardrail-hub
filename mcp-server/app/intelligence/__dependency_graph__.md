# Intelligence Layer — Dependency Graph

This document shows how the Intelligence Layer components are wired together at startup.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Startup Composition                                │
└─────────────────────────────────────────────────────────────────────────────┘

  Configuration (YAML)
         │
         ▼
  ┌──────────────────┐
  │  RegistryLoader  │ ◄─────────────────────────────┐
  └────────┬─────────┘                              │
           │                                        │
           ├────────────────────────────────────────┤
           │                                        │
           ▼                                        ▼
  ┌──────────────────┐                    ┌──────────────────┐
  │ ProviderLoader   │                    │   ModelLoader    │
  └────────┬─────────┘                    └────────┬─────────┘
           │                                        │
           ▼                                        ▼
  ┌──────────────────┐                    ┌──────────────────┐
  │ ProviderRecord[] │                    │   ModelRecord[]  │
  └────────┬─────────┘                    └────────┬─────────┘
           │                                        │
           └────────────────┬───────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │  RegistryValidator      │  (validates cross-references)
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │ CatalogBuilder          │
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │    ModelCatalog        │  (in-memory query layer)
              └───────────┬─────────────┘
                          │
                          ├────────────────────────────────────┐
                          │                                    │
                          ▼                                    ▼
              ┌─────────────────────┐              ┌─────────────────────┐
              │  ProviderFactory    │              │   ProviderManager   │
              │  (registrations)    │              │   (instances)       │
              └──────────┬──────────┘              └──────────┬──────────┘
                         │                                   │
                         │         ┌─────────────────────────┘
                         │         │
                         ▼         ▼
              ┌─────────────────────────────┐
              │      LLMService            │  (main service interface)
              └──────────┬──────────────────┘
                         │
                         ▼
              ┌─────────────────────────────┐
              │        Router              │  (routing decisions)
              └───────────────────────────┘
```

## Component Responsibilities

### RegistryLoader
- Loads provider and model data from configuration sources (YAML)
- Delegates parsing to ProviderLoader and ModelLoader
- Returns raw records and load errors

### ProviderLoader / ModelLoader
- Parse configuration data into records
- Perform syntax and type validation
- Return validated records or load errors

### RegistryValidator
- Semantic validation of records
- Cross-reference validation (models → providers)
- Produces ValidationError with entity, field, and message
- Can run independently of loading

### CatalogBuilder
- Orchestrates loading → validation → catalog construction
- Registers records into the in-memory ModelCatalog
- Returns both catalog and load result

### ModelCatalog
- **NOT storage** - in-memory query layer
- Built from validated ProviderRecord and ModelRecord
- Provides query methods: get_provider, list_providers, find_models_by_capability
- Maintains secondary indices for efficient queries

### ProviderFactory
- Maintains registrations of provider constructors (by ProviderType string)
- Supports capability declarations per provider type
- create(record) instantiates providers from ProviderRecord
- find_by_capability() for provider discovery
- Does NOT own provider instances

### ProviderManager
- Owns provider instances (singleton per provider_id)
- Manages lifecycle: initialize() → validate_configuration() → start() → close()
- Coordinates with ProviderFactory for instance creation
- Catalog is the single source of truth for initialization; no other bootstrap path

### LLMService
- Main interface for LLM operations (chat, embed, vision)
- Coordinates with ProviderManager for provider access
- Uses Router for routing decisions
- No direct knowledge of provider implementations

### Router
- Makes routing decisions based on request requirements
- Consults ModelCatalog for available models
- Uses RoutingStrategy for selection algorithm
- Returns RoutingDecision with provider_id and model_id

## Data Flow

### Startup Flow
```
1. Configuration (YAML) loaded
2. RegistryLoader.load() called
3. ProviderLoader + ModelLoader parse data
4. RegistryValidator.validate() checks semantics
5. CatalogBuilder builds ModelCatalog
6. ProviderManager.start() creates provider instances
7. LLMService initialized with all dependencies
```

### Request Flow
```
1. Client calls LLMService.chat(messages, model=...)
2. LLMService asks Router for routing decision
3. Router queries ModelCatalog for available models
4. Router applies RoutingStrategy to select provider
5. LLMService gets provider from ProviderManager
6. LLMService calls provider.chat()
7. Response returned to client
```

## Dependency Injection Points

### Constructor Injection
```python
# LLMService receives dependencies
llm_service = LLMService(
    provider_manager=provider_manager,
    catalog=catalog,
    router=router,
    default_strategy=strategy,
)

# Router receives catalog
router = Router(catalog=catalog, default_strategy=strategy)

# ProviderManager receives factory and catalog
provider_manager = ProviderManager(factory=factory, catalog=catalog)
```

### Bootstrap Pattern
```python
# In app/bootstrap.py or similar composition root:
catalog, load_result = CatalogBuilder(RegistryLoader()).build(
    providers_data=yaml.safe_load(providers_file),
    models_data=yaml.safe_load(models_file),
)

factory = ProviderFactory()
register_all_adapters(factory)          # Phase 3: register Ollama, OpenAI, Bedrock

provider_manager = ProviderManager(factory=factory, catalog=catalog)
await provider_manager.start()         # catalog must be frozen

llm_service = LLMService(
    provider_manager=provider_manager,
    catalog=catalog,
)
```

## Extension Points

### Adding a New Provider
1. Create adapter class inheriting from ``BaseProviderRuntime`` and relevant
   capability ports (``ChatCapable``, ``EmbeddingCapable``, etc.)
2. Implement ``initialize()``, ``validate_configuration()``, ``start()``, ``close()``
3. Register constructor: ``factory.register("my-provider", MyAdapter)``
4. Register capabilities: ``factory.register_capabilities("my-provider", {Capability.CHAT})``
5. Register in ``register_all_adapters()`` for automatic discovery
6. Add provider record to YAML configuration

### Adding a New Routing Strategy
1. Subclass RoutingStrategy
2. Implement `select()` method with custom selection logic
3. Register strategy: `router.add_strategy(MyStrategy())`

### Adding a New Validation Rule
1. Add method to RegistryValidator
2. Call from `validate()` method
3. Yield ValidationError for violations

## Phase 3 Additions

Phase 3 introduced the Provider Runtime:

- **BaseProviderRuntime**: Shared lifecycle contract for all adapters
  (initialize / validate_configuration / start / close)
- **OllamaAdapter**: Self-hosted Ollama inference; env-var resolution for
  OLLAMA_BASE_URL / OLLAMA_API_KEY
- **OpenAICompatibleAdapter**: OpenAI-API-compatible endpoints; resolves
  OPENAI_API_KEY / OPENAI_BASE_URL
- **BedrockAdapter**: AWS Bedrock; resolves AWS_REGION and AWS credentials
- **register_all_adapters()**: Convenience helper to register all Phase 3
  adapters with a ProviderFactory in one call

Phase 3 still deferred: HTTP client integration, inference execution,
streaming, health monitoring, conversation persistence.

## Phase 2 Additions

- **YAML loading from files**: RegistryLoader loads directly from files
- **ModelCatalog freeze()**: In-memory catalog becomes read-only after startup
- **RegistryValidator**: Cross-reference validation for models → providers
- **RegistryRuntime**: Process-lifetime owner of the frozen catalog
