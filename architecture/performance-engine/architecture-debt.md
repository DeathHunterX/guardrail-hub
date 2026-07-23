# Performance Engine — Architecture Debt Register

**Purpose:** track accepted architectural debt for the Performance Engine subsystem that is **deliberately deferred**, so it is neither forgotten nor allowed to silently expand. This register is **not** an ADR and does **not** modify [ADR-0010](../../.ai/decisions/0010-performance-engine-capability.md); it records debt the backend-owner has chosen to defer. Items graduate to an ADR amendment only by explicit decision.

**Status of ADR-0010:** unchanged (ratified through R2). The R3/INV14 proposal was **withdrawn** by owner decision — AD-1 remains tracked debt, not an invariant.

| ID | Title | Class | Severity | Status | Surfaced by |
|---|---|---|---|---|---|
| AD-1 | Worker-side runtime-failure reporting (eventual terminal state) | Architecture debt | Medium (liveness) | **Deferred** — after Phase 3 | P2AR |
| AD-2 | Inline artifact transport at scale | Scalability / future-architecture debt | Low now, grows with scale | **Deferred** | P2AR |

---

## AD-1 — Worker-side runtime-failure reporting (eventual terminal state)

**Class:** Architecture debt (a liveness property of the pull orchestration model — engine-neutral, not JMeter-specific).

**Description.** `PerformanceRuntime.execute` *raises* in two cases that occur **before or instead of** a terminal report reaching the server: (1) a worker-side plan rejection, and (2) a report-**delivery** failure (`ReportSendError`). On a raise the worker frees itself *locally* but sends **no report**, so the operation stays `RUNNING` and the worker stays server-side "busy" (its `op_id` remains bound). The only server-side recovery is the heartbeat-timeout sweep — which does **not** fire for a still-heart-beating worker. Engine failures/timeouts/cancellations are unaffected (they return a result and *are* reported).

**Impact.** A stuck operation (`RUNNING` forever) plus a worker that appears busy server-side while idle locally — it never receives new work. Bounded to the two runtime-raise paths; the happy, engine-failure, and cancellation paths are correct and tested.

**Why deferred (owner decision).** The architecture is not to be changed before Phase 3, and Phase 3 is integration/wiring only — no behavioural changes. AD-1's fix is a behavioural worker-loop change and must not be mixed into Phase 3.

**Recommended resolution (when scheduled).** Promote to an invariant (eventual terminal state) enforced by a **report-or-relinquish** worker contract: on a runtime failure, the worker reports a `FAILED` outcome while the report channel is reachable; if it cannot reach the server at all, it stops heart-beating (self-quarantine / deregister) so the heartbeat-timeout sweep reclaims and fails the operation (at-most-once, no auto-retry). This closes the gap between ADR-0010 §4.6 ("if persistence fails, the operation is FAILED") and the mechanism. Requires: an ADR amendment (the invariant + contract) **and** a worker-loop change — both as a single, separately-reviewed change, **not** Phase 3.

**Does Phase 3 make it worse?** No. Phase 3 wires components without altering the failure paths; AD-1's blast radius is unchanged by composition.

---

## AD-2 — Inline artifact transport at scale

**Class:** Scalability / future-architecture debt.

**Description.** The worker→server report channel (ADR-0010 §4.6) carries artifacts **base64-inline** inside a single JSON POST — deliberately chosen over shared volumes to keep the worker inbound-channel-free and filesystem-agnostic. For large JTL/HTML dashboards this inlines the full artifact set into one request body (worker memory + request size + server memory on ingest).

**Impact.** None at foundation scale / single-node. It becomes a memory and payload-size concern for large test plans, high artifact volumes, or distributed/high-throughput deployments.

**Trigger to revisit.** Real artifacts approaching request-size/memory limits, or a distributed deployment where a shared/object store is already present.

**Recommended direction (when triggered).** A streaming/chunked upload or an object-store-backed transport (worker writes redacted artifacts to a shared/object store; the report carries references). The `PersistencePort` / report-channel contract is the seam that already isolates this — the change would be behind it, without touching the Runtime, Worker loop, or Dispatcher.

**Does Phase 3 make it worse?** No. Phase 3's concrete `ReportStore` is filesystem-backed for the single-node foundation; the transport contract is unchanged. A future object-store `ReportStore`/transport slots in behind the same contract.

---

## Deferral guarantee

Both items are safe to defer past Phase 3 because Phase 3 is **wiring only**: it instantiates ratified components without changing any failure path (AD-1) or the artifact-transport contract (AD-2). Neither item blocks composition, and neither is worsened by it. Each will be addressed as its own reviewed change (AD-1 with an ADR amendment; AD-2 when its trigger fires).
