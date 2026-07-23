# Performance Engine — Governance Index

**Entry point** for the Performance Engine's architecture governance. This is a **navigation index only** — it introduces no rules and defines nothing new; every item lives in the artifact it points to. Canonical architecture is [ADR-0010 (R2)](../../.ai/decisions/0010-performance-engine-capability.md).

> **Governance status: FROZEN.** No proactive governance changes. New rules/gates are added only when implementation reveals a *real* architectural risk — never speculatively.

Paths below are relative to the repo root (`mcp-server/…` for code/tests).

## Architecture Invariants (INV1–INV13)
Purpose: the acceptance backbone — the properties every Performance operation must uphold. Defined in ADR-0010 [§4.11](../../.ai/decisions/0010-performance-engine-capability.md) (INV1–INV11) and [§4.12](../../.ai/decisions/0010-performance-engine-capability.md) (INV12–INV13).

| INV | Purpose | Implemented in | Validated by |
|---|---|---|---|
| INV1 | One worker → one active job | `app/services/performance/worker/performance_worker.py` (`_maybe_start_job`) | `tests/services/performance/worker/test_performance_worker.py`, e2e |
| INV2 | One workspace per operation, never reused | `app/services/performance/runtime/workspace.py` | `tests/services/performance/runtime/test_workspace.py` |
| INV3 | JMX whitelist (unknown rejected) | `app/integrations/jmeter/jmx_validator.py` | `tests/integrations/jmeter/test_jmx_validator.py` |
| INV4 / INV10 | Redact before persistence; never persist secrets | `app/services/performance/redaction/redactor.py` + runtime ordering | `tests/services/performance/redaction/test_redactor.py`, e2e |
| INV5 | Cleanup after persistence, on success and failure | `runtime/workspace.py` (context mgr) + `performance_runtime.py` | `test_workspace.py`, `test_performance_runtime.py` |
| INV6 | Worker stateless between jobs | `worker/performance_worker.py` (`_run_job` finally) | `test_performance_worker.py`, e2e |
| INV7 | `subprocess` only in the Runner | `app/integrations/jmeter/process_group.py` | runtime/dispatcher purity tests |
| INV8 | Process-group kill on timeout/cancel | `app/integrations/jmeter/process_group.py` | `tests/integrations/jmeter/test_process_group.py` |
| INV9 | Worker exposes no inbound channel (worker-initiated only) | `integrations/performance/{server_client,report_sender}.py` (outbound-only) | design; import graph (no server on worker) |
| INV11 | Below-min-version worker never assigned | `app/integrations/performance/fitness.py` | `tests/integrations/performance/test_scheduling.py` |
| INV12 | Each dispatcher processes only its supported type set | `dispatcher.py` + DAO `scope_queued_by_type` | Coexistence Guard (below) |
| INV13 | Engine identity immutable across the lifecycle | dispatcher (scoped) + no type mutation anywhere | Coexistence Guard; Gate B (Phase 3) |

## Coexistence Guard
Purpose: prove multiple engines' dispatchers share one Operations queue safely (INV12 + INV13) — the permanent, engine-neutral regression guard. Implemented by the ZAP §4.12 scoping (`app/services/tools/owasp_zap/execution/dispatcher.py`) + the Performance dispatcher (`app/services/performance/dispatcher.py`). Validated by `mcp-server/tests/services/performance/test_dispatcher_coexistence.py`.

## Purity Tests
Purpose: mechanically enforce engine-neutrality and execution-ownership boundaries via AST/import checks.

| Guard | Purpose | Validated by |
|---|---|---|
| Engine-seam purity | seam names/imports no engine | `tests/services/performance/engine/test_engine_seam.py` |
| Scheduler/Pool purity | scheduler ends at assignment; no runtime/engine import | `tests/integrations/performance/test_scheduling.py` |
| Dispatcher purity | no runtime/engine/subprocess import | `tests/services/performance/test_performance_dispatcher.py` |
| Runtime purity | no subprocess / engine / docker import | `tests/services/performance/runtime/test_performance_runtime.py` |

## Validation Gates A–E
Purpose: composition-integrity gates for Phase 3. Defined in [phase-3-roadmap.md](phase-3-roadmap.md); implemented during the commits noted there.

| Gate | Purpose | Lands in |
|---|---|---|
| A | Singleton integrity — the five subsystem objects instantiated once, shared | C3.4 |
| B | OperationType end-to-end integrity (INV13 across the full path) | C3.6 (server), C3.7 (full) |
| C | Composition-root purity — subsystem objects constructed only in wiring/bootstrap (import-origin-aware) | C3.4 |
| D | Dependency-direction purity — composition root is a sink; no subsystem imports it | C3.4 |
| E | Configuration ownership — `Settings` reads + concrete construction only in wiring/bootstrap | C3.4 |

## Common Per-Commit Gates
Purpose: the standing bar every Phase 3 commit must clear. Defined in [phase-3-roadmap.md](phase-3-roadmap.md): full suite green · Coexistence Guard green · ZAP suite byte-for-byte green · `python .ai/tools/aios.py check` PASS · `git diff` shows **no modification** to any frozen subsystem file (wiring/additions only).

## Architecture Debt Register
Purpose: tracked, deliberately-deferred debt (not ADR changes). See [architecture-debt.md](architecture-debt.md): **AD-1** (worker-side runtime-failure reporting / eventual terminal state) and **AD-2** (inline artifact transport at scale).

## ADR References
- [ADR-0009](../../.ai/decisions/0009-execution-capability.md) — execution contract hygiene (H1–H4); the "decouple first" precondition.
- [ADR-0010 (R2)](../../.ai/decisions/0010-performance-engine-capability.md) — the Performance capability, warm-worker/pull model, seam, security model, INV1–INV13, §4.12 coexistence.
- [implementation-plan.md](implementation-plan.md) — phase sequencing (Phase 0 → Phase 3).
- [phase-3-roadmap.md](phase-3-roadmap.md) — Phase 3 commits, Gates A–E, common gates.
