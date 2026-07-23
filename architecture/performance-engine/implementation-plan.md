# Performance Engine — Implementation Plan (Phase 0 → Phase 3)

**Date:** 2026-07-22 · **Status:** Active — engineering may begin.
**Canonical architecture (do not re-decide here):** [ADR-0009 (Accepted)](../../.ai/decisions/0009-execution-capability.md) and [ADR-0010 (Accepted)](../../.ai/decisions/0010-performance-engine-capability.md). Where this plan and an ADR ever disagree, the ADR wins — this document is execution sequencing only, not architecture.

## Purpose

Translate the accepted Performance Engine architecture into phased, independently shippable engineering work. This document holds *tasks, targets, sequencing, and acceptance criteria*; it deliberately contains **no new architectural decisions**. Every "why" lives in ADR-0010; every reference below points there by section (e.g. §4.6) rather than restating it.

## Conventions (apply to every phase)

- **Definition of done, per phase:** the phase's acceptance criteria pass **and** the full existing test suite is green **and** `python .ai/tools/aios.py check` passes. No phase merges red.
- **Traceability:** every unit of work cites the ADR-0010 invariant (INV1–INV11) or contract section (§4.2–§4.11, §5) it satisfies. The traceability matrix at the end must stay complete.
- **Scope fence (ADR-0010 §6):** no LLM/AI analysis, no recommendations/optimisation, no k6/Gatling/Locust code, no shared ZAP+Performance worker-pool extraction, worker-recycling as *extension points only*. A change outside this fence is out of scope for these phases.
- **Non-negotiable seam (ADR-0010 §4.4, INV7):** `subprocess` appears **only** in the JMeter Runner. Any `subprocess` reference elsewhere fails review.

---

## Phase 0 — Execute ADR-0009 H1–H4 (neutral execution contract)

**Goal:** remove the ZAP-and-framework coupling from the generic execution contract so the Performance path never inherits `ZapWorkerInfo`. This is the only phase that edits existing ZAP code and is the **explicit review checkpoint** (ADR-0010 §7).

**Work (in this order — each step independently shippable, behaviour-preserving):**

1. **H3 — delete dead strategy members.** Remove `PARALLEL`, `BATCH`, `FAN_IN` from `ExecutionStrategy` (`services/tools/owasp_zap/execution/execution_strategy.py`); the dispatcher reads only `requires_worker`.
2. **H2 — remove the framework type from the contract.** Drop `pydantic.BaseModel` from the handler contract in `execution/handler.py`; the contract needs serialize/deserialize behaviour, not a base class.
3. **H1 — neutral execution context.** Replace the `worker: Optional[ZapWorkerInfo]` parameter in `ZapOperationHandler.execute` with a neutral, tool-owned context object. For `api_scan`/`api_scenario` the context still carries the assigned worker; for `api_suite` it stays empty.
4. **H4 — consolidate concurrency ownership.** Inject and settings-bound the two module-level `ThreadPoolExecutor`s (`api_scanner.py`, `scan_api_scenario.py`), wired from `bootstrap.py` exactly as the dispatcher's orchestration executor already is.

**Targets:** `services/tools/owasp_zap/execution/{execution_strategy,handler,registry}.py`, the three handler factories, `dispatcher.py`, `api_scanner.py`, `scan_api_scenario.py`, `bootstrap.py`, and their tests.

**Acceptance:**
- All three ZAP tools behave **byte-identically** (existing suite green, no snapshot/report drift).
- The generic execution contract imports **no** ZAP schema and **no** `pydantic`.
- No module-level thread pool remains in the two scan services.
- `aios check` PASS.

**Gate:** ratified review of this phase before Phase 1 begins (it is the one phase touching working ZAP code).

---

## Phase 1 — Engine seam + JMeter runner + security primitives (unit-tested)

**Goal:** build the worker-side execution building blocks in isolation. No distributed wiring yet — everything here is unit-testable without a running worker.

**Work & targets:**

