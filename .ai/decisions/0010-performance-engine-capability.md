# 0010 — Introducing a Performance Engine: What Does JMeter Change?

Status: **Accepted** — ratified by backend-owner 2026-07-22 as the **canonical architectural baseline** for the Performance Engine. The recommendation below is approved as written; the R1 revision (§4.2–§4.11) is part of the accepted baseline. This ADR records architectural decisions only; phased engineering work is sequenced in the separate implementation plan at `architecture/performance-engine/implementation-plan.md`.
Owner: Loi Phan
Date: 2026-07-22
Relates to: [Decision 0009](0009-execution-capability.md) (this ADR is the reopening its §6 revisit-trigger named), [Decision 0007](0007-domain-layer-justification.md) (the "earn your existence" evidentiary standard), [Decision 0008](0008-domain-ubiquitous-language.md) §2.3 (rejected *Execution* as domain vocabulary), [backend-layering](../standards/architecture/backend-layering.md), [service-package-design](../standards/architecture/service-package-design.md), [domain-layer](../standards/architecture/domain-layer.md). Supersedes nothing. The JMeter Docker infrastructure landed 2026-07-22 as scaffolding; this ADR governs the runtime it will host.
Revision: **R1 (2026-07-22)** — resolves the ten decision gaps raised by the Architecture Readiness Evaluation ("READY WITH MAJOR CHANGES"). The revision **adds** contract-level detail (new §4.2–§4.11) and two closing sections (§11 Architecture Delta, §12 Implementation Readiness Assessment); it **changes no accepted decision** from the original draft. Every §1–§3, §5–§10 conclusion stands. See §11 for the precise delta.

---

## 1. Recommendation

| Proposal | Verdict |
|---|---|
| Execute ADR-0009's approved **contract hygiene** (H1–H4) as the enabling precondition | ✅ **Approve** — it is the "decouple first" step |
| A **Performance capability** (runtime + worker + engine seam) on the neutral contract | ✅ **Approve** — JMeter is a real second substrate; the shape is now knowable |
| A **multi-engine framework** abstracting over JMeter/k6/Gatling/Locust today | ❌ **Reject — not yet** — one performance engine exists; the others are zero |
| A **shared worker-pool extraction** unifying ZAP and Performance infra now | ❌ **Defer** — two worker models now exist but differ fundamentally; consolidate on evidence, not anticipation |
| Warm worker, **queue + local runtime, pull delivery, subprocess with process groups** | ✅ **Approve** — the correct model for a batch engine |

**The decisive fact:** ADR-0009 rejected an execution abstraction because "you cannot abstract over a set of one," and it named the reopening condition precisely — *"a second execution substrate lands."* JMeter is that substrate: a distributed/long-running, batch-CLI engine, categorically unlike ZAP's long-lived daemon. So the abstraction 0009 deferred is now justified **at the contract level** (H1–H4) and **at the worker-model level** (a second worker lifecycle is real). It is **not yet** justified at the *engine* level, where the same "set of one" logic 0009 applied to execution now applies to performance engines: JMeter is one; k6, Gatling, Locust are zero. We therefore build the engine *seam*, not the engine *framework*.

This keeps two promises at once: the spec's "the engine must remain replaceable" (satisfied by a thin, honest seam) and 0009's precedent (satisfied by refusing to scaffold engines that do not exist).

---

## 2. Evidence

### 2.1 JMeter is the second substrate 0009 predicted — and it is genuinely different

ADR-0009 §2.1 enumerated three hypothesised substrates with counts `1, 0, 0`: daemon pool (ZAP), ephemeral process, and **distributed/long-running (JMeter)**. JMeter moves the third count to `1`. Crucially, it is not a variation on ZAP; it inverts the lifecycle:

