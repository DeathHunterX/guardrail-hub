# 0009 — Has Execution Become an Architectural Capability?

Status: **Proposed** — recommendation is **Reject the capability; approve a narrow contract-hygiene fix**. Requires backend-owner ratification.
Owner: Loi Phan
Date: 2026-07-20
Relates to: [Decision 0007](0007-domain-layer-justification.md) (the evidentiary standard this ADR is held to), [Decision 0008](0008-domain-ubiquitous-language.md) §2.3 (which already rejected Execution as *domain* vocabulary), [domain-layer-growth-stress-test.md](../architecture/evidence/domain-layer-growth-stress-test.md) §5 (which first flagged execution as the next pressure point).
No implementation, no file moves, no AIOS changes follow from this ADR.

---

## 1. Recommendation

| Proposal | Verdict |
|---|---|
| A general **Execution capability / abstraction** over pluggable execution models | ❌ **Reject — not yet** |
| **Execution contract hygiene** (decouple the existing contract from ZAP, consolidate concurrency ownership, delete dead strategy members) | ✅ **Approve** |

**The abstraction is rejected because its shape is not knowable today, not because execution is unimportant.** You cannot usefully abstract over a set of one: the repository contains exactly one execution model (a pooled, long-lived worker) and zero implementations of the others. What *can* be done today — and should be — is stop the single existing model from being baked into the contract every future tool will implement.

This is the same test ADR-0007 applied to the Domain layer. That ADR approved a layer on evidence of **six present-day duplicate definitions with a live correctness conflict**. Execution has no comparable evidence. Approving it on the strength of a tool roadmap that has *zero lines of code* would contradict the precedent this repository just set, and ADR-0007 §2.4 explicitly rejected roadmap-based justification.

---

## 2. Evidence

### 2.1 The abstraction has no second implementation to abstract over

Verified: **nothing outside the ZAP tool package imports `execution/`** except `bootstrap.py`, which is the composition root. There is one dispatcher, one pool, one registry, one worker model. An abstraction extracted from a single case encodes that case; it does not generalise it.

The growth stress-test identified at least three substrates that would eventually be needed — daemon pool (ZAP, Burp), ephemeral process (Semgrep, Trivy, Checkov, Nuclei), and distributed/long-running (JMeter) — but **all three counts of implementations are: 1, 0, 0.**

### 2.2 The current design already contains a failed speculative abstraction

`ExecutionStrategy` declares five members. Verified usage across the entire codebase:

| Member | Used? |
|---|---|
| `SEQUENTIAL` | ✅ `api_scan`, `api_scenario` |
| `FAN_OUT` | ✅ `api_suite` |
| `PARALLEL` | ❌ never — comment says "reserved" |
| `BATCH` | ❌ never — comment says "reserved for future batching semantics" |
| `FAN_IN` | ❌ never — declared, never registered |

Three of five members were added for futures that never arrived. The Dispatcher reads **exactly one property** off the whole enum — `requires_worker`, a boolean.

This is the strongest single argument against the proposal. *The last time this codebase speculated about execution shapes, it was 60% wrong.* Building a larger abstraction on the same speculation repeats a mistake already visible inside the package being abstracted.

### 2.3 What *is* real today: the contract is coupled to one tool and one framework

`execution/handler.py` is documented as the generic contract every ZAP tool implements. It imports:

- `from app.schemas.tools.owasp_zap.worker import ZapWorkerInfo` — a **tool schema** in the generic contract, and
- `from pydantic import BaseModel` — a **framework** type in the generic contract.

`ZapOperationHandler.execute(operation_id, request, worker: Optional[ZapWorkerInfo])` therefore states, in its signature, that *executing anything means being handed a ZAP worker*. Semgrep has no worker. Trivy has no worker. This is the same defect class as `OperationStatus` living inside a ZAP schema — which ADR-0008 identified and this repository has since fixed.

**This is present-day, verified evidence, and it is the part worth acting on.** It does not require a new capability; it requires removing a wrong assumption from an existing contract.

### 2.4 Concurrency ownership is genuinely duplicated

Three thread pools, verified:

