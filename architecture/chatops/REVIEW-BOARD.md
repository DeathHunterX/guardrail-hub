# ChatOps Platform — Architecture Review Board

Reviewers: Architecture Review Board (Principal-level) · Date: 2026-07-07 · Subject: [architecture/chatops/](README.md) + [ADR 0004](../../.ai/decisions/0004-chatops-platform-architecture.md)
Review posture: **adversarial pre-approval gate.** Assumes production targets: SaaS, self-hosted, enterprise, **air-gapped**, millions of jobs, thousands of concurrent evaluations.

> This document reviews the design. It does not modify it. Where it says "the design claims," it is quoting design intent, not implemented code — the whole subsystem is greenfield, which is itself a review finding (see [Global G1](#g)).

---

## 0. Global findings (cut across every document)

These are the issues a reviewer raises before reading page one, because they invalidate multiple documents at once.

<a name="g"></a>

**GF-1 — Air-gapped + cloud chat is a contradiction the design never confronts. (Critical)**
Slack, Discord, and Microsoft Teams are cloud SaaS. In a true air-gapped deployment there is **no egress to slack.com**, so the primary channels the platform is built around **cannot function**. Every deployment table ([11-deployment §11.2](11-deployment.md)) lists Slack/Teams as if universally available. The only channels that survive air-gap are internal SMTP email, internal webhooks, and a self-hosted chat server (Mattermost/Rocket.Chat/Matrix). This is not a footnote — it changes the adapter roadmap, the reference channel, and the "one artifact, three profiles" claim. The board will not approve a "supports air-gapped" statement that is physically false for the flagship channel.

**GF-2 — Target authorization is an open SSRF / attack-proxy hole. (Critical)**
`/run security_scan target=web-api` takes a user-supplied target from a chat channel ([04-api §5.4](04-api-design.md), [08 §9.3](08-chatops-architecture.md)). Nothing in the design binds `target` to a pre-authorized asset inventory. Anyone with chat access can type `target=partner-bank.com` or an internal metadata endpoint and turn Guardrail Hub into a paid attack proxy / SSRF engine. G4 is cited but only as a sandbox egress allow-list — that is the wrong layer. Authorization must happen at command admission against a registered, org-scoped asset inventory with verified ownership. This is missing entirely.

**GF-3 — Chat-identity → Actor binding is hand-waved, and it gates all authz. (Critical)**
[08 §9.4](08-chatops-architecture.md) / [01 §2.2 ACL](01-bounded-contexts.md) resolve a Slack user to an Actor, but never specify account-linking or anti-spoofing. In a shared Slack channel, any member could invoke privileged commands if identity resolution is naive. There is no verified-linking flow, no handling of un-linked users, no per-workspace trust boundary. In a security product this is the front door and it is undefended.

**GF-4 — Multi-tenant secret/token storage is absent. (Critical/High)**
A multi-workspace Slack/Teams app holds a bot token **per installation** — potentially 100k encrypted secrets. Where they live, how they are encrypted (envelope encryption? per-tenant keys?), rotation, and revocation are never addressed. G1 forbids secrets in source but says nothing about the far larger runtime secret-at-rest problem the platform creates for itself.

**GF-5 — Redis is a system-wide single point of failure. (High)**
Redis is load-bearing for sessions, dedup, throttle buckets, live progress, and the cancellation flag ([06](06-queue-and-scalability.md), [07](07-notification-architecture.md), [08](08-chatops-architecture.md)). Its failure mode is never analyzed: does throttling fail open (spam storm) or closed (silent outage)? Does a cancellation flag loss orphan a running scan? "HA Redis" is asserted; the blast radius is not. A single dependency that can simultaneously break notifications, cancellation, and progress is an architectural smell.

**GF-6 — Two messaging systems (queue + bus) to operate, three bus substrates to support. (High)**
The design runs a job **queue** (Redis Streams/SQS) *and* an event **bus** (Kafka/Redpanda/NATS), and offers three interchangeable bus backends "behind a port" ([06 §7.1](06-queue-and-scalability.md), [13 tech](13-extensions-tech-risks.md)). Delivery, ordering, and retention semantics differ materially across Kafka vs NATS vs Redis Streams — a port cannot paper over that; consumers written against Kafka replay assumptions will behave differently on Redis Streams. This multiplies the test matrix (3 buses × 2 DBs × 4 deploy profiles) and the on-call surface, especially for self-hosted/air-gapped operators. Pick one substrate that runs everywhere (NATS JetStream or Redpanda) and standardize.

**GF-7 — The audit hash-chain is incompatible with an at-least-once, multi-producer, partitioned event stream. (Critical)**
[02 §3.5](02-domain-model.md) / [05 §6.2](05-database-design.md) build a per-tenant `prev_hash → hash` chain, and [02](02-domain-model.md) also says audit is *derived from* the event stream. But the bus is at-least-once and events come from multiple producers via multiple outbox relays ([03 §4.5](03-event-catalog.md)) — so the audit consumer sees **duplicates and reordering**. A strict hash chain requires a single, totally-ordered, exactly-once append per tenant. You cannot have both. As written, the tamper-evidence guarantee is unimplementable at scale, and the chain becomes a per-org write-serialization hotspot at millions of jobs. Either move to periodic Merkle anchoring, or make audit a synchronous write on the command path — but the current story is internally inconsistent.

**GF-8 — Idempotency key is derived, not client-supplied, and includes a time bucket. (High)**
`idempotency_key = hash(actor + project + tool + params + time-bucket)` ([02 §3.2](02-domain-model.md)). Two problems: (a) a legitimate "run the same scan again now" is silently blocked within the bucket; (b) a double-tap straddling a bucket boundary produces two jobs — the exact failure it claims to prevent. Chat providers already supply a stable delivery/interaction id (Slack `event_id`, retry headers); use *that* as the client-supplied key. Deriving the key defeats the purpose.

**GF-9 — Progress events through the transactional outbox is a scale anti-pattern. (High)**
[06 §7.3](06-queue-and-scalability.md) emits `job.progressed.v1` via the outbox ([03 §4.5](03-event-catalog.md) makes all lifecycle events go through it). Progress is high-frequency and ephemeral; routing thousands of concurrent scans' progress ticks through a durable Postgres outbox table is enormous write amplification on the primary DB and directly contradicts the "write to Redis, DB only on transitions" claim in the same document. Ephemeral progress should bypass the durable outbox entirely and flow Redis → streaming gateway.

**GF-10 — The outbox pattern does not port cleanly to DynamoDB. (High)**
[05 §6.5](05-database-design.md) claims the DAO hides Postgres-`UNIQUE` vs Dynamo-conditional-put. But the **outbox** needs an atomic (state + event) write; on DynamoDB that is `TransactWriteItems` (25-item cap, cost, single-region) or, more idiomatically, DynamoDB Streams — a *different mechanism*, not a hidden implementation detail. The claim that one DAO interface hides this is where the abstraction leaks hardest.

**GF-11 — No disaster recovery, RPO/RTO, or multi-region story. (High)**
Nothing defines backup/restore for the compliance-critical audit ledger, bus retention/replay windows, RPO/RTO targets, or cross-region failover. For enterprise + 100k orgs this is table stakes and absent across all documents.

**GF-12 — Data residency / geographic sharding is unaddressed. (High)**
Partitioning is by `org_id` hash only ([05 §6.4](05-database-design.md)). Enterprise + EU orgs require region-pinned data (GDPR). There is no region dimension in the tenancy key, no residency policy, no per-region bus/DB topology.

**GF-13 — Ambition vastly exceeds the codebase; sequencing risk. (High)**
The only built path is one ZAP tool ([intelligence/system-overview](../../.ai/intelligence/system-overview.md)). The design specifies CQRS projections, event sourcing-adjacent outbox, hash-chain audit, three bus backends, two DB providers, per-tool autoscaled worker pools, and a streaming gateway. That is years of platform build. §11.4 gestures at an evolutionary path but the documents elsewhere read as if all of it is day-one. Review risk: teams build the plumbing and never ship the product.

---

## 1. README / Overall Architecture ([README.md](README.md))

- **Strengths:** Clear central constraint ("bot has no business logic"); correct C4 layering; explicit ports enumerated; honest planned-vs-built labelling (G5 discipline is genuinely good and rare).
- **Weaknesses:** The mandated linear pipeline (User→Slack→ChatOps→API→Job→Eval→Bus) is presented as *the* architecture, but the real system is a cycle (events flow back); the linear framing undersells the hard part (the return path). "Reuse the existing spine" overstates what exists.
- **Scalability risks:** Context diagram implies every service talks to the bus; no mention of partition/region topology at L1.
- **Security concerns:** Trust boundaries not drawn — where does untrusted input enter? The diagram has no boundary between the cloud chat providers and the core.
- **Operational concerns:** No SLOs/error budgets defined anywhere, starting here.
- **Enterprise concerns:** Air-gapped (GF-1) not visible in the context model.
- **Missing concepts:** Trust-boundary overlay; data-residency dimension; DR posture.
- **Over-engineering:** Six design principles is fine; none are wrong.
- **Under-engineering:** No non-functional requirements (latency, availability, throughput targets) stated to design against.
- **Future extensibility:** Ports enumeration is the strongest extensibility asset in the set.

## 2. Bounded Contexts ([01-bounded-contexts.md](01-bounded-contexts.md))

- **Strengths:** Ownership line (platform owns ChatOps + Notification only) is exactly right and defends the core constraint; ACL/anti-corruption layer named; ubiquitous language table is disciplined.
- **Weaknesses:** Evaluation vs Policy split is asserted but the seam is fuzzy — "regression" lives in Policy, raw findings in Evaluation, yet detectors (jailbreak/PII) arguably *are* policy judgements. Expect boundary disputes. Audit is "owned by Core (ledger) + all contexts (producers)" — shared ownership of the most compliance-sensitive context is a governance smell.
- **Scalability risks:** —
- **Security concerns:** Identity & Access context is listed as core but the chat→actor binding that feeds it (GF-3) lives at the ChatOps edge with no defined contract.
- **Operational concerns:** —
- **Enterprise concerns:** No context for **Tenant/Org lifecycle** (provisioning, offboarding, data export/delete) — required for enterprise and GDPR.
- **Missing concepts:** Billing/Quota context (GF-13 cost control); Asset/Target inventory context (GF-2).
- **Over-engineering:** Seven contexts for a one-tool product today — acceptable as target, premature as build order.
- **Under-engineering:** Anti-corruption layer is named once and never specified (mapping rules, failure handling).
- **Future extensibility:** Context map is clean and additive.

## 3. Domain Model ([02-domain-model.md](02-domain-model.md))

- **Strengths:** Job aggregate is complete and covers the brief's fields plus tenancy, idempotency, correlation; ULID choice is sound; explicit state machine; audit types enumerated.
- **Weaknesses:** `idempotency_key` derivation is flawed (GF-8). `progress:int 0..100` treats security-scan progress as linear — it is notoriously not; consumers will show "90%" for 20 minutes. `result_ref` single URI assumes one artifact; multi-artifact jobs (report + SARIF + transcript) not modeled. No optimistic-concurrency/version field on Job for the state machine (`schema_version` is schema evolution, not row versioning) — concurrent worker + cancel updates can race.
- **Scalability risks:** Hash-chain audit serialization (GF-7).
- **Security concerns:** `payload` "redacted before persistence" is asserted as a guarantee with no mechanism, validation, or defense-in-depth.
- **Operational concerns:** No terminal-state retention/TTL on Job rows; the "current state only" table still grows unboundedly without a lifecycle policy.
- **Enterprise concerns:** No field for data-residency/region; no legal-hold flag on audit (enterprise e-discovery).
- **Missing concepts:** Row-version for concurrency; asset/target entity; cost/credits on Job.
- **Over-engineering:** Hash chain per event may be more than most tenants need (Merkle/periodic anchor is cheaper and scales).
- **Under-engineering:** Concurrency control on the aggregate; multi-artifact results.
- **Future extensibility:** `schema_version` + enum `tool` as data is good — new tools need no model change.

## 4. Event Catalog & Bus ([03-event-catalog.md](03-event-catalog.md))

- **Strengths:** The domain/integration/notification tiering is correct and well-drawn; canonical envelope with `trace_id`/`correlation` is excellent; outbox pattern is the right instinct; the "subscribe without modifying core" section is the extensibility crown jewel.
- **Weaknesses:** **Cross-producer ordering is unsolved** — API, Job Service, Eval Engine each own an outbox and relay; there is no per-job monotonic sequence, so `completed` can be published before `started` and consumers have no defined reordering rule. Single relay per producer is a SPOF/throughput bottleneck (GF-9 compounds it). "Schema registry" is named once with no governance.
- **Scalability risks:** Progress via outbox (GF-9); partition-by-org means a whale org saturates its partitions and head-of-line-blocks its own critical alerts behind progress spam.
- **Security concerns:** Security-alert payloads "redacted before leaving Policy context" — again asserted, not enforced; no DLP backstop.
- **Operational concerns:** No poison-message handling on the bus (DLQ is defined for the queue, not the bus consumers); no consumer-lag SLO except a passing mention.
- **Enterprise concerns:** Event retention/replay window undefined — matters for audit reconstruction and air-gapped forensics.
- **Missing concepts:** Per-job sequence number; schema-registry governance; consumer contract tests.
- **Over-engineering:** Three bus backends (GF-6).
- **Under-engineering:** Ordering guarantees; exactly-once/idempotent-consumer spec (dedup store TTL and its failure mode unspecified).
- **Future extensibility:** Strong — new consumer groups are genuinely free.

## 5. API Design ([04-api-design.md](04-api-design.md))

- **Strengths:** Async 202 + job_id is correct; idempotency-key header; CQRS reads; RFC 9457 problem+json; four surfaces over one core is the right shape; command→API mapping table is clear.
- **Weaknesses:** Read-your-writes hazard — user runs `/run` then `/status`, but reads come from the CQRS projection ([§5.3](04-api-design.md)) which lags the write; the launching user may see "not found." No pagination contract (cursor vs offset), no field-filtering, no bulk endpoints for the "millions of jobs" list. No API for the asset/target inventory that GF-2 requires. Webhook replay-protection (timestamp window, nonce) not specified — only "verify signature."
- **Scalability risks:** `GET /projects/{id}/jobs` at millions of rows needs cursor pagination + hard caps; offset paging will melt.
- **Security concerns:** `/report` returns a link to `result_ref` — is the link authz'd per requester, signed, expiring? Undefined (GF-2 sibling). AuthZ "in the core" is correct in principle but the mapping from a Slack identity to a permission set is undefined (GF-3).
- **Operational concerns:** No rate-limit tiers per plan; 429 "slow down" reply path after a slash command needs `response_url`, not addressed.
- **Enterprise concerns:** No mTLS/private-link option for enterprise API ingress; no per-tenant API keys/scopes model.
- **Missing concepts:** Asset-inventory API; cursor pagination; report-link authorization; webhook anti-replay.
- **Over-engineering:** Optional gRPC mentioned then dropped — noise.
- **Under-engineering:** Idempotency retention window unspecified; concurrency/If-Match on cancel/retry.
- **Future extensibility:** Adapter-over-one-core is genuinely extensible.

## 6. Database Design ([05-database-design.md](05-database-design.md))

- **Strengths:** Store decomposition by access shape is sound; append-only audit with revoked UPDATE/DELETE grants is a real control; outbox partial index; org-leading composite indexes; honest single-table Dynamo mapping.
- **Weaknesses:** GF-7 (hash chain vs event derivation), GF-9 (progress write path), GF-10 (outbox on Dynamo) all land here. No-ORM + partitioned tables + two providers = a **migration story that is completely absent** and will be the operational tax nobody priced. CQRS projector lag (GF read-your-writes) not mitigated.
- **Scalability risks:** Hash-chain serialization; hot `jobs` rows for fast scans (mitigated by Redis, but then durability of in-flight progress is unclear); Dynamo single-table GSIs for status/history can hit hot-partition limits for whale orgs.
- **Security concerns:** Redaction-before-persist asserted; no column-level encryption for `correlation`/`payload` PII; audit backup encryption unspecified.
- **Operational concerns:** No retention/partition-drop automation spec; no backup/restore/PITR; two providers double the operational runbook.
- **Enterprise concerns:** No residency/region sharding (GF-12); no legal-hold; Dynamo path implies AWS lock-in that enterprise/air-gapped customers may reject.
- **Missing concepts:** Migration framework; PITR/backup; encryption-at-rest key management; projector rebuild procedure.
- **Over-engineering:** Supporting both Postgres and DynamoDB *and* full CQRS *and* hash-chain from the start.
- **Under-engineering:** Concurrency control; migrations; DR.
- **Future extensibility:** DAO abstraction is good where semantics actually match; leaks where they don't (outbox).

## 7. Queue, Streaming & Scalability ([06-queue-and-scalability.md](06-queue-and-scalability.md))

- **Strengths:** Per-tool queues + weighted-fair scheduling by org is the correct anti-starvation design; visibility-timeout/lease + DLQ; sandbox-per-scan; single-source-of-truth streaming (dashboard and chat as equal subscribers) is elegant.
- **Weaknesses:** GF-9 (progress through outbox contradicts Redis-live claim). Cooperative cancellation only ([§7.2](06-queue-and-scalability.md)) — a 20-minute `active_scan` won't stop; no hard-kill of the sandbox for runaway/abusive jobs. Scale-to-zero worker pools ([§7.2](06-queue-and-scalability.md)) impose cold-start (image pull + sandbox spin-up) on "interactive" priority jobs — the exact jobs a human is waiting on in Slack. ETA computed from "stage weights × historical durations" — cold-start problem for a new tool/target with no history.
- **Scalability risks:** Streaming Gateway SSE fan-out — thousands of concurrent connections, each gateway replica presumably consuming the whole bus and filtering; connection/sticky-session and slow-consumer backpressure undesigned. Two messaging systems to scale (GF-6).
- **Security concerns:** Sandbox egress allow-list is the *only* target control and it's the wrong layer (GF-2).
- **Operational concerns:** DLQ raises an alert but no triage/replay tooling; lease-expiry redelivery can double-run a non-idempotent scan (side effects on the target!) — at-least-once execution of an *active scan* is dangerous and unaddressed.
- **Enterprise concerns:** Reserved capacity lanes mentioned; no quota/credit enforcement to stop cost blowout (GF-13).
- **Missing concepts:** Hard-kill cancellation; SSE backpressure/scaling; at-least-once *execution* safety for side-effecting scans; cold-start mitigation.
- **Over-engineering:** Three queue substrates echoing three bus substrates.
- **Under-engineering:** Cancellation; streaming scale; ETA cold start.
- **Future extensibility:** Per-tool pool model matches the tool convention well.

## 8. Notification Architecture ([07-notification-architecture.md](07-notification-architecture.md))

- **Strengths:** Six-stage pipeline is well-factored; throttle/batch/retry/circuit-breaker are all present and correct; severity-bypass for critical alerts; preference precedence model is clear; per-(event×channel) versioned templates.
- **Weaknesses:** Redis-centric throttle/dedup failure mode undefined (GF-5) — fail-open spams users, fail-closed drops critical alerts, and the doc doesn't choose. "Redaction is a template-time guarantee" — but a template is authored by a human and could inline content; "would fail review" is a process hope, not a control. Escalation to PagerDuty/on-call is described but PagerDuty is another cloud dependency (air-gap, GF-1).
- **Scalability risks:** Per-destination global cap + per-job token buckets = many Redis keys; at thousands of concurrent jobs the throttle store itself is hot.
- **Security concerns:** Outbound message is a data-exfiltration path in a security product; only source-redaction defends it — no egress DLP, no per-channel classification policy (e.g., never send `critical` PII detail to a public channel).
- **Operational concerns:** NotificationFailed → DLQ is good; no digest of *undelivered* critical alerts (a dropped page is a silent incident despite the audit row).
- **Enterprise concerns:** No per-tenant channel governance (which channels may receive which severities), required for enterprise data-handling policies.
- **Missing concepts:** Channel-classification policy; delivery-SLA per severity; failure-of-Redis behavior.
- **Over-engineering:** Batching digests are fine; not excessive.
- **Under-engineering:** Egress DLP; Redis-down semantics.
- **Future extensibility:** `NotificationChannelPort` is the right seam; adding a channel is genuinely additive.

## 9. ChatOps Architecture ([08-chatops-architecture.md](08-chatops-architecture.md))

- **Strengths:** Hexagonal boundary is crisp; the "may/may-not" table per layer is an excellent governance artifact; two-ack pattern (transport ack in 3s + domain ack) correctly handles Slack's deadline; declarative command specs share one validated/authorized/audited path.
- **Weaknesses:** GF-3 (identity binding) and GF-2 (target authz) both live here and are the two most security-critical flows in the platform — both undefined. Session state in Redis (GF-5). Interaction-token handling for buttons named, not specified (expiry, replay, one-time use).
- **Scalability risks:** Stateless replicas + Redis session is fine; the Redis dependency is the ceiling.
- **Security concerns:** The entire untrusted-input surface enters here; there is no input-validation/authorization spec beyond "authorize via core RBAC," and RBAC is meaningless without a trustworthy identity (GF-3).
- **Operational concerns:** Slash-command 3s deadline vs core RBAC lookup + DTO build + API call — if the core ack path exceeds 3s under load, UX degrades; no budget stated.
- **Enterprise concerns:** No per-workspace admin controls (which commands are allowed in which channels), needed for enterprise governance.
- **Missing concepts:** Verified account-linking flow; command-authorization against asset inventory; interaction-token security.
- **Over-engineering:** —
- **Under-engineering:** Identity, authorization, input validation — the security core of a ChatOps tool.
- **Future extensibility:** Command-registry-as-data is excellent for adding commands.

## 10. Observability ([09-observability.md](09-observability.md))

- **Strengths:** Correlation via `job_id`/`trace_id` across signals is exactly right; metrics derived from the event stream (not hand counters) is a strong, consistent choice; `outbox_lag` as a data-integrity canary is a nice touch; sensible metric set; log redaction mandated.
- **Weaknesses:** Metrics-from-events means **metrics inherit the event stream's at-least-once duplication** — counters like `ghub_jobs_total` will over-count on redelivery unless the projector dedups (unspecified). Prometheus cardinality bomb: `{org}` label at 100k orgs on multiple metrics will destroy Prometheus — this is a classic mistake and it's written into the metric table.
- **Scalability risks:** Per-org label cardinality (100k × tools × statuses) is unshippable on vanilla Prometheus; needs recording rules/exemplars/a different TSDB or org aggregation.
- **Security concerns:** Log redaction asserted; no mention of trace/span attribute redaction (traces leak params too).
- **Operational concerns:** No SLOs/error budgets defined; alerts listed but no runbook linkage.
- **Enterprise concerns:** Air-gapped needs the whole OTel/Prom/Grafana stack shipped and supported offline — acknowledged only implicitly.
- **Missing concepts:** Cardinality strategy; metric dedup; SLO catalog; trace redaction.
- **Over-engineering:** —
- **Under-engineering:** Cardinality control is a real gap.
- **Future extensibility:** OTel exporter swap is genuinely portable.

## 11. Deployment ([11-deployment.md](11-deployment.md))

- **Strengths:** Clear target topology; profile table acknowledges SaaS/self-hosted/enterprise differences; evolutionary path §11.4 is the most important section in the whole set and is realistic; KEDA/HPA choices sound.
- **Weaknesses:** GF-1 (air-gapped chat impossibility) is precisely where this document should confront reality and instead lists Slack/Teams for all profiles. "One artifact set, three profiles" is contradicted by the DynamoDB/Kafka/managed-service assumptions that don't exist air-gapped. No CI/CD design though it's called out as absent today.
- **Scalability risks:** Multi-AZ named; multi-region absent (GF-11/12).
- **Security concerns:** Secrets per profile mentioned (Vault/KMS/.env) but the multi-tenant token store (GF-4) isn't in the topology.
- **Operational concerns:** No CD pipeline, no progressive-delivery/canary spec, no schema-migration deploy ordering (with no ORM this is manual and dangerous).
- **Enterprise concerns:** Air-gapped chat; offline package/update mechanism for enterprise; license/entitlement enforcement — none present.
- **Missing concepts:** Air-gapped channel strategy; CI/CD; migration/deploy ordering; DR/multi-region topology.
- **Over-engineering:** Full K8s topology is target-appropriate; fine.
- **Under-engineering:** The four hard profiles are named but only two (SaaS/self-hosted) are actually designed.
- **Future extensibility:** Profile-by-config is the right model *if* the air-gapped channel gap is fixed.

## 12. Folder Structure ([12-folder-structure.md](12-folder-structure.md))

- **Strengths:** Faithfully extends the existing `mcp-server/app/` layering and the ZAP tool convention; "no new top-level role" decision is correct and defensible; dependency-direction diagram matches the standard; explicit "what is deliberately not here."
- **Weaknesses:** A single `mcp-server/app/` housing API + ChatOps + Notification + Job orchestration + workers + projectors is a **modular monolith**, yet the deployment doc scales these as independent services — the repo/module boundary and the deployment boundary diverge with no story for how one app image becomes many deployables (feature flags? separate entrypoints? build targets?). `workers/` and `projector_main.py` as entrypoints in the same package imply one image, many roles — viable but unstated as a decision.
- **Scalability risks:** Monolith-to-services extraction cost if boundaries blur (they will without enforcement).
- **Security concerns:** `integrations/chat` holding provider SDKs and tokens — token-handling boundary not called out.
- **Operational concerns:** One image for many roles complicates least-privilege (a worker image shouldn't carry Slack tokens).
- **Enterprise concerns:** —
- **Missing concepts:** Deployable-unit boundary vs module boundary; per-role images/permissions.
- **Over-engineering:** —
- **Under-engineering:** Module-to-service extraction strategy.
- **Future extensibility:** Layout is clean and additive; good.

## 13. Extensions / Tech / Risks / Trade-offs / Best Practices ([13-extensions-tech-risks.md](13-extensions-tech-risks.md))

- **Strengths:** Extension-point table is concrete and mostly true; tech choices are justified against alternatives; the risk table already self-identifies several real issues (notification storms, PII leakage, outbox lag, noisy neighbor) — credit for candor; best-practices list is sound.
- **Weaknesses:** The risk register **misses its own biggest risks**: air-gapped chat (GF-1), target/SSRF authorization (GF-2), identity spoofing (GF-3), token-store (GF-4), hash-chain-vs-stream (GF-7), and DR/residency (GF-11/12). Three-bus support is presented as extensibility but is an operational liability (GF-6). "PII leakage mitigation: redact at source" is repeated as if solved.
- **Scalability risks:** Trade-off table is honest about eventual consistency but not about the Prometheus cardinality or SSE fan-out costs.
- **Security concerns:** Security risks under-weighted for a security product; needs a real threat model (STRIDE) rather than a risk table.
- **Operational concerns:** No mention of the migration/DR/CI-CD gaps.
- **Enterprise concerns:** Entitlements/licensing/air-gapped update absent.
- **Missing concepts:** Threat model; cost model; capacity model; the six missing risks above.
- **Over-engineering:** Explicitly flags some; misses the three-bus one.
- **Under-engineering:** Security and DR sections.
- **Future extensibility:** The extension table is the best single artifact for onboarding new integrators.

## 14. ADR 0004 ([0004-chatops-platform-architecture.md](../../.ai/decisions/0004-chatops-platform-architecture.md))

- **Strengths:** Correctly formatted to the repo's ADR contract; strong context/rationale; alternatives-rejected table is genuinely reasoned; ties to guardrails and standards; status honestly "Proposed."
- **Weaknesses:** Scopes itself to "architecture" and defers the hardest questions (identity, target authz, air-gapped channels, DR) to "follow-on decisions" — but several of those are load-bearing enough that approving 0004 without them is approving a hole. The ADR should at minimum record them as **explicit open questions with owners**, as the repo's own Decision practice ("capture options considered … at the time") implies.
- **Everything else:** N/A — it's a decision record, not a runtime component.

---

## Prioritized Findings

### 🔴 Critical (must fix before any approval — these are correctness/safety holes, not polish)

1. **Target authorization / SSRF (GF-2).** User-supplied `target` from chat with no binding to an owned, verified asset inventory turns the platform into an attack proxy. Add an Asset/Target context, verified ownership, and admission-time authorization. *Blocks approval.*
2. **Chat-identity → Actor binding & anti-spoofing (GF-3).** RBAC is worthless without a trustworthy identity. Define verified account-linking, un-linked-user handling, and per-workspace trust boundaries.
3. **Audit hash-chain vs at-least-once/reordered event stream (GF-7).** The tamper-evidence guarantee is currently unimplementable as specified. Choose one coherent model (synchronous audit write on the command path, or Merkle/periodic anchoring) and resolve the ordering/dedup contract.
4. **Air-gapped ≠ cloud chat (GF-1).** The flagship channels cannot run air-gapped. Redefine the air-gapped channel strategy (self-hosted chat / email / webhooks) and stop listing Slack/Teams as universal.

### 🟠 High

5. **Multi-tenant token/secret storage (GF-4)** — design the encrypted, rotatable, per-installation token store.
6. **Idempotency key derived + time-bucketed (GF-8)** — switch to a client-supplied provider delivery id.
7. **Progress events through the durable outbox (GF-9)** — route ephemeral progress Redis→gateway; keep only lifecycle transitions in the outbox.
8. **Outbox does not port to DynamoDB (GF-10)** — specify Dynamo Streams path; stop claiming the DAO hides it.
9. **Redis system-wide SPOF (GF-5)** — analyze and specify fail-open/closed behavior for throttle, dedup, cancellation, sessions.
10. **Cross-producer event ordering** — add per-job monotonic sequence; define consumer reordering rule.
11. **At-least-once *execution* of side-effecting scans** — lease-expiry redelivery can double-run an active scan against a live target; needs execution-idempotency or single-flight guarantee.
12. **No DR / RPO-RTO / multi-region / residency (GF-11, GF-12)** — required for enterprise; currently absent.
13. **Prometheus per-`org` label cardinality (doc 10)** — will collapse Prometheus at 100k orgs; redesign the metric label strategy.
14. **Migrations story absent (docs 6, 11)** — no-ORM + partitioned + two providers demands a real, tested migration/deploy-ordering framework.
15. **Two messaging systems + three bus backends (GF-6)** — reduce to one substrate that runs in every profile.

### 🟡 Medium

16. Read-your-writes on `/status` after `/run` (serve single-job reads from the write store).
17. Hard-kill cancellation path for long stages / runaway jobs (cooperative-only is insufficient).
18. Streaming-gateway SSE fan-out scaling + slow-consumer backpressure.
19. Report-link (`/report`) per-requester authorization, signed/expiring URLs.
20. Webhook anti-replay (timestamp window + nonce), not just signature.
21. Cursor pagination + hard caps on list endpoints (millions of jobs).
22. Egress DLP / channel-classification policy for notifications (defense-in-depth beyond source redaction).
23. Optimistic-concurrency (row version) on the Job aggregate.
24. Cold-start mitigation for scale-to-zero interactive workers; ETA cold-start.
25. Modular-monolith → independent-services deployable-boundary strategy (doc 12 vs doc 11).
26. Schema-registry governance + consumer contract tests.
27. Tenant lifecycle context (provisioning/offboarding/export/delete) for GDPR.
28. Quota/credit enforcement to cap cost and free-tier abuse (GF-13).

### 🟢 Low

29. Drop the "optional gRPC" mention or design it.
30. `result_ref` should model multiple artifacts.
31. Trace/span attribute redaction (not just logs).
32. Metric dedup in the projector (at-least-once over-counting).
33. Interaction-token security spec (expiry/one-time-use).
34. Non-functional requirements/SLO catalog stated explicitly up front.
35. Trust-boundary overlay on the C4 diagrams.

---

## Architecture Score

| Dimension | Weight | Score | Weighted | Notes |
|---|---:|---:|---:|---|
| Architectural soundness (patterns, boundaries) | 20 | 17/20 | 17 | Hexagonal + event-driven + bounded contexts are correct and disciplined. |
| Scalability | 15 | 9/15 | 9 | Right instincts (per-tool queues, partitioning, CQRS) undercut by outbox-progress, cardinality, SSE fan-out, hash-chain serialization. |
| Security | 20 | 9/20 | 9 | Unacceptable for a *security* product: target authz, identity, token store, egress DLP all missing. Biggest single drag. |
| Operational maturity | 10 | 5/10 | 5 | No DR, migrations, CI/CD, SLOs; Redis SPOF. |
| Enterprise/air-gapped readiness | 10 | 4/10 | 4 | Air-gapped chat contradiction, no residency/DR/entitlements. |
| Extensibility | 10 | 9/10 | 9 | Ports + event subscription + tool convention are genuinely excellent. |
| Data architecture | 10 | 6/10 | 6 | Good decomposition; outbox/Dynamo leak, hash-chain, migrations, concurrency gaps. |
| Documentation quality & honesty | 5 | 5/5 | 5 | Clear, diagrammed, G5-honest about planned-vs-built. |
| **Total** | **100** | | **64/100** | |

**Score: 64 / 100** — *A strong skeleton with the right bones and a security/operational surface that is not yet safe to build against.*

---

## Recommendation

### ⚠️ APPROVE WITH CHANGES — conditional, blocking on the four Criticals.

**Rationale.** The core architecture is directionally correct and, unusually, honest about what is real. Hexagonal boundaries, event-driven decoupling, the bounded-context ownership line, and the extensibility model are the hard things to get right, and they *are* right. None of the defects require a redesign — they are gaps and inconsistencies inside a sound frame, which is exactly what "approve with changes" is for rather than "reject."

**However**, this is a security product, and the design currently has **four Critical holes** — target/SSRF authorization, identity binding, an unimplementable audit-integrity guarantee, and an air-gapped claim that is physically false. Shipping against this as-is would put the product's own trustworthiness at risk (the exact thing guardrails G2/G3/G4 exist to protect).

**Conditions for full approval:**

1. Resolve all four **Critical** findings in the design docs and in ADR 0004 (or a superseding ADR 0005), with the security items backed by a written STRIDE threat model.
2. Down-scope the build to the **evolutionary path** ([§11.4](11-deployment.md)): ship the spine (queue + outbox-lifecycle-only + one channel + notification) and *defer* CQRS, hash-chain audit, the second DB provider, and multi-bus support behind explicit later decisions. Do not build the cathedral before the first channel works.
3. Record the remaining **High** findings as tracked, owned open questions in the ADR — approval does not mean they vanish.

**Re-review** required after the four Criticals and the threat model land. Target post-remediation score: ≥ 82/100.

---

## Board sign-off

| Concern owner | Position |
|---|---|
| Security | **Reject until Criticals 1–3 + threat model.** Non-negotiable for a security product. |
| Scalability | Approve with changes; Highs 6–15 before GA. |
| Operations | Approve with changes; DR/migrations/CI-CD are GA blockers, not design blockers. |
| Enterprise | Approve with changes; air-gapped channel strategy (Critical 4) before any enterprise commit. |
| Architecture (chair) | **Approve with changes.** The frame is sound; fix the four holes, down-scope the build, re-review. |
