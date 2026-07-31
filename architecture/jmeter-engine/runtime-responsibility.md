# JMeter Engine — Runtime Responsibility Boundaries (Final)

Status: **Final** — decided 2026-07-28.
Resolves: adjustment **A4** (and, for target authorization, **A8**) of the [architecture validation report](architecture-review.md).

---

## 1. First, the naming collision

"Runtime" means two different things in this repository, and a contributor told to "follow the ZAP philosophy" will guess wrong.

- In ZAP, `app/integrations/owasp_zap/runtime.py` is a module of **process-wide singletons** — `registry`, `scheduler`, `pool_manager`. It orchestrates nothing.
- In the JMeter plan, `JMeterRuntime` is the **per-operation orchestrator**: Generate → Validate → Execute → Parse → Persist.

**Decision: keep both names, disambiguated by layer, and state the rule.**

| Path | Meaning |
|---|---|
| `app/integrations/jmeter/runtime.py` | Process singletons — mirrors ZAP exactly (`registry`, `scheduler`, `pool_manager`). Module-level, no class |
| `app/services/tools/jmeter/execution/runtime.py` → `class JMeterRuntime` | The per-operation orchestrator. Application logic, so it lives in `services/` |

The rule, stated once so it generalizes: **`integrations/<tool>/runtime.py` is process wiring; `services/tools/<tool>/execution/runtime.py` is per-operation orchestration.** Orchestration is application logic and never lives in `integrations/`; only the subprocess/client adapter does. This satisfies [backend-layering](../../.ai/standards/architecture/backend-layering.md) R3/R4 and keeps the JMeter package structurally parallel to `services/tools/owasp_zap/execution/`.

## 2. Package layout

```
app/schemas/tools/jmeter/
    run_jmeter_test.py             # run_jmeter request/response + analyze_jmeter_result request/response
    jmeter_test_result.py          # the persisted result contract (see result-contract.md)
    worker.py                      # JMeterWorkerState, JMeterWorkerInfo
app/services/tools/jmeter/
    run_jmeter_test_service.py     # JMeterTestService.init_run_jmeter_test — submission
    analyze_jmeter_result_service.py  # JMeterAnalyzer.analyze_jmeter_result
    execution/
        dispatcher.py              # JMeterDispatcher — queue lane → worker assignment
        runtime.py                 # JMeterRuntime — the per-operation pipeline
    plan/                          # JMX generation + request/plan validation (internal)
app/integrations/jmeter/
    worker.py                      # JMeterWorker — registration + the JMeter process
    parser.py                      # JMeterParser — JTL → metrics
    runtime.py                     # process singletons
    registry.py  scheduler.py  pool.py    # JMeter-specific copies (see §5)
app/routers/mcp/jmeter_router.py   # run_jmeter, analyze_jmeter_result (thin submit adapters)
```

Files named after an MCP tool carry the tool in the filename (`run_jmeter_test_service.py`); files named after an architectural component do not, since the package is already JMeter-scoped (`worker.py`, `parser.py`, `runtime.py`, `dispatcher.py` — matching ZAP). `jmeter_test_result.py` is prefixed because the unprefixed alternative, `test_result.py`, is collected by pytest's default `test_*.py` pattern.

Only `plan/`, `integrations/jmeter/runtime.py`, `registry.py`, `scheduler.py` and `pool.py` remain unbuilt after Phase 1.

## 3. The boundary table

Read this as: **every row's "Owns" appears in exactly one row.**

### `JMeterDispatcher` — *when* work starts

- **Owns:** polling its queue lane (`BatchType.ALL_JMETER_TYPES`, see [queue-isolation](queue-isolation.md)); asking the pool manager for an idle Active worker; handing the operation to `JMeterRuntime`; the heartbeat sweep that fails operations whose worker went Offline.
- **Never:** knows what a JMX file is, reads a JTL, computes a metric, or interprets a result. It is scheduling only — the same role ZAP's dispatcher has.

### `JMeterRuntime` — *what* happens, in order

