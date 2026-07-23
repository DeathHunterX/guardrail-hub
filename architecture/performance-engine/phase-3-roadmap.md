# Phase 3 — Implementation Roadmap (Integration / Wiring Only)

**Status:** ratified P3AR; awaiting go-ahead to implement C3.1. **Scope:** integration and composition only — no behavioural change, no subsystem modification, no ADR change. AD-1 and AD-2 remain deferred (see [architecture-debt.md](architecture-debt.md)). Canonical architecture: [ADR-0010 (R2)](../../.ai/decisions/0010-performance-engine-capability.md).

Phase 3 wires the ratified Phase 2 components into the running app and packages the worker. It proceeds `C3.1 → C3.7`. Every commit is small and independently reviewable.

## Cross-cutting validation gates (added by owner review)

Three architectural validation gates apply across Phase 3, each landing in the commit noted. They are **validation-only** (tests) — they enforce the accepted design, they do not change it.

### Gate A — Composition-Root Singleton Integrity  (lands in C3.4)
Verify that **all** Phase 2 subsystem singletons are instantiated **exactly once** and shared everywhere — not only the Registry. At minimum, assert instance identity across the graph for:
- Registry, Scheduler, Pool, Dispatcher, WorkerCoordinator.

Concretely: the Dispatcher's pool is the wiring Pool; the Pool's registry and the Coordinator's registry are the wiring Registry; the Scheduler in the Pool is the wiring Scheduler; there is one Dispatcher and one Coordinator. Prevents accidental duplicate singleton graphs (risk R-A, now extended from Registry-only to all five).

### Gate B — OperationType End-to-End Integrity  (server-side portion in C3.6; full chain in C3.7)
An in-process end-to-end test proving `PerformanceOperationType` is **never transformed, rewritten, or re-inferred** along the complete path:

```
MCP Tool → OperationService → DAO → Dispatcher → Assignment → Worker → Report → Persistence
```

The value may be **read** at any hop (e.g. the dispatcher's scoped read, the tool's stamping) but must be **byte-identical** at every hop where it appears. This is the integration-level proof of **INV13** (immutable engine identity). Recorded operation-type at each stage must all equal the value the tool stamped.

### Gate C — Composition-Root Purity  (lands in C3.4)
An **AST-based** test (mirroring the seam/scheduler/dispatcher purity tests) proving that construction of subsystem objects happens **only inside the composition root** (`integrations/performance/wiring.py` + `bootstrap.py`). The following must never be *instantiated* outside wiring/bootstrap in `app/`:
- Registry, Scheduler, Pool, Dispatcher, WorkerCoordinator.

Every other module must receive them by dependency injection only. (Tests may construct them directly — the scan targets `app/`, not `tests/`.)

**Implementation note (grounded):** the scan MUST be **import-origin-aware**, not bare-name. The class names `RoundRobinScheduler` and `WorkerScheduler` are **shared** with the ZAP subsystem (`app/integrations/owasp_zap/scheduler.py`; ZAP constructs `RoundRobinScheduler()` in its own composition root `owasp_zap/runtime.py`). A bare-name match would false-positive on ZAP's legitimate construction. Gate C must resolve each constructed name to its import source and only flag classes imported from `app.integrations.performance.*` / `app.services.performance.*` (the four uniquely-named ones — `PerformanceWorkerRegistry`, `PerformancePoolManager`, `PerformanceDispatcher`, `WorkerCoordinator` — plus the Performance `RoundRobinScheduler` resolved by its `app.integrations.performance.scheduler` origin). ZAP's parallel scheduler is out of scope for this gate.

### Gate D — Dependency-Direction Purity  (lands in C3.4)
An **AST/import** test proving the composition root is a **dependency sink only**. No subsystem module (`app/services/performance/**`, `app/integrations/performance/**` except the wiring module itself, `app/integrations/jmeter/**`) may import `integrations.performance.wiring`, `bootstrap`, or any other composition-root module. The direction is strictly `Composition Root → Subsystem`, never the reverse. *Grounded baseline: clean today (no subsystem module imports a composition root).*

### Gate E — Configuration Ownership  (lands in C3.4)
An **AST/import** test proving configuration concerns live **only** in the composition root (`wiring.py` + `bootstrap.py`). Subsystem modules (Runtime, Worker, Dispatcher, Scheduler, Registry, Pool, Runner, Validator, redaction, workspace, coordinator, persistence, clients) must **never**: read `Settings` (`app.core.config`), construct concrete infrastructure implementations (the concrete stores, senders, clients, executors, or the subsystem singletons), create singletons, or assemble their own dependencies. They receive everything by injection. *Grounded baseline: clean today (no subsystem module reads `Settings` or constructs infrastructure).*

---

## Commits

