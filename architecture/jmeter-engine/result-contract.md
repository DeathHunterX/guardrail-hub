# JMeter Engine — Result Contract (Final)

Status: **Final** — decided 2026-07-28. Governed by [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md).
Resolves: conflict **C4** and adjustment **A3** of the [architecture validation report](../../jmeter-engine-architecture-review.md).

This is the canonical shape persisted into `operation.result` when a JMeter operation completes, and the **only** input `analyze_jmeter_result` reads.

---

## 1. Scope of this contract

It is a **JMeter wire format** — a tool-specific Pydantic model in `app/schemas/tools/jmeter/jmeter_test_result.py`, per [backend-layering](../../.ai/standards/architecture/backend-layering.md) R3 and [backend-naming](../../.ai/standards/coding/backend-naming.md) R4.

> **Amended 2026-07-29 (consistency pass).** `JMeterExecutionMetadata.jmeter_version` was **removed** after Phase 1, on the owner's direction: the engine version is a property of the Docker image the worker runs, and echoing it into the result created a second source of truth for it. The caller never selects a version, so there is nothing to record on their behalf. No replacement field was introduced.
>
> ⚠️ This diverges from [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md) §2, which lists `jmeter_version` in the accepted contract. The ADR was **not** edited — decision records are append-only, and the consistency-pass brief explicitly forbade both amending accepted ADRs and creating new ones. The divergence is recorded here so it is visible rather than silent, and it is safe to carry: no JMeter result has ever been persisted, so nothing stored depends on the field. **Owed:** a one-line amendment note or a superseding record against ADR-0010, in a governance task rather than an implementation one.

> **Amended 2026-07-29 (Phase 3).** `summary` and `metrics` are now **optional**. Every field in both is derived from the JTL results file, and parsing lands in Phase 4 — so the execution phase can persist a truthful record (what ran, where its artifacts are, when and on which worker) without inventing sample counts it never measured. A fully-populated result validates unchanged: this is a relaxation, not a removal, and Phase 4 fills both in without any further contract change.
>
> ⚠️ Second divergence from [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md) §2, which lists both as required. Same handling and same reason as the `jmeter_version` removal above — the ADR is append-only and this phase's brief forbade amending it. It folds into the one governance follow-up already owed, which should now cover **both** changes.

It is not a domain concept, not shared with ZAP, and not a cross-tool result model. [ADR-0008](../../.ai/decisions/0008-domain-ubiquitous-language.md) §6 reserved a `Result` root and a `Metrics` concept for the day JMeter arrives; [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md) fires that trigger and answers **defer the domain root, ship the wire format** — with the reasoning on the record.

## 2. The contract

```python
# app/schemas/tools/jmeter/jmeter_test_result.py

class JMeterLatency(BaseModel):
    """Response-time distribution, milliseconds."""
    min_ms: float
    max_ms: float
    mean_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float


class JMeterLabelMetrics(BaseModel):
    """Metrics for one sampler label (one request in the plan)."""
    label: str
    sample_count: int
    error_count: int
    error_rate_percent: float
    latency: JMeterLatency
    throughput_rps: float


class JMeterExecutionSummary(BaseModel):
    """What happened, at a glance."""
    target_url: str
    total_samples: int
    error_count: int
    error_rate_percent: float
    duration_seconds: float


class JMeterMetrics(BaseModel):
    """Aggregate metrics across the whole run, plus the per-label breakdown."""
    latency: JMeterLatency
    throughput_rps: float
    received_kb_per_sec: float
    sent_kb_per_sec: float
    labels: list[JMeterLabelMetrics] = Field(default_factory=list)


class JMeterArtifacts(BaseModel):
    """Public links to the files this run produced."""
    view_report: Optional[str] = None    # /public/report/jmeter/detail-report/{op_id}/index.html
    results_data: Optional[str] = None   # .../{op_id}/results.jtl
    test_plan: Optional[str] = None      # .../{op_id}/plan.jmx
    engine_log: Optional[str] = None     # .../{op_id}/jmeter.log


class JMeterExecutionMetadata(BaseModel):
    """Who ran it, when, under which load profile.

    No engine version: that is the worker's Docker image, the single source
    of truth for it, and is never caller-selected. (Amended 2026-07-29.)
    """
    worker_id: str
    started_at: datetime
    finished_at: datetime
    thread_count: int
    ramp_up_seconds: int
    hold_seconds: int


class JMeterTestResult(BaseModel):
    """The full payload persisted to operation.result."""
    operation_id: str
    summary: JMeterExecutionSummary
    metrics: JMeterMetrics
    artifacts: JMeterArtifacts
    metadata: JMeterExecutionMetadata
```

Persisted exactly as ZAP does it — `JMeterTestResult(...).model_dump(by_alias=True)` passed to `OperationService.complete(operation_id, result=...)`.

## 3. Field-by-field justification

Every field is something JMeter actually emits today. Nothing is reserved, nullable-for-later, or extensible-by-design.

