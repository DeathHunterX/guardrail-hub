# Guardrail Hub ChatOps — Evolution Plan

> Derived from the approved **North Star Architecture** ([README](README.md) + docs 01–14). This plan **phases** the existing components; it introduces no new service, context, event, or pattern. Every component named here already exists in the North Star — this document only decides *when each is built, why it waits, and how it migrates*.

Owner: Loi Phan · Date: 2026-07-07

## How to read this

Four stages, aligned with the already-approved deployment profiles ([11-deployment §11.2](11-deployment.md)) and the security tiers ([SECURITY-PRIORITIZATION](SECURITY-PRIORITIZATION.md)), and with the evolutionary path already sketched in [11-deployment §11.4](11-deployment.md):

| Stage | Meaning | Profile | Security tier | Scale target |
|---|---|---|---|---|
| **1 — Foundation** | The MVP spine; the loop works end-to-end for a pilot | Self-hosted / small SaaS | A (MVP) | 1s–10s orgs |
| **2 — Growth** | Commercial SaaS GA; breadth + hygiene to sell | Managed SaaS | B (SaaS GA) | 100s–1,000s orgs |
| **3 — Scale** | 100k orgs, millions of jobs, thousands of concurrent scans | SaaS at scale | (High register) | 100k orgs |
| **4 — Enterprise** | Enterprise + regulated + air-gapped | Enterprise / air-gapped | C + D | Dedicated / regulated |

**Complexity legend:** S = days · M = weeks · L = months · XL = multi-quarter.
**Current status** is grounded in what exists in code today per [intelligence/system-overview](../../.ai/intelligence/system-overview.md): only the ZAP MCP path, the pluggable DAO (Postgres/DynamoDB), a ZAP Docker container, static report files, and Docker Compose. Everything else is "not started." `pyjwt`/`bcrypt` are declared-unused.

---

## Evolution Matrix

Cells describe the **target state at the end of that stage**. Blank-ish stages inherit the previous unless noted.

### Edge & ChatOps
| Component | Current | Stage 1 — Foundation | Stage 2 — Growth | Stage 3 — Scale | Stage 4 — Enterprise |
|---|---|---|---|---|---|
| Inbound chat adapters | none | Slack only | + Discord, Teams, CLI | HA, rate-limited | + Mattermost (air-gap); per-workspace admin |
| ChatOps core (cmd/session/ACL) | none | /run,/status,/help + session + admission | full command set + buttons | stateless HA replicas | command governance, break-glass UX |
| Outbound channel adapters | none | Slack + email | Discord/Teams, rich cards | per-dest caps, breakers | self-hosted; classification-aware |

### API & Domain
| Component | Current | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|---|---|---|---|---|---|
| Guardrail API (+admission) | partial (ZAP, history) | jobs CRUD + admission + idempotency | full query set + asset/identity endpoints | cursor paging, reads from projections, rate tiers | mTLS/private-link, per-tenant scopes |
| Identity & Access | schema only | verified linking + Installation + basic RBAC | full RBAC + token lifecycle/revocation | scaled auth + caching | SCIM, dual-control/break-glass, MFA, SPIFFE |
| Asset Registry | none | register + ownership-verify + admission gate | asset lifecycle, richer kinds | admission-lookup caching | governance/attestation, residency tags |
| Job Service | none (inline ZAP) | async lifecycle + 1 queue + cancel + outbox | retry, multi-tool, priority lanes | per-tool queues, fair scheduling | reserved capacity / quotas |
| Evaluation Engine + tools | ZAP only | ZAP-as-worker + 1–2 core tools | broaden tool set | per-tool scaling, ETA model | tool governance, custom detectors |
| Policy & Governance | none | minimal pass/fail | baselines + regression alerts | scaled baseline compare | policy-as-code, approval gates |

### Messaging & Execution
| Component | Current | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|---|---|---|---|---|---|
| Event Bus + outbox | none | outbox + light bus, lifecycle events only | full event catalog + consumers | partition by org_id, scaled substrate | event signing, per-topic encryption, cross-region |
| Job Queue + scheduling | none | single durable queue + DLQ | per-tool queues + priority | weighted-fair per-org + autoscale | reserved lanes, cost quotas |
| Workers + sandbox | partial (ZAP container) | worker slice + sandbox + SSRF egress + cancel | multi-tool pools, retry-safe | KEDA autoscale, scale-to-zero | escape containment, FIPS, air-gap images |
| Streaming Gateway (SSE) | none | *deferred* (poll /status) | SSE progress (dash + CLI) | connection scaling, backpressure | within air-gap/enterprise nets |
| Notification Service | none | routing + templates + delivery | prefs, throttle, batch, retry, breaker | per-dest caps, dedup, digests | classification policy + egress DLP |