- **Owns:** the per-operation pipeline and **all lifecycle persistence for it**:
  1. **Generate** — calls the plan generator to produce a JMX from the validated request.
  2. **Validate** — request validity **and** target authorization (Guardrail G4, see §4) **before** anything executes; also that the generated JMX is well-formed.
  3. **Execute** — hands the JMX to the assigned worker and waits, translating worker progress into `operation_service.report_progress(...)`.
  4. **Parse** — hands the run's results file to `JMeterParser` and receives metrics back. **The only phase whose failure does not fail the operation:** every phase before it decides *whether the test may run*, while this one reads back what a run that already happened produced. An unreadable JTL therefore degrades the result (both derived sections absent) instead of discarding a load test that really did execute — see [result-contract](result-contract.md) §1.
  5. **Persist** — assembles `JMeterTestResult`, calls `operation_service.start / complete / fail`, and releases the worker in a `finally` (ZAP's `zap_scan_worker` is the precedent for the try/except/finally shape).
- **Also owns:** placing artifacts under `ReportPaths.JMETER_DETAIL_DIR/{operation_id}/` and turning those paths into the public URLs in `JMeterArtifacts`; and, at Persist, calling `execution/artifact_package.py` to write the package's `summary.html` and `execution.json`. That call sits here because this is the only point where the request, the worker and both timestamps are simultaneously in hand — see [result-contract](result-contract.md) §7 for the layout and the reasoning.
- **Never:** spawns or signals an OS process itself; parses a JTL row; decides whether the numbers are good; picks which worker runs the job.
- **Sole caller of `OperationService`** for JMeter operations — with one deliberate exception: the dispatcher's own `fail()` for an operation it could not hand off at all (unresolvable metadata, dead worker). That mirrors ZAP exactly.

### `JMeterWorker` — *where* it runs

- **Owns:** accepting one assignment at a time; the local filesystem workspace for one run; launching, monitoring, and killing the short-lived `jmeter -n -t plan.jmx -l results.jtl -e -o report/` subprocess; enforcing the run timeout; and reporting its own local state and workspace back when asked.
- **Registration and heartbeat are *not* on this class** (settled in Phase 3). They live in `docker/jmeter/register-worker.sh`, mirroring exactly how a ZAP worker announces itself — the container's sidecar registers, the application code only executes. This keeps the agent process free of any server-lifecycle concern and means the worker's Python surface is `accept` / `report_for` / `cancel` and nothing else.
- **Never:** touches the Operations table, the DAO, or `OperationService`; interprets the JTL; knows about queues, other operations, or other workers.
- **Lifecycle note:** the *worker* is long-lived (so heartbeats mean something); the *JMeter process* is ephemeral. This is the distinction [ADR-0009](../../.ai/decisions/0009-execution-capability.md) §2.5's concern about ephemeral workers does not apply to.

### `JMeterParser` — *what the numbers are*

- **Owns:** reading a JTL file and producing `JMeterMetrics` + the numeric parts of `JMeterExecutionSummary` — aggregation, percentiles, error rate, throughput, per-label breakdown.
- **Never:** does I/O beyond reading the file it is handed; touches the DB, the operation, the pool, or the network; makes a judgment about the values — no SLA, no threshold, no recommendation.
- **Property this buys:** the parser is a pure function of file → numbers. It is unit-testable against a fixture JTL with no JMeter, no worker, and no database — which is where the arithmetic bugs will actually be caught, and where they are in fact caught (`tests/integrations/jmeter/test_jmeter_parser.py`).
- **Two decisions worth recording**, since both are visible in stored results and neither is forced:
  - **Percentiles are nearest-rank**, not interpolated. Every figure reported is a response time that was actually measured, so a p99 names a request that really took that long. It differs from JMeter's own dashboard by at most one adjacent sample.
  - **Durations come from the samples**, not the Runtime's clock: the window runs from the first request starting to the last one finishing, which excludes JVM startup and HTML dashboard generation and so measures the load rather than the job.
- **`target_url` is passed in, not parsed.** It is the one field of `JMeterExecutionSummary` a JTL cannot supply — a JTL records sampler labels, not the request that authorized them. Passing it as a value keeps the parser free of any dependency on the request pipeline.

### `JMeterAnalyzer` — *what the numbers mean*

- **Owns:** backing the `analyze_jmeter_result` MCP tool. Loads the persisted record (DAO / `HistoryService.get_result`), verifies `record.batch_type in BatchType.ALL_JMETER_TYPES`, handles the FAILED case from `record.status` / `record.error`, and turns the stored `JMeterTestResult` into a human-readable interpretation.
- **Never:** re-opens the JTL or the HTML report, recomputes any metric, re-runs anything, or touches the worker pool. Its **only** input is `operation.result`, reached through a single read-only `get_operation` call.
- **Reports four outcomes distinctly**, because conflating any two of them misleads the reader: *not finished* (queued/running), *execution failed* (terminal, non-completed — the record's own `error` is quoted, never reinterpreted), *parser degradation* (completed, but `summary`/`metrics` absent — the run happened and the target was loaded, so metadata and artifacts are still returned), and *parsed* (the full reading). The third is the one worth naming explicitly: absent measurements must never read as "no load was generated".
- **Describes, never judges.** It reports measured values and arithmetic relationships between them ("p95 is 4.2x the median"). It emits no verdict, threshold, SLA or recommendation — that is `Policy` ([ADR-0008](../../.ai/decisions/0008-domain-ubiquitous-language.md) §6), whose trigger has not fired. The one place wording varies with the data is the sentence describing distribution shape; both branches report identical numbers, and the ratio behind the choice is a descriptive cut, not a threshold anything passes or fails.
- **Deterministic:** the same stored record always yields the same words. No clock, no randomness, no model call.
- **Consequence, on the record:** if the analyzer needs a number, that number must be added to the result contract and produced by the parser. "The analyzer will just read the JTL" is the boundary violation this rule exists to prevent.

## 4. Guardrail G4 — where target authorization lives

A load engine's blast radius is larger than a scanner's: an unauthorized or mistaken target is a denial-of-service, not an unwanted scan. Therefore:

- The target is an **explicit, required input** of `run_jmeter`. It is never inferred, defaulted, or discovered.
- `JMeterRuntime`'s **Validate** step is the single enforcement point, and it runs **before** Generate's output is executed and before a worker is engaged.
- JMX generation may never widen the target set beyond what was requested — the generated plan addresses the caller's target and nothing else.

Validation is a trust boundary. It is not simplified away, and it is not duplicated into the worker (which would give two places to get it wrong).

## 4a. Where the worker's own code lives, and why it is not a `workers/` package

ZAP and JMeter differ in the tools, not in the design: **ZAP is a daemon**, so its worker container runs the vendor image and this repository contains no ZAP worker code at all. **JMeter is a CLI**, so something on the worker host must accept an assignment and own the process. That asymmetry is unavoidable; where the resulting code lives is a choice, and it was made against the standard rather than by convenience:

| Component | Location | Rule it satisfies |
|---|---|---|
| `JMeterWorker`, `JMeterProcessRunner` | `integrations/jmeter/` | [backend-layering](../../.ai/standards/architecture/backend-layering.md) R3 — adapters to an external thing (the `jmeter` binary) |
| Worker agent ASGI app + its 3 endpoints | `app/runtime/jmeter/main.py` (endpoints inline) | [runtime-boundary](../../.ai/standards/architecture/runtime-boundary.md) RB1 — a Runtime Boundary, governed outside the backend role set |
| Registration / heartbeat | `docker/jmeter/register-worker.sh` | Mirrors `docker/owasp_zap/register-worker.sh` exactly |

**A `app/workers/` package was considered and rejected**, and the concept was resolved by [ADR-0012](../../.ai/decisions/0012-runtime-boundary.md) instead. `workers/` is not in R1's role list, so creating it is a *new top-level role* — a Decision-level change per the Exceptions clause, and named directly in the Anti-patterns ("Adding a new top-level role because a concept doesn't fit anywhere"). It was also simply the wrong name: `integrations/owasp_zap/` already contains a worker registry, pool and scheduler, so "worker" was taken, and what actually distinguishes this component is that it is **independently deployed**.

The answer was not to admit a role but to place the component **outside** the role set: `app/runtime/` is a category, not a layer, so R1's whitelist is unchanged and still blocking. The four-condition test (own image, own lifecycle, own interface, local execution) is what keeps that category from becoming a dumping ground.

The agent's endpoints are deliberately *not* under `routers/`: R2 partitions `routers/` by audience of the mcp-server, and these are served by a different process. Note the contrast with `routers/public/jmeter_worker_router.py`, which *is* the server's surface — the endpoints workers call to register — and is correctly placed there, next to ZAP's.

**Isolation holds at three levels** (RB3 + RB5):

1. **Rule** — `aios arch` scans `app/runtime/**` and fails on any import of `app.dao`, `app.services`, `app.routers` or `app.bootstrap`.
2. **Image** — `docker/jmeter/Dockerfile` copies only `app/runtime/jmeter/`, `app/core/`, `app/schemas/tools/jmeter/` and `app/integrations/jmeter/` — 35 Python files instead of the full 143. The forbidden modules are not in the worker image at all.
3. **Closure** — `tests/integrations/jmeter/test_jmeter_worker_isolation.py` measures the agent's real *transitive* imports in a clean interpreter and fails if they grow past that allowlist, which keeps the Dockerfile's copy list from silently drifting back to `COPY app ./app`.

## 5. What is copied from ZAP, and what is imported

Nothing JMeter-side imports from `app/integrations/owasp_zap/` or `app/services/tools/owasp_zap/`. The registry, scheduler, and pool manager are typed on `ZapWorkerInfo`; importing them would create the cross-tool coupling this design exists to avoid (conflict **C2**).

| Reused as-is (genuinely shared) | Copied as a pattern (JMeter-specific) |
|---|---|
| Operations table + `BaseOperationDAO` | Worker registry |
| `OperationService` + lifecycle events | Scheduler (round-robin) |
| Notification pipeline | Pool manager |
| `domain.lifecycle.OperationPhase` | Dispatcher |
| `MCPLogger`, config pattern | Worker registration/heartbeat router |
| History endpoints, `/public` static serving | |

The duplication is deliberate — it is the **Implement** step of Implement → Observe → Extract. [ADR-0009](../../.ai/decisions/0009-execution-capability.md)'s revisit trigger is where extraction gets *considered*, after two substrates exist and can be compared. Extracting now would generalize from a set of one.

Registration endpoints and heartbeat/sweep intervals are JMeter-scoped and independently configurable (adjustment **A7**): a worker saturated by load generation may heartbeat less promptly than an idle ZAP daemon, and the two pools must not be able to cross-register.

## 6. `run_jmeter` is asynchronous

Settled here because it determines who owns the response (adjustment **A6**): `run_jmeter` returns `{operation_id, status, message}` immediately, exactly like every ZAP MCP tool. Summary and artifact links come later from `GET /api/history/get-result` or `analyze_jmeter_result`.

A synchronous return would make the dispatcher and pool tier pointless — and load tests run for minutes. One model, chosen: submit-and-poll.