| Section | Source | Why it exists |
|---|---|---|
| `summary` | JTL aggregate | The one-line answer: did it run, how long, how many samples, how many failed |
| `metrics.latency` | JTL `elapsed` column | JMeter's own dashboard reports exactly min/max/mean/p50/p90/p95/p99 |
| `metrics.throughput_rps`, `received_kb_per_sec`, `sent_kb_per_sec` | JTL aggregate | The three throughput figures JMeter's aggregate report produces |
| `metrics.labels` | JTL `label` column | A plan with several samplers produces several labels; "which endpoint is slow" is unanswerable without it. Not speculation — `label` is a mandatory JTL column |
| `artifacts` | Files written by the run | The HTML dashboard (`-e -o`), the raw JTL (`-l`), the executed JMX, the engine log |
| `metadata` | Worker + validated request | Reproducibility: which worker, which load profile, wall-clock window. Not the engine version — see §1 |

`thread_count` / `ramp_up_seconds` / `hold_seconds` are the three properties of a duration-driven JMeter thread group — the profile the generator produces. Loop-driven plans are not generated today and no field is reserved for them.

## 4. What is deliberately absent

| Not in the contract | Why |
|---|---|
| `status`, `error` | The `Operation` owns lifecycle status ([ADR-0008](../../.ai/decisions/0008-domain-ubiquitous-language.md) §3.1, I2). Duplicating it inside the result creates two sources of truth. On failure, `OperationService.fail()` sets `operation.error` and `result` stays `None` — `analyze_jmeter_result` reads `record.status` / `record.error` for that case |
| SLA verdict, pass/fail, thresholds | That is `Policy` — [ADR-0008](../../.ai/decisions/0008-domain-ubiquitous-language.md) §6, trigger not fired. No gating requirement exists. Metrics are reported; judgment is not encoded |
| `Finding`, `Severity`, `FindingSummary` | ADR-0008 §2.4 / the domain stress-test already established a load test produces no findings |
| A shared `Result` / `Metrics` root | One implementation. Deferred by [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md) |
| Time-series / per-sample data | The HTML dashboard already renders it and the JTL already holds it, both linked from `artifacts`. Duplicating a load test's sample stream into a database row is a size problem with no consumer |
| Comparison to a previous run, baselines, trends | No consumer today |

## 5. Interaction with the shared pipeline

The generic operation/notification path needs **two additive presentation rows** in the composition root (`app/bootstrap.py`) — the extension points its own comment already anticipates ("a new tool just adds a row"):

1. `OPERATION_TITLES[BatchType.JMETER_TEST] = "JMeter Load Test"`. Without it the renderer falls back to its default title — degraded, not broken.
2. `_operation_context_resolver` reads the report link from `result["reports"]["view_report"]` (ZAP's key). Widen that one lookup to also accept `artifacts`:
   ```python
   links = result.get("reports") or result.get("artifacts") or {}
   links = links if isinstance(links, dict) else {}
   ```
   ZAP's path is evaluated first and is unchanged.

Two more consequences, requiring no code change:

- **`complete(findings=...)` is omitted for JMeter.** `OperationCompleted.findings` is already `Optional`; a load test has no severity breakdown and passes nothing. The notification layer already handles `None`.
- **Operation metadata must carry `url`.** `_format_scan_target` resolves the user-facing target line from `metadata["target_url" | "url" | "target"]`. Submitting the JMeter request with `url` in metadata makes the notification card render correctly with zero shared-code change.

## 6. Consumers

| Consumer | Reads | Never does |
|---|---|---|
| `analyze_jmeter_result` | `operation.result` via the DAO / `HistoryService.get_result` | Re-open the JTL, recompute metrics, or reach into the worker |
| `GET /api/history/get-result` | The same record, unmodified | — |
| Notification pipeline | `result["artifacts"]["view_report"]` only | Parse metrics |

`analyze_jmeter_result` verifies ownership with `record.batch_type in BatchType.ALL_JMETER_TYPES` (see [queue-isolation](queue-isolation.md) §3).

## 7. Artifact location

Follows the existing `ReportPaths` mechanism — no "artifact store" component is introduced (conflict **C3**):

```python
class ReportPaths:
    BASE_DIR = "./public"
    ZAP_DETAIL_DIR = "./public/report/owasp-zap/detail-report"
    JMETER_DETAIL_DIR = "./public/report/jmeter/detail-report"   # NEW
```

Layout per operation: `./public/report/jmeter/detail-report/{operation_id}/{index.html, results.jtl, plan.jmx, jmeter.log}`, served by the existing `/public/**` static mount. Note that JMeter's HTML dashboard is a *directory*, not a single file — the only structural difference from ZAP's report layout, and the reason the operation id is a directory level here.

## 8. Change policy

This contract is persisted data. Adding a field is additive and safe. Removing or renaming one breaks stored results and `analyze_jmeter_result` — it requires a new ADR superseding [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md), not an edit to this file.