| Location | Pool |
|---|---|
| `api_scanner.py:71` | module-level `ThreadPoolExecutor(max_workers=32)` |
| `scan_api_scenario.py:52` | module-level `ThreadPoolExecutor(max_workers=32)` |
| `execution/dispatcher.py:78` | injected-or-default `ThreadPoolExecutor(max_workers=4)` |

Two are module-level globals — created at import, unconfigurable, unbounded by settings, and not injectable for tests. A third scan tool would add a fourth. This is real duplication of a real responsibility (concurrency ownership), and unlike the execution *model* it is duplicated **today**.

### 2.5 Capabilities that are modelled but do not exist

| Concern | Status |
|---|---|
| **Cancellation** | `OperationPhase.CANCELLED` and `OperationService.cancel()` exist. **Nothing calls `cancel()`** — verified, zero call sites. A phantom capability: modelled, published as an event contract, never invoked. |
| **Retries** | Explicitly out of scope, documented in five places ("no automatic retry — resubmitting is left to the user"). |
| **Heartbeats** | Implemented, but as a *worker-liveness* mechanism specific to long-lived daemons. Meaningless for an ephemeral process, which either exits 0 or does not. |
| **Scheduling** | Round-robin over idle workers (`scheduler.py`, 62 lines). No priorities, no fairness, no queue classes. |
| **Container / cloud execution** | Not implemented in any form. |

Designing an abstraction whose members include two things that do not exist (cancellation, retries) and two that are not implemented at all (container, cloud) would be designing against imagination.

### 2.6 Evidence *for* the proposal (stated fairly)

- **Deferral has a compounding cost.** Every tool added before the contract is fixed inherits the `ZapWorkerInfo` signature, so the eventual migration grows with tool count. §2.3's fix addresses precisely this, without the layer.
- **~1,190 lines** of worker-pool infrastructure (`registry`, `scheduler`, `pool`, `runtime`, `client`, `configurator`) already form a coherent subsystem. It *looks* like a capability. But it is coherent as **ZAP infrastructure**, correctly located in `integrations/owasp_zap/`, and none of it is currently shared.
- **The naming misleads.** `execution/`, `ExecutionStrategy`, `dispatcher` read as generic while being ZAP-bound. That is a documentation and contract problem, not a missing layer.

---

## 3. Capability Test

Applying an explicit test for an *application capability* (distinct from the Domain qualification test, which Execution already fails on business-meaning grounds per ADR-0008 §2.3):

| Criterion | Result |
|---|---|
| More than one implementation exists today | ❌ One (worker pool) |
| The abstraction's shape is knowable from evidence | ❌ Three substrates hypothesised, zero built |
| Consumed by more than one context | ❌ ZAP package + composition root only |
| Responsibility is duplicated today | ⚠️ **Partially** — concurrency ownership yes (§2.4); execution model no |
| Deferring bakes in a wrong assumption | ✅ **Yes** — `ZapWorkerInfo` in the generic contract (§2.3) |
| Has a clear prospective owner | ✅ backend-owner |
| Stable semantics | ❌ Substrate varies fundamentally per tool family |
| Independent of infrastructure | ❌ Execution *is* infrastructure — threads, processes, containers |

**Two of eight.** The two that pass are exactly the two the narrow approval addresses. The six that fail are all forms of the same fact: there is one execution model and its successors are unbuilt.

---

## 4. Approved scope — Execution Contract Hygiene

Not a new capability, layer, or package. Four bounded changes inside the **existing** `services/tools/owasp_zap/execution/`:

**H1 — Decouple the execution contract from the worker model.** `ZapOperationHandler.execute` should not name `ZapWorkerInfo`. The handler needs "the resources this operation was allocated"; for a pooled tool that is a worker, for an ephemeral tool it is nothing. Replacing the parameter with a neutral, tool-owned context object removes the worker-pool assumption from the contract without inventing an execution abstraction. *(Highest value: it is what every future tool would otherwise inherit.)*

**H2 — Remove the framework type from the contract.** `pydantic.BaseModel` in `handler.py` makes request validation part of the execution contract. The contract needs serialize/deserialize behaviour, not a framework base class.