- **Engine seam (ADR-0010 §4.4, D5).** `services/performance/engine/` — `PerformanceRunner` protocol + neutral `ExecutionRequest` / `ExecutionResult` / `ArtifactSet` DTOs. DTOs carry **no** JMeter-isms (no `.jmx`/`.jtl`/`-n -t`).
- **JMeter Runner (§4.4 Runner row, INV7/INV8).** `integrations/jmeter/jmeter_runner.py` — build `jmeter -n` args, launch the subprocess in **its own process group**, enforce `ExecutionPolicy.timeout` locally, enact cancellation by killing the **whole group** (`SIGTERM`→grace→`SIGKILL`), capture stdout/stderr + exit code, collect raw artifacts.
- **JMX whitelist validator (§5 S1, INV3).** `integrations/jmeter/jmx_validator.py` — allow-list of safe elements; reject BeanShell, JSR223 (all langs), Java Sampler, OS Process Sampler; **unknown element ⇒ reject**.
- **Runtime lifecycle manager (§4.4 Runtime row).** `services/performance/runtime/` — the engine-neutral per-operation lifecycle: create workspace → write plan → validate → invoke Runner → collect → redact → hand off → confirm → cleanup → reset. Knows no JMeter specifics.
- **Workspace manager (§4.6, INV2/INV5).** isolated per-operation workspace; **guaranteed** destruction on success and failure.
- **Redaction (§5 S4, INV4/INV10).** `services/performance/redaction/` — strip Authorization, Proxy-Authorization, Cookie, Set-Cookie, X-API-Key, X-Amz-Security-Token, JWT, Basic auth; extensible key set.
- **Policy shape (§4.7).** `schemas/performance/` — `ExecutionPolicy` value object (fields only, **no** numeric defaults).

**Acceptance (unit tests):**
- A JMX containing a JSR223/BeanShell/OS-Process element is **rejected** (INV3).
- A simulated over-timeout run kills the entire process group — asserted **no orphan** children remain (INV8).
- Workspace cleanup runs on a **forced failure** path, not only success (INV5).
- Redaction removes **every** S4 key from a sample artifact; the server-facing output contains no secret (INV4).
- `ExecutionResult`/`ArtifactSet` reference no JMeter-specific symbol (seam purity, extensibility guard).
- `aios check` PASS.

**Depends on:** Phase 0 (uses the neutral contract). Independent of Phases 2–3.

---

## Phase 2 — Warm worker subsystem + queue wiring

**Goal:** stand up the pull-based warm-worker orchestration on the reused Operations queue, mirroring the ZAP registry/pool/scheduler/dispatcher shapes but engine-neutral and health-aware.

**Work & targets:**