### Data
| Component | Current | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|---|---|---|---|---|---|
| Persistence / DAO | exists (PG/Dynamo) | + jobs/audit/outbox/assets/installations/prefs | read-model tables + migrations framework | partitioning + retention/drop | residency placement, at-rest KMS, PITR |
| CQRS read projections | none | *deferred* (read write-store) | projectors for /jobs,/history | scaled + rebuild tooling, whale orgs | residency-aware reporting |
| Redis (ephemeral) | none | sessions, cancel flag, dedup | + throttle buckets, live progress | HA/cluster, per-tenant namespacing | hardened isolation |
| Object store | partial (static files) | reports via result_ref | signed/expiring URLs + /report authz | lifecycle/retention tiers | residency, WORM-adjacent, KMS |
| Audit ledger | none | txn append-only + tenant_seq hash chain | full type coverage + projections | scaled per-tenant seq, batching | WORM + external anchor + SoD + 17a-4 |

### Platform & Cross-cutting
| Component | Current | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|---|---|---|---|---|---|
| Observability | logs only | structured logs + basic metrics + health | OTel traces + Prom + Grafana + alerts | cardinality strategy, SLOs | air-gap offline stack, tenant dashboards, evidence |
| Secret mgmt / KMS | .env / config | encrypted-at-rest basics (few tokens) | multi-tenant token store + rotation | scaled key hierarchy | FIPS 140-3 HSM, offline backend |
| Supply chain / CI-CD | none (lockfiles exist) | CI + pinned digests + basic scan | SBOM + signing/provenance + dep-confusion | continuous re-scan, registry hardening | SSDF attestation, signed offline updates |
| Deployment & orchestration | Compose (local) | Compose / small K8s, single region | K8s + Helm + HPA + staging/prod | multi-AZ, KEDA, DR/backup | multi-region/residency, air-gap, dedicated |
| Security controls (cross-cutting) | partial | SSRF egress (C1) + admission + TLS + secret hygiene | prompt-injection (C6) + supply chain (C5) + anti-replay | DoS/quota + event integrity | mTLS/SPIFFE, dual-control, WORM, classification (C3/C4) |
| Multi-tenancy & isolation | none | org/workspace/project scoping everywhere | per-tenant limits, logical isolation | partitioning + noisy-neighbor fairness | dedicated/crypto isolation, residency |

---

## Component detail

Each block: **Current status → Target status (Stage-4 end)**, then the seven required fields. Stage-by-stage targets are in the matrix above.

### Edge & ChatOps

**C1. Inbound chat adapters**
- Current → Target: none → all channels (Slack/Discord/Teams/CLI/Mattermost) behind `ChatCommandPort`, HA and rate-limited.
- Why deferred: one channel proves the whole loop; the rest are additive by design, so building them early is wasted breadth.
- Trigger: per-channel customer demand; a self-hosted/air-gapped deal triggers Mattermost.
- Migration strategy: add adapters that satisfy the existing port; no core change.
- Dependencies: ChatOps core, Guardrail API.
- Estimated complexity: S per adapter.

**C2. ChatOps core (commands / session / ACL)**
- Current → Target: none → full declarative command set, HA stateless replicas, per-workspace governance.
- Why deferred: MVP needs only launch/status/help; other commands are registry rows added on demand.
- Trigger: command demand (each new `/command`); GA for the full set.
- Migration strategy: add command specs to the registry; session state already externalized to Redis, so replicas scale without change.
- Dependencies: Guardrail API, Redis, Identity & Access.
- Estimated complexity: M (Stage 1), S per later command.

**C3. Outbound channel adapters**
- Current → Target: none → all delivery channels with breakers and classification-aware routing.
- Why deferred: mirrors inbound; delivery hygiene (caps, breakers) only matters as volume grows; classification is regulated-only.
- Trigger: channel demand; message volume (breakers); regulated tenant (classification).
- Migration strategy: `NotificationChannelPort` adapters + templates; additive.
- Dependencies: Notification Service.
- Estimated complexity: S each.

### API & Domain

