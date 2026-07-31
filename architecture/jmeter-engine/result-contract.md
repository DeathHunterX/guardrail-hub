# JMeter Engine — Result Contract (Final)

Status: **Final** — decided 2026-07-28. Governed by [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md).
Resolves: conflict **C4** and adjustment **A3** of the [architecture validation report](architecture-review.md).

This is the canonical shape persisted into `operation.result` when a JMeter operation completes, and the **only** input `analyze_jmeter_result` reads.

---

## 1. Scope of this contract

It is a **JMeter wire format** — a tool-specific Pydantic model in `app/schemas/tools/jmeter/jmeter_test_result.py`, per [backend-layering](../../.ai/standards/architecture/backend-layering.md) R3 and [backend-naming](../../.ai/standards/coding/backend-naming.md) R4.

> **Amended 2026-07-29 (consistency pass).** `JMeterExecutionMetadata.jmeter_version` was **removed** after Phase 1, on the owner's direction: the engine version is a property of the Docker image the worker runs, and echoing it into the result created a second source of truth for it. The caller never selects a version, so there is nothing to record on their behalf. No replacement field was introduced.
>
> ⚠️ This diverges from [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md) §2, which lists `jmeter_version` in the accepted contract. The ADR was **not** edited — decision records are append-only, and the consistency-pass brief explicitly forbade both amending accepted ADRs and creating new ones. The divergence is recorded here so it is visible rather than silent, and it is safe to carry: no JMeter result has ever been persisted, so nothing stored depends on the field. **Owed:** a one-line amendment note or a superseding record against ADR-0010, in a governance task rather than an implementation one.

> **Amended 2026-07-29 (Phase 3).** `summary` and `metrics` are **optional**. Both are populated by `JMeterParser` on the normal path, so a completed run carries its numbers exactly as ADR-0010 intended — but the fields stay optional, and **the justification has changed since the relaxation was first written**.
>
> They were originally optional because parsing was unimplemented. They are now optional because **Parse is the only pipeline phase whose failure does not fail the operation**. Every phase before it decides *whether the test may run*; Parse reads back what a run that already happened produced. A run that executed and wrote artifacts really did load the target — losing its numbers is a degraded result, not a failed test, and the HTML dashboard and raw JTL are still linked from `artifacts`. Recording it with both sections absent is truthful; zero-filling them would assert measurements nobody took.
>
> The practical consequence for consumers: **`summary`/`metrics` absent on a COMPLETED operation means "the run happened, its results file was unreadable"** — not "still running" and not "no load was generated". `analyze_jmeter_result` must handle that case explicitly rather than assuming a completed JMeter operation always carries metrics.
>
> ⚠️ Second divergence from [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md) §2, which lists both as required. Same handling and same reason as the `jmeter_version` removal above — the ADR is append-only and this phase's brief forbade amending it. It folds into the one governance follow-up already owed, which should now cover **both** changes. Note the follow-up is no longer a formality that Phase 4 dissolves: this divergence is now permanent by design, so the superseding record has to actually decide whether optionality is accepted.

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
    """Public links to the files this run produced.

    Every field is a link; the sibling JMeterTestResult.summary is
    measurements. Hence `summary_page`, not `summary`.
    """
    summary_page: Optional[str] = None   # .../{op_id}/summary.html
    view_report: Optional[str] = None    # .../{op_id}/html-report/index.html
    results_data: Optional[str] = None   # .../{op_id}/test-results.jtl
    test_plan: Optional[str] = None      # .../{op_id}/test-plan.jmx
    engine_log: Optional[str] = None     # .../{op_id}/engine.log


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

Layout per operation, served by the existing `/public/**` static mount. Note that JMeter's HTML dashboard is a *directory*, not a single file — the only structural difference from ZAP's report layout, and the reason the operation id is a directory level here.

```
{operation_id}/
    summary.html            # Guardrail Hub run summary + links   (we generate)
    execution.json          # execution metadata, machine-readable (we generate)
    test-plan.jmx           # the plan that was executed           (JMeter -t)
    test-results.jtl        # every sample, CSV                    (JMeter -l)
    engine.log              # JMeter's engine log                  (JMeter -j)
    html-report/            # JMeter's own dashboard, untouched    (JMeter -e -o)
        index.html
        statistics.json
        ...
```

**Why the filenames describe their content.** A run package is downloaded, attached to a ticket and archived — read months later by someone who did not run it. `results.jtl` and `report/` mean nothing once separated from the directory that named them; `test-results.jtl` and `html-report/` survive the trip. These are **physical names only**: the `JMeterArtifacts` JSON keys (`test_plan`, `results_data`, `engine_log`, `view_report`) are unchanged, so no consumer of the result had to change.

**Why `execution.json` exists.** JMeter's dashboard is excellent at *what the numbers were* and silent about *which run produced them* — open it a month later and nothing on the page names the target, the load profile, the worker or the time window. Without this file the artifacts do not survive being separated from the Operation record, and being separated is exactly what sharing a run means. It carries **execution metadata only, never metrics**: metrics already live in `test-results.jtl`, in the parsed `operation.result` and in the dashboard, and a fourth copy is a fourth chance to disagree with the other three.

**Why `summary.html` exists, and why the vendor dashboard is untouched.** The same facts for a human, with links into each artifact and a button through to the dashboard. Nothing writes inside `html-report/`. Injecting our content into generated HTML would make the package's provenance ambiguous — a reader could no longer tell which parts JMeter measured and which parts we added — and it would break silently on any JMeter upgrade that changes the template. A separate page keeps the boundary legible, and the dashboard stays byte-identical to what the engine wrote.

Both generated files are written by `services/tools/jmeter/execution/artifact_package.py`, called once by the Runtime at the Persist phase — the only point where the request, the worker and both timestamps are all in hand. Writing them never fails an operation: they are a convenience layered on a run that already succeeded, and the measurements are safe in the artifacts regardless.

`summary.html` **is** reachable from the API, as `artifacts.summary_page` — an additive field, which §8 permits. It carries the `_page` suffix rather than being called `summary` because `JMeterTestResult.summary` already means *measurements*: the two never collide inside a payload, but they collide constantly in log lines, review comments and conversation, and that is where the confusion actually costs something. `execution.json` is deliberately **not** exposed as an artifact link: it is the machine-readable twin of a page that is already linked, so a second key would buy nothing.

## 8. Change policy

This contract is persisted data. Adding a field is additive and safe. Removing or renaming one breaks stored results and `analyze_jmeter_result` — it requires a new ADR superseding [ADR-0010](../../.ai/decisions/0010-jmeter-result-contract.md), not an edit to this file.