**H3 — Delete the unused strategy members.** `PARALLEL`, `BATCH`, `FAN_IN` have never been used (§2.2). Deleting them shrinks the contract to what is true and removes three invitations to build on speculation. *(This ADR deliberately recommends **removing** abstraction, not adding it.)*

**H4 — Consolidate concurrency ownership.** The two module-level thread pools (§2.4) should be injected and settings-bounded, as the dispatcher's orchestration executor already is. This is a genuine present-day duplication fix, independent of any future execution model.

Explicitly **not** approved: an `ExecutionEngine` interface, an execution capability package, a substrate abstraction, container/cloud execution, a retry policy, a cancellation mechanism, or a scheduler abstraction.

---

## 5. Ownership and Dependency Rules

Unchanged by this ADR, restated so ratification is unambiguous:

- **Owner:** backend-owner. Execution remains part of the ZAP tool package (`services/tools/owasp_zap/execution/`); the worker-pool machinery remains ZAP infrastructure in `integrations/owasp_zap/`.
- **Layer:** Application/Infrastructure. Execution is **not** Domain — ADR-0008 §2.3 settled this ("mechanics, not business meaning"; a user does not care whether a scan ran `SEQUENTIAL`).
- **Dependency direction:** execution may depend on `domain/`, `core/`, `schemas/`, `integrations/`, and `dao/`. Nothing in `domain/` may depend on execution. The composition root remains the only module outside the tool package that touches it.
- **After H1/H2:** the execution contract depends on no tool schema and no framework — the same purity property the Domain layer holds, achieved without moving it anywhere.

---

## 6. Migration Strategy (planning only)

Sequenced so each step is independently shippable and behaviour-preserving:

1. **H3 (delete dead members)** — smallest, zero behavioural risk, shrinks the surface the later steps touch.
2. **H2 (drop the framework type)** — contained to `handler.py` and the three handler factories.
3. **H1 (neutral execution context)** — touches `handler.py`, three handlers, the dispatcher's two dispatch paths, and their tests. Behaviour-preserving: for `api_scan`/`api_scenario` the context still carries the assigned worker; for `api_suite` it stays empty.
4. **H4 (inject the thread pools)** — touches `api_scanner.py` and `scan_api_scenario.py`; wire from settings in `bootstrap.py`, matching how dispatcher intervals are already configured.

Each step ends with the full suite plus `aios check`. **No file moves and no new packages** — this is a contract change inside an existing package.

### Revisit trigger

This ADR should be reopened — as a new Decision, not an amendment — when **either** holds:

- **A second execution substrate lands.** The first non-daemon tool (Semgrep, Trivy, Checkov, Nuclei) gives a real second implementation to generalise from. That is when the abstraction's shape becomes knowable rather than imagined.
- **A cross-tool execution concern is genuinely required** — e.g. global concurrency limits, priority queues, or cancellation actually being invoked by a user-facing feature.

Until then the answer is: fix the contract, do not build the layer.

---

## 7. Risks

**If rejected (recommended):**
- *Medium* — the naming (`execution/`, `ExecutionStrategy`) keeps implying generality it does not have; a contributor may over-trust it. Mitigated by H1–H3, which make the contract honest about its scope.
- *Low* — a second tool arrives and needs contract work then. Reduced by H1: the worker assumption is already removed.

**If approved as proposed (not recommended):**
- *High* — an abstraction derived from one implementation. The most likely outcome is that tool #2 does not fit it and it is rewritten, having cost the design work twice. §2.2 shows this already happened once at enum scale.
- *High* — a new package invites accretion (retries, cancellation, scheduling policies) for capabilities that do not exist, exactly the dumping-ground failure Decision 0006 was written to prevent.
- *Medium* — contradicts the evidentiary standard set two decisions ago, weakening the precedent that a layer must earn its existence.

---

## 8. Decision Record

**Reject** the Execution capability. **Approve** H1–H4 as contract hygiene within the existing package.

The honest summary: execution is the correct *next* pressure point, and the current contract does contain a real, verified defect — it hard-codes one tool's worker model into the abstraction every future tool must implement. That defect deserves fixing now. But the fix is subtraction, not addition: remove the wrong assumption, delete the unused speculation, and wait for a second implementation before generalising. The evidence for a capability will exist the day a second execution substrate does — and not before.