**C4. Guardrail API (command/query + admission)**
- Current → Target: partial (ZAP + history) → full command/query surface with mTLS ingress and per-tenant scopes.
- Why deferred: the app exists; endpoints are added as each surface is needed rather than up front.
- Trigger: each surface need; scale drives cursor pagination and projection-backed reads.
- Migration strategy: additive routers within the existing FastAPI app (audience-split buckets already established).
- Dependencies: Job Service, Identity, Asset Registry, DAO.
- Estimated complexity: M.

**C5. Identity & Access**
- Current → Target: schema/JWT declared-unused → verified linking + full RBAC + SCIM + dual-control + service identity (SPIFFE).
- Why deferred: MVP needs verified identity + coarse roles (Tier A/B); SoD, SCIM, MFA are enterprise/regulated concerns.
- Trigger: GA (full RBAC, token lifecycle); enterprise/regulated (SCIM, dual-control, mTLS).
- Migration strategy: activate the declared `pyjwt`; add RBAC and linking additively; service identity introduced with the mesh at Stage 4.
- Dependencies: Guardrail API, Redis.
- Estimated complexity: L overall (M at Stage 1).

**C6. Asset Registry**
- Current → Target: none → governed, attested, residency-tagged asset inventory.
- Why deferred: born at Stage 1 (it is the SEC-C1 Tier-A control); governance/attestation is later.
- Trigger: MVP (security admission); enterprise (governance/attestation).
- Migration strategy: new aggregate + service wired into admission from Stage 1; later stages extend fields only.
- Dependencies: Guardrail API, Job Service, DAO.
- Estimated complexity: M.

**C7. Job Service**
- Current → Target: none (ZAP runs inline/synchronously today) → per-tenant orchestrated async lifecycle with fair scheduling and reserved capacity.
- Why deferred: generalize the existing inline ZAP execution into the worker/job model incrementally; fairness only matters at multi-tenant scale.
- Trigger: MVP (async is mandatory for long scans); scale (fair scheduling at many tenants).
- Migration strategy: extract the current ZAP service into a worker + job-lifecycle model behind ports; the ZAP path is the reference slice.
- Dependencies: Job Queue, Event Bus, DAO, Workers.
- Estimated complexity: L.

**C8. Evaluation Engine + tool slices**
- Current → Target: ZAP only → the full tool taxonomy with per-tool scaling and custom detectors.
- Why deferred: tools are additive per the `tools/<tool>/` convention; ship by product roadmap priority.
- Trigger: product roadmap per tool.
- Migration strategy: add `schemas/services/integrations/tools/<tool>/` slices exactly like ZAP; no orchestration change.
- Dependencies: Workers, integrations.
- Estimated complexity: M per tool.

**C9. Policy & Governance**
- Current → Target: none → baselines + regression detection + policy-as-code with approval gates.
- Why deferred: MVP shows raw findings; regressions require accumulated baselines (needs history first); governance is enterprise.
- Trigger: GA (regression alerts); enterprise (governance/approvals).
- Migration strategy: additive context consuming Evaluation output; emits the already-catalogued `security.*` events.
- Dependencies: Evaluation Engine, DAO, Event Bus.
- Estimated complexity: L.

### Messaging & Execution

**C10. Event Bus + outbox**
- Current → Target: none → partitioned, signed, encrypted, cross-region event backbone.
- Why deferred: MVP needs only a minimal reliable emit (outbox + light substrate); partitioning is a scale need; signing/encryption is regulated.
- Trigger: MVP (outbox for reliable notifications); scale (partition by org_id, substrate swap); regulated (signing/encryption).
- Migration strategy: substrate sits behind the event port — start on NATS/Redis Streams, swap to Kafka/Redpanda at Stage 3 without touching producers; events are versioned (`.v1`).
- Dependencies: DAO (outbox table), all producer services.
- Estimated complexity: L.

**C11. Job Queue + scheduling**
- Current → Target: none → per-tool, weighted-fair, quota-aware scheduling with reserved lanes.
- Why deferred: MVP runs on a single durable queue; per-tool isolation and fairness only pay off with multiple tools and many tenants.
- Trigger: multi-tool (per-tool queues); 100k-org fairness (weighted scheduling).
- Migration strategy: `JobQueuePort` abstracts the substrate; add queues and scheduling policy additively.
- Dependencies: Job Service, Workers.
- Estimated complexity: M.

**C12. Workers + sandbox / execution**
- Current → Target: partial (ZAP in Docker) → autoscaled, hardened, FIPS-capable, air-gap-image execution tier.
- Why deferred: reuse the existing ZAP container model for MVP; autoscaling and hardening follow load and assurance needs.
- Trigger: MVP (sandbox + SSRF egress, Tier A); scale (KEDA autoscale); regulated (escape containment, FIPS).
- Migration strategy: generalize the ZAP integration into a generic worker running a tool slice; sandbox network policy enforced from Stage 1.
- Dependencies: Job Queue, integrations, sandbox infrastructure.
- Estimated complexity: L.

