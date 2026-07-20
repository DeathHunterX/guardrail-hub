# Fifth-Pass Review — Package Semantics

**Date:** 2026-07-20
**Scope:** package *names and boundaries* only. Layers, Domain, ownership, execution and contracts are ratified and were treated as fixed.
**Outcome:** **2 changes out of 41 packages.** 39 packages reviewed and deliberately left unchanged.
**Verification:** 195 passed / 2 pre-existing failures (baseline), `aios check: PASS`, no circular imports, notification public API byte-identical.

---

## 1. Package Semantic Review

The test applied to every package: *would this package still naturally exist if the project were rewritten in Go, Java, Rust or C#?* A package that survives that translation is named for a responsibility. A package that dissolves is named for a Python construct.

### 1.1 Changed — `services/notification/models/` → dissolved

**Why it failed the test.** `models` is a construct label ("things that are data"), not a responsibility. Rewritten in Java or Go, nobody creates a `models` package inside a notification component — the types sit with the behaviour that owns them.

**Why it became actively harmful, not merely imperfect.** This package was created in the third pass, *before* `app/domain/` existed. Once the Domain layer landed, the word "model" acquired a specific meaning in this codebase: a **domain model**, governed by ADR-0008's ubiquitous language. `services/notification/models/` contains no domain models at all — it held a delivery DTO and a presentation snapshot. A new engineer reading `notification/models/` now has a reasonable expectation that is exactly wrong. That is ambiguity introduced by a later ratified decision, which is a substantive justification rather than a stylistic one.

**Why dissolve rather than rename.** The package held two types with genuinely *different* responsibilities, so no single new name could describe both honestly. Renaming would have produced a second vague noun.

| Type | Responsibility | New home | Reasoning |
|---|---|---|---|
| `Notification` | **Message** — the request to deliver one message through one channel | `services/notification/message/` | It is the context's central vocabulary: accepted by the service, built by subscribers and dispatch, re-exported by the façade, used by `platform_reporter`. "What a message *is*" is a distinct responsibility from how one reads, whether to send, or how it is delivered. |
| `OperationProgress` | **Render model** — the neutral snapshot describing what happened | `services/notification/rendering/` | Its entire purpose is to be rendered; the renderer is its primary consumer and its docstring says the renderer and notifier "work only against this model". It belongs with the responsibility that consumes it, not in a bucket of data shapes. |

The resulting package set reads as a sentence: `message/` (what), `rendering/` (how it reads), `policy/` (whether to send), `dispatch/` (how it is delivered), `subscribers/` (what triggers it).

**Considered and rejected:** moving both types to the package root. `service-package-design` R1 (ratified, Decision 0006) states DTOs must never sit loose at a package root. Contradicting a ratified standard to save one directory is not a trade worth making.

### 1.2 Changed — `schemas/tools/jmeter/` removed

An **empty directory**. Not a naming problem — a truthfulness problem: the tree advertised a JMeter integration when zero lines exist. ADR-0005 already established removing empty scaffold directories as this repository's own anti-pattern; this one survived that sweep. Removal, not rename.

---

## 2. Responsibility Matrix

Every package, its responsibility, and whether its name states it.

| Package | Responsibility owned | Name states it? |
|---|---|---|
| `app/domain/findings/` | What a finding is; severity; aggregation rules | ✅ business capability |
| `app/domain/lifecycle/` | The phases an operation moves through | ✅ business capability |
| `app/core/ports/` | Outbound boundary contracts (hexagonal ports) | ✅ architectural role |
| `app/core/events/` | Event contracts + in-process delivery | ✅ responsibility |
| `app/core/config/` | Configuration composition | ✅ responsibility |
| `app/services/notification/` | Deciding and delivering notifications | ✅ capability |
| `…/notification/message/` | What gets delivered | ✅ **(new)** |
| `…/notification/rendering/` | How a notification reads + the model it reads from | ✅ |
| `…/notification/policy/` | Whether to send (throttling) | ✅ |
| `…/notification/dispatch/` | Delivery strategy (update vs. new, state) | ✅ |
| `…/notification/subscribers/` | What triggers a notification | ✅ |
| `app/services/operations/` | Operation lifecycle orchestration | ✅ capability |
| `app/services/platform/` | Platform lifecycle reporting | ✅ capability |
| `app/services/evaluations/` | Synchronous evaluation use case | ✅ capability |
| `app/services/public/` | Services backing public (non-MCP) endpoints | ⚠️ audience, not capability — see §5 |
| `app/services/tools/owasp_zap/` | The ZAP tool | ✅ vendor boundary |
| `…/owasp_zap/execution/` | Resolving and running operations | ✅ responsibility |
| `…/execution/handlers/` | Per-tool adapters onto the execution contract | ✅ responsibility |
| `…/owasp_zap/scenario/` | Authenticated workflow replay | ✅ capability |
| `…/owasp_zap/suite/` | Fan-out/fan-in across endpoints | ✅ capability |
| `app/integrations/chat/slack/` | Slack platform adapter | ✅ platform |
| `app/integrations/owasp_zap/` | ZAP transport, worker pool, scheduler | ✅ platform |
| `app/dao/` + `postgres/`, `dynamodb/` | Persistence; one package per backend | ✅ role + implementation |
| `app/routers/mcp/`, `public/` | HTTP/MCP entry points by audience | ✅ role |
| `app/schemas/` (+ `internal/`, `tools/owasp_zap/`) | Request/response contracts | ⚠️ ratified role — see §5 |
| `app/constants/` | Deployment-stable values | ⚠️ ratified role — see §5 |
| `app/helpers/tools/` | Tool-specific helper functions | ⚠️ ratified role — see §5 |

---

