# Frozen Repository Convention v1.0

**Status:** FROZEN · **Scope:** `mcp-server/app/**` and its mirrored test tree · **Supersedes:** nothing · **Next revision:** Architecture Freeze v2.0

---

## 1. Purpose

This document freezes the organization of this repository. It is the canonical answer to *"where does this code go?"*

**Future work extends this convention. It does not redesign it.**

Read this before creating any file. If a change appears to require new structure, that is a signal to re-read §5, not to invent. Anything genuinely undecided is marked **NOT FROZEN** in §10 — those items are the only open questions, and they are resolved by decision, not by improvisation.

This document states the convention only. It contains no rationale, no history, and no roadmap.

---

## 2. Repository Taxonomy

Nine top-level packages plus the composition root. This list is closed.

### `domain/`
- **Owns:** the canonical business vocabulary — what is *true* about security work regardless of framework, transport, or datastore.
- **Belongs:** business meaning, business rules, value objects, entities, canonical vocabularies. Partitioned by business capability (`findings/`, `lifecycle/`).
- **Never:** FastAPI, Pydantic, ORM, drivers, HTTP clients, transport SDKs, rendering, persistence, logging, tool-specific types, or any import from elsewhere in `app/`.

### `services/`
- **Owns:** application capabilities — use cases and workflows.
- **Belongs:** application services at each capability root; implementation detail in responsibility subpackages (§4).
- **Never:** transport framework types, direct persistence drivers, canonical vocabulary definitions.

### `integrations/`
- **Owns:** outward-facing implementations of ports — third-party SDKs, clients, transports, worker pools.
- **Belongs:** vendor adapters, connection management, native protocol handling, vendor-specific presentation.
- **Never:** application workflows, business rules, imports from `services/`.

### `dao/`
- **Owns:** persistence.
- **Belongs:** the DAO interface, one implementation per backend, runtime backend selection, row/item mapping, migrations, the persistence record.
- **Never:** ORM models, business decisions, imports from `services/`.

### `routers/`
- **Owns:** transport entry points (HTTP and MCP).
- **Belongs:** thin adapters, request/response wiring, error-to-status mapping. Partitioned by audience (`mcp/`, `public/`).
- **Never:** business logic, execution, persistence access.

### `schemas/`
- **Owns:** transport contracts.
- **Belongs:** request/response models and their boundary validation. Partitioned by audience (`internal/`) and by tool (`tools/<tool_name>/`).
- **Never:** persistence records, algorithms unrelated to validating a contract, business rules.

### `core/`
- **Owns:** cross-cutting infrastructure and inter-context contracts.
- **Belongs:** configuration composition, logging, exceptions, hexagonal ports (`ports/`), event contracts and delivery (`events/`), boot sequencing.
- **Never:** capability-specific business logic.

### `constants/`
- **Owns:** deployment-stable values.
- **Status:** see §10 — **NOT FROZEN**.

### `helpers/`
- **Owns:** nothing new. No file may be added here.
- **Status:** see §10 — **NOT FROZEN**.

### Composition root — `bootstrap.py`, `main.py`
- **Owns:** wiring and application construction.
- **Belongs:** dependency assembly, ASGI construction, lifespan, router mounting, event subscription, event-name→phase and type→title maps.
- **Privilege:** the composition root **may** import implementation details directly, past any capability façade. **No other module may.**
- **Never:** business logic, execution, rendering.

---

## 3. Tool Convention

### Canonical form

```
<layer>/tools/<tool_name>/
```

Applied today in `services/`, `schemas/`, `core/config/`, and the mirrored test tree. `integrations/` currently differs — see §10.

### Canonical tool naming rule

`<tool_name>` is the tool's full lowercase identifier with underscores: `owasp_zap`, `semgrep`, `trivy`, `checkov`, `gitleaks`, `jmeter`, `nuclei`. Abbreviations, hyphens, and vendor prefixes are not used in code paths. The same identifier is used in every layer.

### Category is never a directory

**Forbidden:** `tools/security/zap/`, `tools/performance/jmeter/`, or any `tools/<category>/<tool>/` form.

A filesystem path encodes facts that are **stable, single-valued, and objective**. A tool's name is all three. A tool's category is none: categories are reclassified over time, a single tool commonly belongs to several at once, and assignment is a judgment call. Encoding category in a path forces one permanent answer to a question with several, and multiplies the cost of revision by the number of layers a tool spans.

Category is therefore **documentation metadata**: it groups tools in `docs/`, where a tool may legitimately appear under more than one heading, and where reclassification costs nothing.

---

## 4. Internal Capability Organization

### The rule

> **A capability root answers *what the capability does for the business*.**
> **Its subpackages answer *how it does it*.**

- **Capability root contains application services only**, plus the `__init__.py` façade.
- **Every other responsibility lives in a subpackage** named for that responsibility.
- **Implementation details are never loose at a root**: no DTOs, dataclasses, enums, protocols, renderers, policies, adapters, or registries.