- **Performance worker registry/pool/scheduler (§4.2, §2.3).** `integrations/performance/` — registry (self-register + heartbeat with **health metrics**: status, version, current job, CPU, mem, disk, workspace size, orphan count, last cleanup), pool manager, and a `WorkerScheduler` implementation that treats unfit health **and** version-incompatibility as not-schedulable (§4.8, INV11). Pool-singleton wiring owned by the **composition root**, not a `runtime.py` module (§4.10).
- **Performance dispatcher (§4.4).** assigns a `QUEUED` performance operation to an idle, healthy, compatible worker and **stops** (no `execute()` — pull model); reuses the existing heartbeat-timeout **sweep** to fail orphaned operations. Concurrency injected + settings-bound (mirrors H4).
- **Worker-facing endpoints (§4.2, §4.9).** `routers/public/performance_worker_router.py` (its own namespace, e.g. `/performance/workers`, **not** ZAP's `/workers`) — Register, Heartbeat (response carries `assignment{op}` and `cancel_requested`), Pull-Assignment (returns validated plan + resolved policy), Report (completion/failure/cancellation). Authenticated, least-privilege, revocable (§4.9).
- **Long-lived worker loop (§4.2, INV1/INV6/INV9).** `services/performance/worker/` — register → heartbeat(health) → on assignment pull → run via Runtime → report → cleanup → reset → idle. Exactly one active job; stateless between jobs; no inbound channel.
- **Cancellation (§4.3).** server intent via `OperationService.cancel()` (first real caller); worker observes `cancel_requested` on heartbeat and kills the process group.
- **Plan store (§4.5).** server-owned canonical plan store behind the DAO boundary; delivered in the Pull response; ephemeral workspace copy.
- **Execution-policy resolution (§4.7).** server resolves effective policy per operation before assignment; metadata endpoint blocked by default; RFC1918 **not** hardcoded (§5 S3).

**Acceptance:**
- An enqueued performance operation is assigned only to an idle, healthy, version-compatible worker (INV1, INV11).
- A worker that stops heart-beating mid-job has its operation marked FAILED by the sweep (parity with ZAP).
- A cancel request reaches a running worker within one heartbeat interval and terminates the process group (§4.3).
- No worker ever holds two operations; no state carries across operations (INV1/INV6).
- Artifact flow honours ordering: redact(worker) → persist(server) → confirm → cleanup (INV4/INV5).
- `aios check` PASS.

**Depends on:** Phases 0 + 1.

---

## Phase 3 — JMeter worker Docker image + MCP tool stubs

**Goal:** package the worker and expose the two tools, keeping Docker as infrastructure (§7).

**Work & targets:**

- **Worker image.** dedicated non-root, workspace-write-only image that runs the **long-lived worker loop** with the `jmeter` binary present (reuse the accepted `docker/jmeter/` base); each job launches a fresh `jmeter -n`. Compose profile wiring; no ephemeral-per-job containers.
- **MCP tool stubs (§6).** `routers/mcp/jmeter_router.py` + `schemas/tools/jmeter/` — `generate_performance_plan` (generate/validate/prepare plan; validation at this boundary, §5 S1) and `execute_performance_test` (enqueue execution; validation at this boundary too; returns operation id, then deterministic metrics via the existing history API). **No** analysis, **no** LLM.
- **Docs.** update `mcp-server/docs/jmeter/` from "infrastructure only" to the runtime model.

**Acceptance:**
- Image builds; worker registers and heartbeats with health; runs as non-root with writes confined to its workspace (§5 S2).
- End-to-end smoke operation: enqueue → assign → pull → `jmeter -n` → JTL+HTML+logs+metadata → redact → persist → workspace destroyed (INV2/INV4/INV5).
- Both tools validate their plan input before enqueue (§5 S1, at both boundaries).
- `aios check` PASS.

**Depends on:** Phases 0 + 1 + 2.

---

## Traceability Matrix (ADR → phase → verification)

| ADR-0010 contract / invariant | Phase | Verified by |
|---|---|---|
| §4.4 seam + boundaries; INV7 (subprocess only in Runner) | 1 | seam-purity test; review grep for `subprocess` |
| §5 S1 JMX whitelist; INV3 | 1 (validator), 3 (tool boundary) | reject-scripting-element unit test; tool-boundary test |
| §4.6 redaction ordering; §5 S4; INV4/INV10 | 1 (redactor), 2 (ordering) | redaction unit test; artifact-flow ordering test |
| §4.6 cleanup ordering; INV2/INV5 | 1 (workspace), 2 (post-persist) | forced-failure cleanup test; e2e smoke |
| INV8 process-group kill | 1 | over-timeout no-orphan test |
| §4.2 pull protocol + lifecycle; INV1/INV6/INV9 | 2 | worker-loop tests; one-active-job test |
| §4.3 cancellation | 2 | cancel-within-one-heartbeat test |
| §4.5 plan transport | 2 | pull-delivers-plan test |
| §4.8 version compatibility; INV11 | 2 | incompatible-worker-not-scheduled test |
| §4.9 worker auth | 2 | unauthenticated-rejected test |
| §4.7 execution policy shape | 1 (shape), 2 (resolution) | policy value-object test; resolution test |
| §7 Docker as infrastructure; §5 S2 non-root | 3 | image build; non-root/workspace-only check |
| §6 two MCP tools (no analysis) | 3 | tool registration + boundary tests |
| ADR-0009 H1–H4 neutral contract | 0 | ZAP suite byte-identical; no ZAP/pydantic in contract |

## Out of scope for these phases (ADR-0010 §6, §8)

LLM/AI analysis · performance recommendations/optimisation · k6/Gatling/Locust code · shared ZAP+Performance worker-pool extraction · full worker-recycling policy (extension points only) · automatic retries.