## 3. Before / After

```
BEFORE                                    AFTER
app/services/notification/                app/services/notification/
    __init__.py                               __init__.py
    notification_service.py                   notification_service.py
    models/              ← construct          message/             ← what gets delivered
        notification.py                           notification.py
        operation_progress.py                 rendering/           ← how it reads
    rendering/                                    operation_progress.py   (moved here)
        renderer.py                               renderer.py
    policy/                                   policy/
    dispatch/                                 dispatch/
    subscribers/                              subscribers/

app/schemas/tools/                        app/schemas/tools/
    jmeter/          ← empty scaffold          owasp_zap/
    owasp_zap/
```

Nothing else moved.

---

## 4. Justification for what changed

Both changes clear the Rename/Split justification bars:

| Condition | `models/` dissolution |
|---|---|
| Communicates responsibility more clearly | ✅ `message/` and `rendering/` name what they own; `models/` named a Python construct |
| Objectively more descriptive, not fashionable | ✅ Each type now sits with the behaviour that consumes it |
| Reduces ambiguity | ✅ **Primary driver** — "model" now denotes a domain model here, and these are not domain models |
| Improves maintainability | ✅ A new progress field is a rendering change; a new delivery field is a message change — the diff lands where the reader expects |
| Aligns with ubiquitous language | ✅ ADR-0008 defines the language; "model" is not in it |

Split justification: the two types had **genuinely mixed responsibilities** (a delivery request and a presentation snapshot) forced together by their Python kind. That is the sanctioned reason to split.

`schemas/tools/jmeter/` — removal of an empty directory, justified by ADR-0005's existing anti-pattern, not by naming.

---

## 5. Justification for what did NOT change

The conservative rule was applied literally: 39 of 41 packages were left alone. The notable candidates and why each survived:

**`app/constants/`, `app/helpers/`, `app/schemas/` — construct-shaped names, deliberately retained.** These are **ratified top-level roles** in `standards/architecture/backend-layering` R1 (Active, v1.1.0). Renaming them is not a package-semantics change; it is an amendment to a ratified standard, requiring an ADR and a version bump. The brief fixed those decisions as constraints. Separately, each is defensible on its own: `schemas/` holds request/response contracts (a genuine boundary role, not "classes that happen to be Pydantic"); `constants/` holds deployment-stable values that `paths.py` documents as *deliberately non-configurable*, which is a real distinction from `config/`; `helpers/tools/` is scoped by tool rather than being a general `utils/` dumping ground.

**`app/services/public/`** — names an *audience*, not a capability, and bundles `HealthService` (readiness probing) with `HistoryService` (operation reads). Flagged in the fourth-pass review and still true. Left unchanged because `backend-layering` **R2 explicitly sanctions** audience partitioning (`public/`, `mcp/`, `internal/`) and `routers/public/` mirrors it — renaming one side would break a deliberate, ratified symmetry. Recorded as semantic debt (§6) rather than fixed unilaterally.

**`app/core/ports/`** — "ports" is architectural vocabulary (hexagonal boundary contracts), not a language construct. It would exist verbatim in a Java or Go port of this system.

**`app/core/events/`** — owns event contracts *and* their in-process delivery. Considered splitting `contracts.py` from `dispatcher.py`; rejected as marginal — two closely related files, and the Package Collapse rule warns against packages that exist to hold one type.

**`app/domain/findings/`, `app/domain/lifecycle/`** — capability names fixed by ADR-0008. Out of scope and correct.

**`execution/handlers/`** — "handlers" is a role (adapters implementing the execution contract), not a construct. Also within ADR-0009's open scope; left untouched.

**`dao/postgres/`, `dao/dynamodb/`** — organised by *implementation* deliberately: they are interchangeable backends selected at runtime, which is exactly what a per-backend package should express.

**`notification/policy/`, `dispatch/`, `subscribers/`, `rendering/`** — already responsibility-named; no change.

---

## 6. Remaining semantic debt

1. **`services/public/`** mixes readiness probing with operation-history reads under an audience label. A future split into `health/` and `history/` would be clearer, but requires reconciling with `backend-layering` R2's sanctioned audience partitioning — an ADR-level question, not a refactor.
2. **`schemas/` vs `core/events/contracts.py`** — two homes for contract-shaped types (HTTP boundary contracts vs. inter-context event contracts). Both are correct for their boundary, but the word "contract" now spans two locations. Worth naming explicitly if a third contract kind appears.
3. **`app/helpers/tools/owasp_zap_helpers.py`** — a single 300-line module holding request building, alert conversion, report persistence, and proxy interaction. The *package* is fine; the **module** mixes responsibilities. That is a file-level concern, outside this pass's scope.
4. **`app/core/`** is doing double duty as infrastructure plumbing (logger, config, startup) and Contracts (ports, event contracts). Acceptable today; if Contracts grows, the distinction may deserve its own boundary — flagged, not acted on.

---

## 7. Verification

| Check | Result |
|---|---|
| Test suite | 195 passed / 2 pre-existing failures — **unchanged** |
| `aios check` (validate + links + lint + arch) | **PASS** |
| Circular imports | 48 modules + composition root imported cleanly, none |
| `compileall` | Clean |
| Notification public API | **Byte-identical** — `from app.services.notification import Notification, NotificationService, UnknownChannelError` unchanged; `platform_reporter` (the only external consumer) untouched |
| Construct-named packages remaining under `app/` | **None** except the three ratified top-level roles (§5) |
| Files touched | 10 (import paths only) + 2 façades + 3 file moves |
| Unnecessary movement | None — 39 of 41 packages unchanged |

Success here is not the two changes; it is the thirty-nine packages that were examined and left alone because their names already state what they own.