### Approved responsibility vocabulary

Each name below is in use in the repository today. Use these names when the responsibility exists; do not coin synonyms.

| Name | Owns |
|---|---|
| `execution/` | Resolving which unit of work runs, and running it |
| `handlers/` | Adapters onto an execution contract (nested inside `execution/`) |
| `rendering/` | Turning a model into presentation output, and the model it renders from |
| `policy/` | Pure decisions — whether, when, how often |
| `dispatch/` | Coordinating delivery of an already-decided outcome |
| `subscribers/` | Translating an inbound event into a call on the capability |
| `message/` | The capability's own vocabulary — what it accepts and delivers |

**Package or module.** A responsibility may be a single module when it is one cohesive unit (`platform/rendering.py`) or a package when it owns several (`notification/rendering/`). Prefer the module; promote only when a second cohesive module exists.

### Feature packages are not vocabulary

`scenario/` and `suite/` are **feature names** — business features inside the OWASP ZAP capability. They are not generic vocabulary and must not be copied into another capability by analogy. A new tool names its own features from its own domain.

---

## 5. Package Creation Protocol

**Before creating any file, answer all six questions. Failure to answer any question blocks creation.**

1. **Which business capability owns it?**
2. **Is it an application service or an implementation detail?**
3. **If an implementation detail — which responsibility does it own?**
4. **Does an existing responsibility already own that?**
5. **Can an existing module be extended instead?**
6. **If creating a package — why can this not remain a single module?**

**Order is binding.** Questions 4 and 5 precede question 6, so the default outcome is *extend what exists*. A new package requires questions 4 and 5 to have failed first.

**If question 3 cannot be answered without inventing a responsibility, stop.** Report the ambiguity; do not choose. Reaching for a generic name (§6) means question 3 is still unanswered.

---

## 6. Repository Vocabulary

### Approved package names

Capability names: `notification`, `operations`, `platform`, `evaluations`, `public`, `findings`, `lifecycle`.
Responsibility names: `execution`, `handlers`, `rendering`, `policy`, `dispatch`, `subscribers`, `message`, `ports`, `events`, `config`.
Structural partitions: `tools`, `mcp`, `internal`, `postgres`, `dynamodb`, `chat`.
Feature names: as required by the feature, in its own capability.

### Forbidden package names

```
helpers   utils    common    shared    misc
models    types    dto       base      interfaces
objects   definitions        entities  structs
```

**A package name states the responsibility it owns, never the language construct it contains.** `models/` describes what the objects *are* in Python; `message/` describes what they *mean* in the system. The second is the convention.

This prohibition applies at every level, in every layer, including inside tool packages.

---

## 7. Boundary Rules

### Dependency direction

```
routers → services → integrations | dao → domain
```

Inward only. `domain/` is innermost and imports nothing else from `app/`. Every other layer may depend on `domain/`, including infrastructure.

### Per-layer ownership and common violations

| Layer | Owns | Common violation |
|---|---|---|
| `services/` | Orchestration, use cases, workflows | Execution loops, module-level thread pools, direct socket/HTTP/filesystem I/O, transport framework types |
| `integrations/` | Vendor SDKs, transports, pools | Importing `services/`; parsing rendered output to recover structure |
| `domain/` | Canonical vocabulary and business rules | Any framework or transport import; any import from another layer |
| `dao/` | Persistence and mapping | ORM models; a caller importing a concrete backend instead of the interface |
| `routers/` | Transport entry | Business logic in a handler; reaching past a service into a DAO |
| `schemas/` | Transport contracts | Holding a persistence record; holding algorithms unrelated to contract validation |

### Public API boundary

Each capability exposes its contract through its `__init__.py` façade with an explicit `__all__`. **No module outside the composition root imports a capability's internal subpackage.** Tests are exempt and may import the units they test.

---

## 8. Tool Responsibility Rules

| Responsibility | Owns | Must not |
|---|---|---|
| **execution** | Execution contracts, type/strategy vocabulary, registries, dispatch loops, scheduling, polling, worker binding, the runner bodies that drive a tool | Make business decisions; render; own module-level concurrency; define capability vocabulary |
| **rendering** | Formatting, layout, vocabulary humanisation, format emission, the render model | Persist; perform I/O; execute workflows; make business decisions |
| **policy** | Whether, when, how often — throttling, gating, emission rules | Perform I/O; render; execute. A policy is testable with no collaborator but a clock |
| **dispatch** | Delivery strategy selection, per-subject state, capability-aware branching, best-effort error handling | Render inline; use a transport SDK directly; own business rules |
| **handlers** | Adapting one concrete operation onto the execution contract, plus its registration factory | Contain execution logic; schedule; render |

**translation** — see §10. The responsibility is defined but not yet present in the repository.

