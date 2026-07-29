"""The JMeter result contract persisted to ``operation.result``.

Ratified by ADR-0010 and specified in
``architecture/jmeter-engine/result-contract.md``. Four sections — execution
summary, execution metrics, generated artifacts, execution metadata — and
nothing else.

Deliberately absent, each for a recorded reason:

* ``status`` / ``error`` — the Operation owns lifecycle state (ADR-0008 §3.1,
  invariants I2/I3). On failure ``OperationService.fail()`` sets
  ``operation.error`` and ``result`` stays ``None``.
* SLA verdict / thresholds / pass-fail — that is ``Policy`` (ADR-0008 §6),
  whose trigger has not fired. Metrics are reported; judgment is not encoded.
* Findings and severities — a load test produces none (ADR-0008 §2.4).
* Per-sample time series — it already lives in the linked ``.jtl`` and the HTML
  dashboard; duplicating it into a database row has no consumer.

This is persisted data: adding a field is safe, removing or renaming one breaks
stored results and requires an ADR superseding ADR-0010.

**Amended 2026-07-29 (Phase 3).** ``summary`` and ``metrics`` are now optional.
Every field in both is derived from the JTL results file, and parsing is Phase
4 — so the execution phase can persist a truthful record (what ran, where its
artifacts are, when and on which worker) without inventing sample counts it has
not measured. A fully-populated result still validates unchanged; this is a
relaxation, not a removal. It diverges from ADR-0010 §2 and is recorded in
``architecture/jmeter-engine/result-contract.md`` §1.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JMeterLatency(BaseModel):
    """Response-time distribution for a set of samples, in milliseconds."""

    min_ms: float = Field(..., description="Fastest sample.")
    max_ms: float = Field(..., description="Slowest sample.")
    mean_ms: float = Field(..., description="Arithmetic mean response time.")
    p50_ms: float = Field(..., description="Median response time.")
    p90_ms: float = Field(..., description="90th percentile response time.")
    p95_ms: float = Field(..., description="95th percentile response time.")
    p99_ms: float = Field(..., description="99th percentile response time.")


class JMeterLabelMetrics(BaseModel):
    """Metrics for one sampler label — one request in the test plan.

    JMeter's ``label`` is a mandatory JTL column, so a plan with several
    samplers produces several of these. Without them "which endpoint is slow"
    is unanswerable.
    """

    label: str = Field(..., description="Sampler label as it appears in the JTL.")
    sample_count: int = Field(..., description="Samples recorded for this label.")
    error_count: int = Field(..., description="Failed samples for this label.")
    error_rate_percent: float = Field(
        ..., description="Failed samples as a percentage of this label's samples."
    )
    latency: JMeterLatency = Field(..., description="Response times for this label.")
    throughput_rps: float = Field(
        ..., description="Completed samples per second for this label."
    )


class JMeterExecutionSummary(BaseModel):
    """What happened, at a glance."""

    target_url: str = Field(..., description="The target the plan addressed.")
    total_samples: int = Field(..., description="Samples recorded across the run.")
    error_count: int = Field(..., description="Samples that failed.")
    error_rate_percent: float = Field(
        ..., description="Failed samples as a percentage of all samples."
    )
    duration_seconds: float = Field(
        ..., description="Wall-clock duration of the test execution."
    )


class JMeterMetrics(BaseModel):
    """Aggregate metrics for the whole run, plus the per-label breakdown."""

    latency: JMeterLatency = Field(..., description="Response times across all samples.")
    throughput_rps: float = Field(..., description="Completed samples per second.")
    received_kb_per_sec: float = Field(..., description="Inbound throughput.")
    sent_kb_per_sec: float = Field(..., description="Outbound throughput.")
    labels: list[JMeterLabelMetrics] = Field(
        default_factory=list, description="Per-sampler breakdown."
    )


class JMeterArtifacts(BaseModel):
    """Public links to the files this run produced.

    Served by the existing ``/public/**`` static mount from
    ``ReportPaths.JMETER_DETAIL_DIR/{operation_id}/``. There is no artifact
    store component — this follows the same mechanism ZAP reports use.
    """

    view_report: Optional[str] = Field(
        None, description="Open this link in your browser to view the HTML dashboard."
    )
    results_data: Optional[str] = Field(
        None, description="Raw JTL results, for import into other tools."
    )
    test_plan: Optional[str] = Field(
        None, description="The JMX test plan that was executed."
    )
    engine_log: Optional[str] = Field(
        None, description="JMeter's own engine log for this run."
    )


class JMeterExecutionMetadata(BaseModel):
    """Who ran it, when, and under which load profile.

    Deliberately records no JMeter version. The engine version is a property of
    the Docker image the worker runs, which is the single source of truth for
    it; echoing it here would create a second one that can disagree. The caller
    never selects a version, so there is nothing to record on their behalf.
    """

    worker_id: str = Field(..., description="Worker that executed the run.")
    started_at: datetime = Field(..., description="UTC start of execution.")
    finished_at: datetime = Field(..., description="UTC end of execution.")
    thread_count: int = Field(..., description="Concurrent threads (virtual users).")
    ramp_up_seconds: int = Field(
        ..., description="Seconds over which all threads were started."
    )
    hold_seconds: int = Field(
        ..., description="Seconds the full thread count was sustained."
    )


class JMeterTestResult(BaseModel):
    """The full payload persisted to ``operation.result``.

    Written by ``JMeterRuntime`` at the Persist phase; read by
    ``analyze_jmeter_result`` and ``GET /api/history/get-result``. It is the
    analyzer's **only** input — any number the analyzer needs must be produced
    by the parser and land in this model, never re-derived from the artifacts.
    """

    operation_id: str = Field(
        ..., description="Matches the operation_id returned by run_jmeter."
    )
    summary: Optional[JMeterExecutionSummary] = Field(
        None,
        description=(
            "Sample counts and error rate. Absent until the results file has "
            "been parsed — every field in it is derived from the JTL."
        ),
    )
    metrics: Optional[JMeterMetrics] = Field(
        None,
        description=(
            "Latency, throughput and the per-label breakdown. Absent until the "
            "results file has been parsed."
        ),
    )
    artifacts: JMeterArtifacts
    metadata: JMeterExecutionMetadata