**Common gates (every commit):** full suite green; coexistence guard green; ZAP suite byte-for-byte green; `aios check` PASS; `git diff` shows **no modification** to any frozen subsystem file (runtime / worker / dispatcher / scheduler / registry / pool / engine + port contracts) — wiring/additions only.

### C3.1 — Type + settings foundation
`schemas/performance/operation_type.py` (`PerformanceOperationType`, e.g. `performance_test`); settings (`PERFORMANCE_WORKER_TOKEN`, queue-poll / heartbeat-sweep / heartbeat-timeout intervals, optional `min_compatible_version`).
- *Acceptance:* enum + settings import; the dispatcher's supported-type set is derivable from the enum (single source of truth, risk R-B).
- *Gate:* enum unit test.

### C3.2 — Concrete PlanStore + ReportStore (filesystem-backed)
Implement the existing `PlanStore` / `ReportStore` ports; plans under `data/jmeter/plans/<op_id>`, reports under `reports/jmeter/<op_id>` (mirrors `data/zap` / `reports/zap`).
- *Acceptance:* plan put/get round-trip; report save persists redacted artifacts + metadata; `PlanNotFoundError` on miss.
- *Gate:* store unit tests; the `PlanStore`/`ReportStore` protocols in `worker_api.py` are untouched.

### C3.3 — Worker authentication boundary
A FastAPI dependency verifying `Authorization: Bearer` against `PERFORMANCE_WORKER_TOKEN`, applied in the worker-router factory.
- *Acceptance:* missing/invalid token → 401; valid → passes; coordinator least-privilege (pull-mismatch → 409) still holds (risk R-C).
- *Gate:* auth unit tests (both paths); coordinator logic unchanged.

### C3.4 — Composition root + lifecycle  ▸ **Gates A, C, D, E**
`integrations/performance/wiring.py` singletons (Registry/Scheduler/Pool); `bootstrap.build_performance_coordinator` + `build_performance_dispatcher`; `startup.py` starts the dispatcher (gated on `DATABASE_PROVIDER`, risk R-D); `main.py` mounts the authed router + lifespan stop.
- *Acceptance:* **Gate A** — all five singletons instantiated once and shared (identity asserted); **Gate C** — AST purity: the five classes constructed only in wiring/bootstrap (import-origin-aware); **Gate D** — no subsystem module imports the composition root (sink-only direction); **Gate E** — `Settings` reads + concrete-infrastructure construction occur only in wiring/bootstrap; `OperationService`-as-`OperationStatusSink` conformance asserted (risk R-E); app boots in test; router exposes the four routes.
- *Gate:* Gate-A identity test + Gate-C construction-purity test + Gate-D direction test + Gate-E config-ownership test + conformance assertion; diff limited to wiring/bootstrap/startup/main.

### C3.5 — MCP tool `generate_performance_plan`
Validate via `JmxPlanValidator` → store in `PlanStore` → return the plan reference. No LLM/analysis.
- *Acceptance:* valid plan stored; scripting/invalid plan rejected with the validator's error.
- *Gate:* tool unit tests.

### C3.6 — MCP tool `execute_performance_test`  ▸ **Gate B (server-side portion)**
Validate → `OperationService.create` with `PerformanceOperationType` → return operation id.
- *Acceptance:* creates a QUEUED op with the correct `operation_type`; an in-process `tool → service → DAO → dispatcher → assignment` test asserting the operation-type is byte-identical at every server-side hop (Gate B, server portion) and that the wired dispatcher assigns it to a registered worker (risk R-B).
- *Gate:* tool + enqueue-dispatch tests incl. the Gate-B server-side assertion.

### C3.7 — JMeter worker image + worker composition + docs  ▸ **Gate B (full chain)**
Worker entrypoint assembling `PerformanceWorker` (JMeter runner/validator + `ReportChannelPersistence` + `WorkspaceManager` + authed `HttpServerClient`/`HttpReportSender` + token); non-root warm `docker/jmeter` worker image running the loop; compose profile; docs.
- *Acceptance:* **Gate B (full)** — an in-process end-to-end over the complete path (`… → Worker → Report → Persistence`) asserts `PerformanceOperationType` is byte-identical from the tool's stamp through to persistence (INV13 integration proof); worker composition assembles and runs the loop; image non-root; documented build/run + verification.
- *Gate:* Gate-B full end-to-end + static validation (compose YAML via PyYAML, Dockerfile review, worker-composition smoke). Note: the sandbox cannot `docker build` (no daemon; Apache mirrors blocked), so the image build is a documented gate for a Docker host, as with the Phase-0 infra.

---

## Constraints (whole phase)
Wire, do not modify — Runtime, Worker loop, Dispatcher logic, Scheduler, Registry, Pool, and all engine/port contracts stay byte-for-byte. INV1–INV13 preserved; coexistence guard green; ZAP untouched beyond §4.12; no LLM/analysis; AD-1/AD-2 remain deferred (no behavioural change enters Phase 3).