---

## 9. Future Expansion Rules

A new tool (Semgrep, Trivy, Checkov, Gitleaks, JMeter, Nuclei, or any other) **extends this convention and never redesigns it**.

**A new tool inherits:**
- the `<layer>/tools/<tool_name>/` partition,
- the capability rule (root = application services; subpackages = responsibilities),
- the existing responsibility vocabulary (§4),
- the dependency direction and façade rules (§7),
- the package creation protocol (§5).

**A new tool provides:**
- its application services at its capability root,
- an `execution/handlers/` adapter registered in the composition root,
- its transport contracts under `schemas/tools/<tool_name>/`,
- its vendor adapter under `integrations/`,
- one router module under `routers/mcp/`,
- its settings mixin under `core/config/tools/`,
- its own feature packages, named from its own domain.

**A new tool never:**
- creates a top-level package,
- creates a generic bucket (§6),
- introduces a category directory (§3),
- copies another tool's feature names,
- redefines canonical vocabulary — `Severity`, `Finding`, `FindingSummary`, `FindingIdentity`, `Confidence`, and `OperationPhase` are imported from `domain/`, never re-declared.

**New responsibility vocabulary requires evidence.** A name is added to §4 only when the responsibility exists in code in more than one place, or is required by a ratified decision. A responsibility that has never been implemented is not vocabulary.

---

## 10. Freeze Status

| Convention | Status |
|---|---|
| Top-level taxonomy (nine packages + composition root) | **FROZEN** |
| Dependency direction `routers → services → integrations\|dao → domain` | **FROZEN** |
| Domain purity (no framework, transport, infrastructure, or `app/` imports) | **FROZEN** |
| Capability organization (root = application services; subpackages = responsibilities) | **FROZEN** |
| Responsibility vocabulary: `execution`, `handlers`, `rendering`, `policy`, `dispatch`, `subscribers`, `message` | **FROZEN** |
| Feature packages are feature-named, not generic (`scenario`, `suite`) | **FROZEN** |
| Module-before-package rule | **FROZEN** |
| Package creation protocol (six questions, binding order) | **FROZEN** |
| Forbidden name list | **FROZEN** |
| Public API façade rule + Composition Root Exception | **FROZEN** |
| Tool partition by name: `services/tools/<tool_name>/`, `schemas/tools/<tool_name>/`, `core/config/tools/` | **FROZEN** |
| Category is never a directory | **FROZEN** |
| Category as documentation metadata | **FROZEN** (as a principle) |
| Layer responsibilities and violation list (§7) | **FROZEN** |
| Tool responsibility definitions: execution, rendering, policy, dispatch, handlers | **FROZEN** |
| Tests mirror the source tree | **FROZEN** |
| — | — |
| **`integrations/` tool partition** — uses `integrations/<tool_name>/` today, with no `tools/` level, unlike other layers | **NOT FROZEN** |
| **`translation/` responsibility** — defined in §8 but **not present in the repository**; no package or module exists | **NOT FROZEN** |
| **`execution/runners/`** — does not exist; whether execution bodies warrant a package is undecided | **NOT FROZEN** |
| **`helpers/`** — exists and is currently sanctioned; its removal is pending decision. **No file may be added to it** | **NOT FROZEN** |
| **`constants/`** — exists; its contents' ownership is undecided | **NOT FROZEN** |
| **Tool naming consistency** — `core/config/tools/_zap.py` and `docs/owasp-zap/` differ from the `owasp_zap` identifier | **NOT FROZEN** |
| **`docs/` structure** — category-first grouping is endorsed in principle; no concrete layout is in place | **NOT FROZEN** |
| **Category metadata mechanism** — where a tool declares its category is undesigned | **NOT FROZEN** |
| **Algorithms in `schemas/tools/owasp_zap/`** (`_graph.py`, `openapi_spec.py`) — placement disputed | **NOT FROZEN** |
| **`core/startup.py`** — boot sequencing vs. composition-root placement undecided | **NOT FROZEN** |
| **Execution logic in ZAP capability roots** — extraction approved in principle, destination undecided | **NOT FROZEN** |
| **Direct I/O inside `services/`** (storage probing, report writing) — destinations undecided | **NOT FROZEN** |

### Rules for NOT FROZEN items

1. They are **not** open invitations to improvise. Each is a pending decision.
2. Until decided, **preserve the current state**. Do not "fix" a NOT FROZEN item while implementing a feature.
3. If a feature is blocked by one, **stop and report it** rather than resolving it under delivery pressure.
4. Resolving one requires a recorded decision, after which it moves to FROZEN in v1.1 or later.

---

**This document is the architectural constitution of this repository until Architecture Freeze v2.0.** Everything marked FROZEN is settled: extend it, do not revisit it. Everything marked NOT FROZEN is the complete list of open questions — nothing else is open.