| Property | ZAP (daemon pool) | JMeter (warm worker, batch) |
|---|---|---|
| What is long-lived | the engine (ZAP daemon) | the **worker**, not the engine |
| What is short-lived | nothing | the **`jmeter -n` process** (one per job) |
| How mcp-server drives it | **push** — dispatcher assigns, handler drives worker over HTTP (ZAP REST API) | **pull** — worker claims its assignment; execution is local |
| Worker exposes | a REST API (the ZAP daemon) | **nothing inbound** — no HTTP daemon, no JMeter REST wrapper |
| Execution locus | remote (server-driven, on the worker's daemon) | **local to the worker process** via `subprocess()` |
| Heartbeat meaning | worker (daemon) liveness | worker liveness **plus** capacity/health (§2.3) |

0009 §2.5 observed that heartbeats are "meaningless for an ephemeral process, which either exits 0 or does not." JMeter confirms the boundary: the *worker* is long-lived and heartbeats meaningfully; the *engine process* is ephemeral and simply exits with a code. This is why heartbeats belong to the worker, and exit-code handling belongs to the runner — two different mechanisms for two different lifetimes.

### 2.2 The contract 0009 flagged is exactly what JMeter would otherwise inherit

0009 §2.3 identified the live defect: `ZapOperationHandler.execute(operation_id, request, worker: Optional[ZapWorkerInfo])` welds one tool's worker model and one framework type (`pydantic.BaseModel`) into the supposedly-generic contract. If Performance is built *before* H1–H4, it inherits `ZapWorkerInfo` — a ZAP schema — into a JMeter execution path. That is the compounding cost 0009 §2.6 warned about, now concrete. **"Decouple first" is not optional polish; it is the precondition that keeps JMeter from importing ZAP.**

### 2.3 A performance engine's health is load-bearing for scheduling — unlike a scanner's

The spec requires the heartbeat to expose status, version, current job, CPU, memory, disk, workspace size, orphan-process count, and last-cleanup time, and requires the dispatcher to *use* this when scheduling. This is a real new requirement, not speculation: a JMeter run is resource-hungry (a full JVM under load), so "idle" is insufficient — a worker can be registered-and-idle yet unfit (low memory, disk pressure, leaked orphan processes from a prior kill). ZAP never needed this because a scan's load lives on the ZAP daemon, not the mcp-server-facing worker record. The health-aware heartbeat is therefore a Performance-specific extension of the registry model, justified by a present requirement.

### 2.4 Replaceable engines is a *seam* requirement, not a *framework* requirement

The spec says JMeter "must remain replaceable" by k6/Gatling/Locust and "MUST NOT tightly couple business logic to JMeter." 0009's own reasoning, applied one level down, resolves how far to go: there is exactly **one** performance engine (JMeter); k6/Gatling/Locust are **zero**. Building a plugin registry, capability negotiation, or engine-selection framework now would repeat the precise mistake 0009 documented — abstracting over a set of one, then discovering engine #2 does not fit. The requirement is fully met by a **minimal seam**: a `PerformanceRunner` protocol plus engine-neutral `ExecutionRequest`/`ExecutionResult`/`ArtifactSet` DTOs, with JMeter as the sole implementation and every JMeter-specific concern (CLI flags, `.jmx` validation, `.jtl`/HTML artifacts) confined behind it. Engine #2, when real, becomes a second implementation of a proven seam — not a retrofit of an imagined one.

---

## 3. Capability Test

Applying ADR-0009 §3's explicit capability test to **Performance** (not to a generic engine framework):

| Criterion | Result |
|---|---|
| More than one implementation exists today | ⚠️ **Worker model: yes** (ZAP + JMeter). **Engine: no** (JMeter only) |
| The abstraction's shape is knowable from evidence | ✅ **Worker/runtime: yes** — the batch lifecycle is fully specified. ❌ Multi-engine: no |
| Consumed by more than one context | ✅ MCP tools, dispatcher, worker, and (future) reporting |
| Responsibility is duplicated today | ✅ Concurrency ownership (0009 §2.4, still unfixed); ⚠️ worker-registry model (about to be) |
| Deferring bakes in a wrong assumption | ✅ Building before H1–H4 imports `ZapWorkerInfo` into JMeter (§2.2) |
| Has a clear prospective owner | ✅ backend-owner |
| Stable semantics | ✅ **Performance** (run a plan, produce metrics/artifacts) is stable; the *engine* under it is not |
| Independent of infrastructure | ❌ Execution *is* infrastructure — processes, workspaces, containers |

**The pattern is deliberate:** every criterion passes for *the performance capability and its worker/runtime*, and fails for *a multi-engine framework*. That split **is** the recommendation — approve the capability and the seam, refuse the framework.

---

## 4. Approved Architecture

```
User
 └─ MCP Tool            generate_performance_plan · execute_performance_test   (routers/mcp/jmeter_router.py)
     └─ Performance Service      validate plan · enqueue operation · return result   (services/performance/)
         └─ Operations queue     REUSED as-is — OperationService/OperationDAO (already engine-agnostic)
             └─ Performance Dispatcher   assign QUEUED perf op → idle, healthy worker · orphan sweep
                                          (parallel to ZAP dispatcher, on the H1 neutral contract)
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  process / container boundary  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                 └─ Performance Worker (LONG-LIVED)     register · heartbeat(health) · PULL assignment
                     └─ Performance Runtime (LOCAL)     prepare workspace · validate · invoke runner ·
                                                        collect artifacts · redact · cleanup · report
                         └─ JMeter Runner               build `jmeter -n` args · subprocess in own
                                                        process group · timeout · cancel(kill group) ·
                                                        stdout/stderr · exit code · collect artifacts
                             └─ Apache JMeter (SHORT-LIVED)   one `jmeter -n` per job, then exits
                                 └─ Artifacts            JTL · HTML report · logs · metadata
```

**Load-bearing decisions, stated so ratification is unambiguous:**

- **D1 — Reuse the queue; do not duplicate it.** The Operations table + `OperationService`/`OperationDAO` are already engine-agnostic. Performance operations are ordinary operations with a Performance `operation_type`. No parallel queue.
- **D2 — Assignment is server-side; delivery is pull.** The dispatcher assigns a queued operation to an idle, *healthy* worker (sets `op_id`), exactly as ZAP does. But because the worker exposes **nothing inbound**, the worker *pulls* its assignment on its heartbeat/poll cycle, runs it locally, and *reports* the result back. No HTTP daemon and no JMeter REST wrapper are introduced (per the chosen worker model).
- **D3 — Runtime and Runner run inside the worker process,** not inside mcp-server. mcp-server schedules; the worker executes. The Service layer never calls `subprocess()` — only the Runner does (satisfies the spec's "Service layer must never invoke subprocess directly").
- **D4 — Parallel worker infrastructure, engine-neutral, not a shared extraction.** `PerformanceWorkerRegistry` / `PoolManager` / `Scheduler` / `Dispatcher` mirror the ZAP shapes but operate on the H1 neutral contract and carry the health-aware heartbeat (§2.3). ZAP is untouched. This accepts bounded duplication now (the option chosen over a premature shared extraction) and records the consolidation trigger in §8.
- **D5 — Engine seam, one implementation.** `PerformanceRunner` protocol + neutral DTOs; JMeter is the only implementation. No engine registry, no k6/Gatling stubs.
- **D6 — Stateless worker contract.** Create workspace → execute → export artifacts → cleanup → reset → idle. Cleanup is mandatory and runs on success *and* failure. Workspaces are never reused across jobs. The worker retains no business state between jobs.

### 4.1 Layering & placement (this ADR authorises the new packages per backend-layering "Exceptions")

Engine-neutral **capability** (application/infrastructure, may depend on `domain/`, `core/`, `schemas/`, never the reverse):

```
app/schemas/performance/         worker+health, execution request/result, artifact metadata, execution policy (neutral)
app/services/performance/        engine-neutral capability
    runtime/                     PerformanceRuntime (prepare/validate/invoke/collect/redact/cleanup)
    engine/                      PerformanceRunner protocol + neutral DTOs (the seam)
    policy/                      ExecutionPolicy resolution (network policy; metadata-endpoint block default)
    redaction/                   artifact redaction
    worker/                      PerformanceWorker long-lived loop (register/heartbeat/pull/report)
app/integrations/performance/    worker registry · pool · scheduler · dispatcher (parallel to owasp_zap/)
```

JMeter **engine implementation** (follows the mandated tool layout, backend-layering R3):

```
app/integrations/jmeter/         jmeter_runner.py (the seam impl) · jmx_validator.py (whitelist)
app/schemas/tools/jmeter/        the two MCP tools' wire models
app/routers/mcp/jmeter_router.py generate_performance_plan · execute_performance_test  (stubs this phase)
```

**Vocabulary (per ADR-0008 / backend-agent escalation rule):** this ADR introduces the business concepts *PerformancePlan*, *PerformanceOperation*, *ExecutionPolicy*, *ArtifactSet*, and *WorkerHealth*. Per D2/D4 of [domain-layer](../standards/architecture/domain-layer.md), only concepts that are genuinely engine-agnostic and reused across layers are candidates for `domain/`; engine wire formats (`.jmx`, `.jtl`) stay in the JMeter adapter (domain-layer D5). The initial implementation keeps these in `schemas/performance/`; promotion of any to `domain/` is deferred until a second engine demonstrates the duplication, consistent with 0007's standard.

### 4.2 Pull Worker Contract & Lifecycle

The worker exposes **no inbound channel**; every server→worker signal is delivered as the *response* to a worker-initiated call. There are exactly four worker-initiated calls, all on the authenticated worker API (§4.9), and one control channel (the heartbeat response). This is the whole protocol — nothing else crosses the boundary.

| Call (worker → server) | Purpose | Server does | Response carries |
|---|---|---|---|
| **Register** | announce on startup / restart | upsert into the Performance registry → ACTIVE; record `version`, capacity | assigned `worker_id`, server's `min_compatible_version` (§4.8) |
| **Heartbeat** (periodic) | liveness **+** health + control-channel poll | refresh `last_heartbeat`; return current control state | `state`; `assignment: {operation_id}` if one was bound since last beat; `cancel_requested: bool` for the current operation |
| **Pull Assignment** `(operation_id)` | fetch the payload after a heartbeat announced one | authorize the worker owns that op; return the validated plan + resolved policy | `PerformancePlan` reference/body + `ExecutionPolicy` (§4.5, §4.7) |
| **Report** `(operation_id, outcome)` | terminal result: completion, failure, or cancellation | persist redacted artifacts (§4.6), transition the operation, release the worker | ack |

**Lifecycle of one worker:**

```
start → Register → [ Heartbeat loop ⇄ health+control ]
                        │  heartbeat response has assignment{op}?
                        ▼
                   Pull Assignment(op) → create workspace → write plan → validate →
                   Runner runs `jmeter -n` (own process group) → collect → redact →
                   Report(op, completed|failed|cancelled) → destroy workspace → reset
                        │
                        ▼  (op_id cleared server-side; worker idle)
                   back to Heartbeat loop  → … → SIGTERM → drain (DRAINING) → deregister/stop
```

- **Ready/idle state** is the absence of a bound `op_id`; a worker advertises readiness simply by heart-beating with no assignment. Busy/idle stays **derived** from `op_id` (the ZAP registry invariant — no separate status field).
- **Report Completion / Report Failure / Report Cancellation** are the same call with different outcomes; each is terminal, each releases the worker, none carries unredacted data.
- **Shutdown** reuses the existing `DRAINING → OFFLINE` lifecycle: a worker asked to stop finishes or cancels its current op, then stops heart-beating; the heartbeat-timeout sweep (already built for ZAP) reaps a worker that dies without draining and fails its in-flight op — no new reaping mechanism.

### 4.3 Cancellation Propagation

Cancellation is the one signal that must reach a *running* worker that has no inbound channel. It is resolved by the heartbeat control channel, split into intent (server) and enactment (worker):

- **Ownership — server owns the intent.** A cancel is `OperationService.cancel(operation_id)` (this makes Performance the **first real caller** of the `cancel()` path ADR-0009 §2.5 flagged as dormant). It records cancel-requested state against the operation; the server never reaches into the worker.
- **Observation — worker observes at the next heartbeat.** The heartbeat response for the worker currently bound to that operation returns `cancel_requested: true`. Observation latency is therefore bounded by one heartbeat interval — the deliberate, accepted cost of the pull model.
- **Enactment — worker kills the process group.** On observing the flag (or on local timeout, §4.4/§4.7), the Runner terminates the **entire process group** (`SIGTERM` → grace → `SIGKILL`), never just the parent — preventing orphaned JMeter children (orphan count is a health metric, §2.3, so a leak is visible).
- **Terminal report.** The worker then reports the operation as **cancelled** (or **failed** on timeout), destroys the workspace, and returns to idle. The server transitions the operation to `CANCELLED`/`FAILED` and releases the worker.
- **Timeout behaviour.** Two independent kill triggers converge on the same process-group termination: the **policy timeout** (`ExecutionPolicy.timeout`, enforced *locally* by the Runner — authoritative, because only the worker sees the live process) and **server cancellation** (observed via heartbeat). A worker that has gone silent is handled by the existing sweep, not by cancellation.

### 4.4 Server / Worker / Runtime / Runner Boundaries

Four responsibilities, four owners, one direction of control. This is the layering the ARE asked to be made explicit.

| Boundary | Owns | Must never |
|---|---|---|
| **Server orchestration** (mcp-server: dispatcher, pool, registry, `OperationService`, plan store, artifact store) | queue reuse, assignment, operation-lifecycle transitions, cancellation *intent*, version gating (§4.8), worker auth (§4.9), durable plan/artifact storage | execute an engine; call `subprocess`; see unredacted artifacts |
| **Worker** (long-lived process) | register/heartbeat/pull/report loop, the **one-active-job** guarantee, workspace lifecycle, health reporting, cancellation *enactment*, statelessness between jobs | run two jobs at once; retain state across jobs; expose an inbound port |
| **Runtime** (worker-side execution-lifecycle manager, engine-neutral) | the per-operation lifecycle: create workspace → write plan → validate → invoke Runner → collect → redact → hand off for persistence → confirm → cleanup → reset | know JMeter specifics; build CLI flags; call `subprocess` |
| **Runner** (engine adapter — JMeter) | build `jmeter -n` args, launch the **process-group** subprocess, enforce timeout, enact cancellation, capture stdout/stderr + exit code, collect raw artifacts | schedule; touch the queue; decide policy; persist anything |

The dispatch loop differs from ZAP **by exactly one step and no more**: ZAP's dispatcher assigns *and then drives* the worker (`handler.execute(...)`, push); the Performance dispatcher assigns *and stops* — execution is pulled and run by the worker. The ADR-0009 H1 neutral execution contract (`Runtime → Runner`) therefore lives **inside the worker**; the server side uses the assignment + report contract above, not an `execute()` handler. Everything else — registry, pool, scheduler, heartbeat, sweep, the Operations queue — is the ZAP model reused.

### 4.5 Plan Transport & Lifecycle

- **Ownership.** The server owns the **canonical** validated plan. A plan becomes canonical only after JMX whitelist validation (§5 S1) passes — an invalid plan is never stored and never assignable.
- **Storage.** The plan lives in a **server-owned plan store**, referenced by the operation (the operation record holds a reference, not the bytes). The store is a persistence detail behind the DAO boundary (local blob or object store); the architecture requires only that it is durable and server-owned. `generate_performance_plan` writes here; `execute_performance_test` references an existing plan or supplies one that is validated then written here.
- **Delivery.** The worker receives the plan **in the Pull-Assignment response** (§4.2) — never via a shared filesystem. The worker writes an **ephemeral copy** into the per-operation workspace.
- **Cleanup.** The workspace copy is destroyed with the workspace (§4.6, INV5). The canonical plan's retention is governed by `ExecutionPolicy.artifact_retention`'s sibling plan-retention setting (server-side), independent of any worker.

### 4.6 Artifact Transport, Persistence & Ordering

Transport is over the **worker-initiated Report channel**, not a shared Docker volume — this keeps the worker inbound-channel-free, avoids coupling the design to a Docker volume layout (§7 keeps Docker as infrastructure), and carries forward unchanged to Kubernetes pods later.

Strict ordering, identical on success and failure paths:

```
collect (Runner) → REDACT (Runtime, on the worker) → transport via Report → PERSIST (server, durable) → confirm → CLEANUP workspace (worker)
```

- **Redaction ordering (worker-side, first).** Artifacts are redacted (§5 S4) by the Runtime **before they leave the worker**. Raw secrets therefore never cross the worker boundary and the server never receives, persists, or logs them (INV4/INV10).
- **Ownership & durability.** The worker owns artifacts *transiently* (in-workspace); the server owns them *durably* once its artifact store confirms the write. Durability is defined as "the store acknowledged"; only then is the operation `COMPLETED`.
- **Cleanup ordering (last, unconditional).** Workspace destruction happens **after** persistence is confirmed, and happens **regardless of outcome** (INV5). If persistence fails, the operation is `FAILED`, the workspace is still destroyed, and the artifacts are lost — the accepted **at-most-once** semantic (no retry, consistent with 0009 §2.5). This is a deliberate consequence of the warm-worker + no-retry model, not an oversight.
- **Worker responsibilities:** collect, redact, transport, await confirmation, cleanup. **Server responsibilities:** authenticate, receive, persist durably, confirm, associate with the operation, serve results via the existing history API.

### 4.7 Execution Policy — Architectural Contract

`ExecutionPolicy` is a server-resolved, versioned value object attached to an operation and delivered to the worker with its assignment (§4.5). It is the single carrier of *how* an operation may run. **This ADR fixes the contract's shape, not its values** — no numeric defaults are decided here (deferred to implementation/config).

| Policy field (architectural) | Governs | Enforced by |
|---|---|---|
| `timeout` | max wall-clock per operation | Runner (local, authoritative) |
| `memory`, `cpu` | resource ceilings for the engine process | Worker/Runner (process/container limits) |
| `network_policy` | allow/deny egress rules (§5 S3) | Worker; **fail-closed** on unknown rules |
| `workspace_lifetime` | that the workspace is ephemeral and destroyed post-persist | Runtime (INV5) |
| `artifact_retention` | how long persisted artifacts (and canonical plan) are kept | Server |
| `redaction_policy` | the extensible set of sensitive keys to strip (§5 S4) | Runtime (worker-side, pre-transport) |

- **Resolution & ownership.** The server resolves the effective policy per operation (request ∪ configured defaults) before assignment; the worker enforces the runtime-facing fields and never widens them.
- **Security invariants are not tunable defaults.** Blocking the cloud metadata endpoint (§5 S3) and rejecting unknown JMX elements (§5 S1) are **invariants** (§4.11), not policy values a caller may relax.
- **Extensibility.** The policy is an **open, versioned** structure: new fields are additive; an unknown *security-relevant* field fails closed, an unknown *non-security* field is ignored with a warning. This is the seam by which a future engine (k6/Gatling) contributes engine-specific limits without changing the Service or the queue.

### 4.8 Worker Version Compatibility

- **Reporting.** Every worker reports its `version` at Register and on each Heartbeat (the field already exists in the worker schema).
- **Minimum compatible version.** The server holds a configured `min_compatible_version` and returns it in the Register response so a worker learns its own standing.
- **Dispatcher behaviour on mismatch.** A worker below `min_compatible_version` stays **registered and visible** (for observability) but is **never schedulable** — the scheduler treats version-incompatibility exactly like unfit health (§2.3): present, not assignable. An operation is **never split across workers**, so mixed versions never co-execute one operation.
- **Upgrade strategy.** Rolling **drain-and-replace**, reusing the existing `DRAINING → OFFLINE` lifecycle: mark old-version workers draining (they finish/cancel their current op, take no new work), start new-version workers alongside, retire the drained ones. The warm-worker + pull model makes this zero-in-flight-loss without any new machinery.

### 4.9 Worker Authentication & Trust Boundary

- **Model.** The worker API (Register/Heartbeat/Pull/Report) is authenticated with a **deployment-provisioned worker credential**, mirroring the trust posture ZAP already uses for its worker API key. The architectural requirements are: **authenticated** (only a credentialed worker may register, pull, or report), **least-privilege** (a worker may act only on its *own* current assignment — it cannot pull another worker's plan or report another worker's result), and **revocable**. The concrete scheme (static token, mTLS, signed short-lived token) is an implementation choice, deliberately not fixed here.
- **Trust boundary.** The server trusts an *authenticated* worker to execute an *already-validated* plan and to return *redacted* artifacts. It does **not** extend trust to worker-reported content for posture claims beyond what validation (§5 S1) and redaction (§5 S4) guarantee — forged metrics or artifacts from a compromised worker are a G3 concern, which is why plans are validated server-side *before* assignment (defense in depth) and why authentication gates the Report channel (to keep unauthenticated actors from injecting results).

### 4.10 Runtime Terminology (disambiguation, not redesign)

The word "runtime" is overloaded in the codebase and the ARE flagged it. Resolved by fixing meaning, not by renaming the accepted abstraction:

- Within the Performance capability, **"Runtime" always means the worker-side execution-lifecycle manager** defined in §4.4 (`services/performance/runtime/`). This is the accepted abstraction and keeps its name.
- The ZAP module `integrations/owasp_zap/runtime.py` means something different — *process-wide pool-singleton wiring*. It is **not** renamed (out of scope; ZAP untouched), but the Performance capability will **not** replicate that naming: Performance's pool-singleton wiring is owned by the **composition root** (`bootstrap`), so there is no `performance/…/runtime.py` wiring module to collide with the lifecycle meaning. Result: exactly one meaning of "Performance Runtime."

### 4.11 Architecture Invariants (guarantees)

These hold for every Performance operation and are the acceptance backbone for implementation review:

- **INV1** A worker executes **at most one** active operation at a time.
- **INV2** A workspace belongs to **exactly one** operation and is **never reused** across operations.
- **INV3** A plan is **validated** (JMX whitelist, unknown-rejected) **before** it is stored, assigned, or executed.
- **INV4** Artifacts are **redacted on the worker before they leave it**; the server never receives unredacted data.
- **INV5** Workspace **cleanup always occurs**, **after** persistence is confirmed, on success **and** failure paths.
- **INV6** Workers hold **no business state** between operations (stateless contract).
- **INV7** `subprocess` is invoked **only by the Runner** (engine adapter) — never by Server, Service, or Runtime.
- **INV8** The engine process runs in **its own process group**; timeout or cancellation kills the **whole group**.
- **INV9** **All** worker↔server communication is **worker-initiated**; the worker exposes no inbound channel.
- **INV10** The server **never persists or logs unredacted secrets**.
- **INV11** A worker below `min_compatible_version` is **never assigned** an operation.

---

## 5. Security Model (first-class, not additive)

Guardrail Hub's value is trustworthy posture (guardrails G2/G3), so a JMeter plan is treated as an **executable document**, not data.

- **S1 — JMX whitelist validation.** Uploaded plans are validated against an allow-list of safe elements. Reject scripting/native-execution elements including (non-exhaustively) BeanShell, JSR223 (all languages), Java Sampler, and OS Process Sampler. **Unknown elements are rejected by default** — the list is a whitelist, not a blacklist. Validation happens before a plan is ever enqueued or written to a worker workspace.
- **S2 — Non-root worker, workspace-only writes.** The worker container runs as a dedicated non-root user with write permission confined to its per-operation workspace. Sensitive environment variables are not shared into the worker.
- **S3 — Execution policy, not hardcoded network rules.** Block the cloud metadata endpoint `169.254.169.254` **by default**. Do **not** hardcode blocking of RFC1918 ranges — enterprises legitimately load-test internal services. Network restrictions are expressed through configurable **execution policies**, resolved per operation, not fixed in code.
- **S4 — Artifact redaction before persistence.** Redact sensitive values (Authorization, Proxy-Authorization, Cookie, Set-Cookie, X-API-Key, X-Amz-Security-Token, JWT, Basic auth) from artifacts before they are persisted. Secrets are never written into reports (guardrail G1).
- **S5 — Process-group isolation.** The `jmeter -n` process runs in its own process group; timeout or cancellation kills the **entire group**, never just the parent, to prevent orphaned child processes. Orphan-process count is surfaced in the heartbeat (§2.3) so a leaking worker is visible to the scheduler.
- **S6 — Stateless worker + mandatory cleanup** (D6). No execution data accumulates on the worker filesystem; workspace destruction is guaranteed regardless of outcome.

---

## 6. Scope of This Capability (and explicit non-goals)

**In scope:** the Performance Engine, its Runtime, the warm Worker, Docker integration, a test-plan-generation *foundation*, and a performance-execution *foundation* — plus the security primitives in §5.

**Explicitly out of scope** (rejected here so they are not smuggled in):

- ❌ LLM / AI analysis of results — belongs to a future Intelligence layer.
- ❌ Performance recommendations or optimisation suggestions.
- ❌ A multi-engine framework or any k6/Gatling/Locust code (§2.4).
- ❌ Full worker-recycling *policy* — the worker exposes recycling **extension points** (recycle-after-uptime / recycle-after-N-jobs) without the policy logic wired.
- ❌ A shared ZAP+Performance worker-pool extraction (§8 records when to revisit).
- ❌ Retries — consistent with 0009 §2.5, resubmission stays a user action.

---

## 7. Phased Plan (verifiable; each phase ships independently)

**Phase 0 — Execute ADR-0009 H1–H4 (the "decouple first" step).** H3 delete unused `ExecutionStrategy` members; H2 remove `pydantic.BaseModel` from the handler contract; H1 replace the `ZapWorkerInfo` parameter with a neutral execution-context object; H4 inject + settings-bound the two module-level thread pools.
→ *Verify:* full existing suite green + `python .ai/tools/aios.py check`; behaviour byte-identical for all three ZAP tools. **This phase edits ZAP code and is the one checkpoint that must be reviewed before proceeding.**

**Phase 1 — Engine seam + JMeter runner + security primitives.** `PerformanceRunner` protocol + neutral DTOs; `jmeter_runner.py` (CLI args, subprocess in own process group, timeout, cancel = kill group, stdout/stderr, exit code, artifact collection); `jmx_validator.py` (whitelist, unknown-rejected); workspace manager (isolated per-op, guaranteed cleanup); redaction util.
→ *Verify:* unit tests per component — a JMX with a JSR223 element is rejected; a timeout kills the whole process group (assert no orphans); cleanup runs on a forced failure; redaction removes every S4 header. No distributed wiring yet.

**Phase 2 — Warm worker subsystem + queue wiring.** `PerformanceWorkerRegistry`/`PoolManager`/`Scheduler`/`Dispatcher` on the neutral contract, health-aware heartbeat, reusing the Operations queue; the long-lived `PerformanceWorker` loop (register → heartbeat → pull → run via runtime → report → cleanup → idle); worker-facing internal endpoints (pull assignment, report result); execution-policy resolution.
→ *Verify:* an enqueued perf operation is assigned only to a healthy idle worker; a worker that stops heart-beating mid-job has its operation marked FAILED by the sweep (mirrors ZAP); no worker runs two jobs at once.

**Phase 3 — JMeter worker Docker image + MCP tool stubs.** Dedicated non-root warm worker image running the worker loop with `jmeter` present; compose profile; register `generate_performance_plan` and `execute_performance_test` (structure + validation wiring only — no analysis).
→ *Verify:* image builds; worker registers and heartbeats; an end-to-end smoke operation runs `jmeter -n`, produces JTL+HTML+logs+metadata, redacts, and cleans its workspace.

---

## 8. Consolidation Trigger (when to revisit D4/D5, as a new Decision)

Following 0009's discipline of naming the reopening condition rather than acting on anticipation:

- **Revisit D4 (shared worker-pool extraction)** when the ZAP and Performance worker subsystems have demonstrably duplicated *non-trivial* logic that has drifted or must change in lockstep — i.e. evidence of real duplication, not the mere fact that two registries exist. Two implementations now make the *shape* knowable; a third worker model, or a lockstep change, makes extraction *worth* it.
- **Revisit D5 (engine framework)** the day a second performance engine (k6/Gatling/Locust) has actual code. That is when the seam's assumptions are tested against reality and a framework can be derived from two implementations instead of imagined from one.

Until then: build the capability, keep the seam thin, and let the ZAP and Performance subsystems stay parallel.

---

## 9. Risks

- *Medium* — **Duplication between ZAP and Performance worker infra (D4).** Accepted deliberately over a premature extraction; bounded by §8's explicit revisit trigger and by both subsystems sharing the H1 neutral contract and the single Operations queue.
- *Medium* — **Pull-delivery adds a worker→server round-trip** the ZAP push model avoids. Justified: it is the direct consequence of the chosen "no inbound HTTP on the worker" constraint, which is itself a security simplification (the worker opens no listening port).
- *Low* — **The engine seam proves slightly wrong when engine #2 arrives.** Reduced by keeping the seam minimal (§2.4): a small protocol is cheap to reshape; a framework is not.
- *Low* — **Phase 0 touches ZAP.** Contained by H1–H4 being behaviour-preserving and gated behind the full suite + `aios check`, and by the explicit review checkpoint in §7.

---

## 10. Decision Record

**Approve** the Performance capability, the warm-worker/queue/local-runtime/pull model, and the minimal engine seam, built on ADR-0009's H1–H4 neutral contract (executed as Phase 0). **Reject** a multi-engine framework and a shared worker-pool extraction for now, with §8 recording when each is revisited.

The honest summary: 0009 was right that you cannot abstract over a set of one — and it was right about the fix (decouple the contract) and the reopening condition (a second substrate). JMeter is that substrate. So we do exactly what 0009 licensed: decouple first, then build the capability the second implementation now justifies — while applying the *same* restraint one level down, where performance *engines* are still a set of one. Build the seam; refuse the framework; wait for engine #2.

---

## 11. Architecture Delta (R1 — 2026-07-22 ARE revision)

Every change this revision introduced, why, which ARE finding it closes, and whether it **changes** architectural behaviour or only **clarifies** what was already implied. The test applied: a change is *clarifying* if an engineer following the original §1–§10 could only reasonably build it this way; it is *behavioural* if the original left a real fork now decided.

| # | Change | Section | Resolves (ARE) | Behaviour or clarification |
|---|---|---|---|---|
| Δ1 | Four-call worker protocol (Register / Heartbeat / Pull / Report) + worker lifecycle | §4.2 | MAJOR — undefined pull contract | **Clarifies** — makes the pull model's already-chosen calls explicit; adds no capability |
| Δ2 | Cancellation via heartbeat control channel: server owns intent (`cancel()`), worker enacts (kill process group), latency bounded by one heartbeat | §4.3 | MAJOR — no cancellation path in a no-inbound worker | **Behavioural** — selects the propagation mechanism (heartbeat-response flag) among real alternatives; activates 0009's dormant `cancel()` |
| Δ3 | Server/Worker/Runtime/Runner boundary table; server assigns-and-stops (no `execute()`); H1 contract lives worker-side | §4.4 | MAJOR — server-side dispatch contract for a pull worker undefined | **Clarifies** — resolves *where* each accepted contract lives; the one-step divergence from ZAP was already implied by "pull" |
| Δ4 | Plan transport: server-owned canonical store, delivered in Pull response, ephemeral workspace copy, no shared FS | §4.5 | MAJOR — plan transport unspecified | **Behavioural** — decides report-channel delivery over shared volume |
| Δ5 | Artifact transport + strict ordering: collect→redact(worker)→transport→persist(server)→confirm→cleanup; at-most-once | §4.6 | MAJOR — artifact transport/persistence/ordering unspecified | **Behavioural** — fixes the ordering and the report-channel (not shared-volume) transport, and names the at-most-once semantic |
| Δ6 | `ExecutionPolicy` contract shape (fields as concepts, no numeric defaults; security items are invariants not tunables; open/versioned) | §4.7 | MINOR — policy named but unshaped | **Clarifies** — shapes the contract; explicitly defers all values |
| Δ7 | Worker version compatibility: report / `min_compatible_version` / unschedulable-on-mismatch / drain-and-replace | §4.8 | (New prereq raised in review) | **Behavioural** — adds a compatibility rule; reuses existing `DRAINING` lifecycle, no new machinery |
| Δ8 | Worker auth model: authenticated, least-privilege, revocable; trust boundary stated; scheme deferred | §4.9 | MINOR/security — worker auth undecided | **Behavioural** — fixes the trust model; leaves the mechanism to implementation |
| Δ9 | "Runtime" disambiguation: Performance Runtime = worker-side lifecycle; Performance wiring owned by bootstrap (no `runtime.py`); ZAP untouched | §4.10 | MINOR — "runtime" overloaded | **Clarifies** — naming discipline only; no abstraction renamed |
| Δ10 | Eleven architecture invariants (INV1–INV11) as acceptance guarantees | §4.11 | Review request — invariants as guarantees | **Clarifies** — promotes scattered rules into a single checkable list |

Scope discipline: no new capability, engine, layer, or abstraction was added; Δ4/Δ5/Δ8 are the only new *decisions* (transport, ordering, auth model), and each was a fork the ARE explicitly flagged, not a scope expansion. The engine seam stayed minimal; the multi-engine framework and the shared worker-pool extraction remain rejected/deferred exactly as in §1/§8.

## 12. Implementation Readiness Assessment

**READY.**

The three MAJOR ambiguities the ARE required to be closed before coding are closed with concrete, engineer-facing contracts: the pull worker protocol and lifecycle (§4.2), cancellation propagation in a no-inbound worker (§4.3), the server/worker/runtime/runner boundary split (§4.4), and both plan and artifact transport with strict redaction/cleanup ordering (§4.5–§4.6). The remaining review items — execution-policy shape (§4.7), version compatibility (§4.8), worker auth (§4.9), runtime terminology (§4.10), and invariants (§4.11) — are resolved at the architectural level while correctly deferring implementation values (policy defaults, auth scheme, storage backend) that are not architecture.

No accepted decision changed; this revision only removed ambiguity. Contingent on ratifying ADR-0009 (Accept H1–H4) as the Phase 0 precondition, engineering may begin immediately: Phase 1 primitives depend only on §4.4/§4.6/§4.11 (all now fixed), and Phases 2–3 depend only on §4.2/§4.3/§4.5/§4.8/§4.9 (all now fixed). There is no remaining architectural fork on the critical path.