**C13. Streaming Gateway (SSE)**
- Current → Target: none → scaled, backpressure-aware progress streaming.
- Why deferred: MVP can poll `/status`; live streaming is UX polish, not correctness.
- Trigger: GA UX (dashboard/CLI `--follow`); scale (connection fan-out).
- Migration strategy: additive router + bus consumer; reads snapshot from Redis on connect.
- Dependencies: Event Bus, Redis.
- Estimated complexity: M.

**C14. Notification Service**
- Current → Target: none → full pipeline with classification policy and egress DLP.
- Why deferred: MVP just delivers a message; throttle/batch/retry hygiene matures with volume; classification/DLP is regulated.
- Trigger: GA (prefs/throttle/retry); scale (caps/dedup/digests); regulated (classification/DLP).
- Migration strategy: pipeline stages added incrementally; each stage is an independent concern behind the same port.
- Dependencies: Event Bus, channel adapters, preferences DAO.
- Estimated complexity: L.

### Data

**C15. Persistence / DAO**
- Current → Target: exists (Postgres/DynamoDB) → residency-aware, encrypted, PITR-backed, partitioned stores.
- Why deferred: extend the existing DAO per-entity; partitioning at scale; residency/encryption for regulated.
- Trigger: each new entity (Stage 1–2); scale (partitioning/retention); regulated (residency/at-rest KMS).
- Migration strategy: additive tables via the hand-written DAO (no ORM); introduce a migration framework at Stage 2; partition existing tables at Stage 3.
- Dependencies: existing DAO layer.
- Estimated complexity: M.

**C16. CQRS read projections**
- Current → Target: none (reads hit write store) → scaled, rebuildable, residency-aware read models.
- Why deferred: at MVP volume the write store serves list reads fine; projections are needed only at millions of jobs.
- Trigger: list/query latency at volume.
- Migration strategy: add projector consumers; dual-read (write-store + projection) then cut over.
- Dependencies: Event Bus, DAO.
- Estimated complexity: M.

**C17. Redis (ephemeral state)**
- Current → Target: none → HA, per-tenant-namespaced, hardened cache/coordination tier.
- Why deferred: introduced with ChatOps for sessions/dedup/cancel; HA and isolation only matter at scale/regulated.
- Trigger: MVP (sessions/cancel/dedup); scale (HA/cluster, namespacing).
- Migration strategy: add Redis dependency at Stage 1; move to HA/cluster at Stage 3 (client-transparent).
- Dependencies: ChatOps core, Notification, Workers.
- Estimated complexity: S (Stage 1), M (HA).

**C18. Object store**
- Current → Target: partial (static report files) → residency-aware, retention-tiered, encrypted artifact store.
- Why deferred: static files suffice for a pilot; access control and lifecycle are GA/scale; residency is regulated.
- Trigger: GA (`/report` authz + signed URLs); scale (lifecycle); regulated (residency/retention).
- Migration strategy: move static files behind `result_ref` to S3-compatible storage (MinIO self-hosted); references in the DAO.
- Dependencies: DAO (refs), Guardrail API.
- Estimated complexity: M.

**C19. Audit ledger**
- Current → Target: none → WORM, externally-anchored, SoD-separated ledger meeting SEC 17a-4.
- Why deferred: MVP needs tamper-*evidence* (transactional hash chain); WORM/anchoring is regulated (Tier D).
- Trigger: MVP (ledger + chain); regulated (WORM/anchor/SoD).
- Migration strategy: additive; the Stage-4 WORM/anchoring attaches as a storage tier + notarization cadence **without changing the table shape** (as already noted in [05-database §6.2](05-database-design.md)).
- Dependencies: DAO, all state-transition services.
- Estimated complexity: M (Stage 1), L (Stage 4).

### Platform & Cross-cutting

**C20. Observability**
- Current → Target: logs only → full OTel/Prom/Grafana with cardinality strategy, SLOs, and offline air-gap stack.
- Why deferred: MVP needs minimal logging + health; the full stack is GA operations maturity.
- Trigger: GA ops (traces/metrics/dashboards); scale (cardinality/SLOs); regulated (offline + evidence).
- Migration strategy: OTel exporters added to services; a metrics projector consumes the bus (metrics derived from events, per the North Star).
- Dependencies: Event Bus, deployment.
- Estimated complexity: M.

**C21. Secret management / KMS**
- Current → Target: `.env`/config → FIPS 140-3 HSM, per-tenant keys, offline backend.
- Why deferred: MVP has few secrets (basic encrypted-at-rest, G1); the multi-tenant store is a SaaS-scale need (SEC-C2, Tier B); FIPS/offline is regulated.
- Trigger: GA (multi-tenant token store + rotation); regulated (FIPS/HSM, offline backend).
- Migration strategy: introduce KMS/Vault; migrate installation tokens into the store; rotate.
- Dependencies: Identity & Access, deployment.
- Estimated complexity: L.

**C22. Supply chain / CI-CD**
- Current → Target: none (lockfiles present) → SSDF-attested, signed, provenance-tracked pipeline with signed offline updates.
- Why deferred: a controlled pilot tolerates minimal CI; SBOM/signing (SEC-C5, Tier B) is needed to sell; attestation/offline is regulated.
- Trigger: GA (questionnaires demand SBOM/signing); regulated (SSDF/offline provenance).
- Migration strategy: stand up CI with pinned digests at Stage 1; layer SBOM/signing/provenance at Stage 2.
- Dependencies: deployment, all build artifacts (incl. scanner images).
- Estimated complexity: M (Stage 1), L (full program).

**C23. Deployment & orchestration**
- Current → Target: Docker Compose → multi-region/residency, air-gap-packaged, optionally dedicated-isolation deployment.
- Why deferred: start simple; grow infrastructure with load and customer tier.
- Trigger: GA (K8s + Helm); scale (multi-AZ + DR); regulated (air-gap/residency/dedicated).
- Migration strategy: Compose → Helm chart; additive infra; profiles by configuration (North Star property).
- Dependencies: every runtime component.
- Estimated complexity: L.

**C24. Security controls (cross-cutting)**
- Current → Target: partial → the full control set (SSRF, prompt-injection, supply chain, mTLS, dual-control, WORM, classification, residency, FIPS).
- Why deferred: sequenced exactly per [SECURITY-PRIORITIZATION](SECURITY-PRIORITIZATION.md) — Tier A at Stage 1, Tier B at Stage 2, Highs at Stage 3, Tier C/D at Stage 4.
- Trigger: per-finding tier (A→MVP, B→GA, D→regulated).
- Migration strategy: additive controls at the existing trust boundaries; no boundary is moved.
- Dependencies: many (spans the platform).
- Estimated complexity: L (spans stages).

**C25. Multi-tenancy & isolation**
- Current → Target: none → partitioned + fair + optionally dedicated/cryptographically-isolated, residency-aware tenancy.
- Why deferred: scoping is present from day one; hard isolation and residency are enterprise/regulated.
- Trigger: multi-tenant onboarding (Stage 1 scoping); scale (partitioning/fairness); regulated (residency/dedicated).
- Migration strategy: tenancy keys (`org/workspace/project`) exist from Stage 1; partitioning added at Stage 3 without schema redesign.
- Dependencies: DAO, Event Bus, Job Queue, Redis.
- Estimated complexity: L.

---

## Stage exit criteria (what "done" means per stage)

- **Stage 1 — Foundation:** one chat channel launches a real async job end-to-end, admission (asset+identity+RBAC) enforced, SSRF egress control live, tamper-evident audit, notifications delivered, reports stored. Pilot-ready.
- **Stage 2 — Growth:** multiple channels + core tool set, full command surface, prefs/throttle/retry, CQRS reads, OTel/Prom/Grafana, multi-tenant secret store, SBOM/signing, prompt-injection controls. Commercial-GA-ready.
- **Stage 3 — Scale:** org-partitioned data/bus/queue, per-tool autoscaled workers, weighted-fair scheduling, HA Redis, DR, cardinality-safe metrics. 100k-org-ready.
- **Stage 4 — Enterprise:** WORM/anchored audit, data-classification notifications, residency, dedicated isolation, mTLS/SPIFFE, dual-control, FIPS/HSM, air-gap packaging + signed offline updates. Regulated/air-gap-ready.

## Non-negotiables carried in every stage
Guardrails G1–G5 apply from Stage 1; the adapter-has-no-business-logic constraint, hexagonal ports, one-directional layering, and the pluggable DAO are invariant across all stages. No stage relaxes them.

*This plan phases the North Star; it does not alter it. Any future need that cannot be met by phasing an existing component would be a new architectural decision and is out of scope here.*
