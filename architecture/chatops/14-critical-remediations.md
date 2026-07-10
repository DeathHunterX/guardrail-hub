# Critical Remediations

> Resolves the four **Critical** findings from [REVIEW-BOARD.md](REVIEW-BOARD.md). Scope was deliberately constrained to the Criticals only; High/Medium/Low findings remain tracked but unaddressed here. Changes are **minimal, additive, and backward-compatible** except one intentional breaking change (job creation now requires `asset_id`). ADR-0004 stays **Proposed** — nothing here accepts it.

Owner: Loi Phan · Date: 2026-07-07

Guiding constraints honored: preserve the original vision (adapter-only bot, event-driven core, hexagonal ports), minimal change, no gratuitous complexity, backward compatibility where possible.

---

## C1 — Target authorization / SSRF (was GF-2)

**1. Why it exists.** `/run security_scan target=<free text>` accepted an arbitrary, user-typed target from a chat channel and passed it to the scanner. Nothing bound the target to something the org actually owns, so anyone with chat access could aim the platform at a third party or an internal metadata endpoint — turning a security product into an attack proxy / SSRF engine. G4 was cited but only at the sandbox egress layer, which is too late.

**2. Architectural change.** Introduce a small **Asset** aggregate and an **Asset Registry** bounded context. A Job now references an ownership-`VERIFIED` `asset_id`, never free text. Authorization happens at **admission in the Guardrail API** (the core), which refuses any job whose asset is unregistered or unverified. The asset's `egress_allow` still feeds the sandbox as defense-in-depth. The bot is untouched in spirit — it still just forwards a command; the *core* decides.

**3. Trade-offs.** Adds a registration/verification step before a target can be scanned (friction, and a new proof-of-ownership flow to build) and removes ad-hoc "scan any URL" from chat. That loss is the entire point — unrestricted targeting is the vulnerability. Cost is one new aggregate, one context, two endpoints; no change to the event or queue design.

**4–9. Artifacts updated.** Domain model ([02 §3.1, §3.2, §3.6](02-domain-model.md)) adds `Asset` + `Job.asset_id`; bounded contexts ([01](01-bounded-contexts.md)) add the Asset Registry context and ACL edge; API ([04 §5.2, §5.4, §5.6](04-api-design.md)) adds asset endpoints, the `asset_id` field, and the admission rule; database ([05 §6.2, §6.5](05-database-design.md)) adds the `assets` table + Dynamo access pattern; ChatOps flow ([08 §9.2, §9.3](08-chatops-architecture.md)) and sequences ([10 §10.1, §10.6](10-sequence-diagrams.md)) show admission; event catalog ([03 §4.4b](03-event-catalog.md)) adds `command.rejected.v1{unauthorized_target}`; folders ([12](12-folder-structure.md)) add `services/assets`, `assets_dao`, `assets_router`.

---

## C2 — Chat-identity spoofing (was GF-3)

**1. Why it exists.** The design resolved a Slack user to an Actor but never specified *how*, and never verified the binding. In a shared channel, a naive resolution lets any member trigger privileged commands as though they were a trusted actor. RBAC is meaningless when the identity feeding it is unauthenticated. This is the platform's front door and it was undefended.

**2. Architectural change.** Add a one-time **verified account-linking** flow and an **Installation** entity that binds one chat workspace to exactly one org. A `ChatIdentity` now carries `verification_status`; resolution succeeds only for a `VERIFIED` identity **within its installation's org**. Unlinked or cross-org identities cannot act. Linking is a code issued in the authenticated web app and confirmed from chat — no new identity provider, reusing existing auth.

**3. Trade-offs.** Users must link their chat account once before issuing commands (onboarding friction), and we store per-identity verification + installation bindings. In exchange, spoofing and cross-tenant confusion become impossible by construction. No change to the command execution path beyond an admission check.

**4–9. Artifacts updated.** Domain model ([02 §3.1, §3.6](02-domain-model.md)) adds `Installation` + `ChatIdentity.verification_status`/`installation_id`; contexts ([01](01-bounded-contexts.md)) strengthen Identity & Access; API ([04 §5.6](04-api-design.md)) adds link start/confirm/revoke + the identity clause in the admission rule; database ([05 §6.2, §6.5](05-database-design.md)) adds `installations` + `verification_status`; ChatOps ([08 §9.2, §9.3, §9.4](08-chatops-architecture.md)) requires verified identity and adds installation→org scoping; sequences ([10 §10.6](10-sequence-diagrams.md)) add the linking flow; event catalog ([03 §4.4b](03-event-catalog.md)) covers `unverified_identity` rejections.

---

## C3 — Audit hash-chain over an at-least-once stream (was GF-7)

**1. Why it exists.** The design said the audit ledger was *derived from* the event bus **and** protected by a per-tenant `prev_hash → hash` chain. Those two claims are incompatible: the bus is at-least-once, multi-producer, and reorderable, but a hash chain requires a single, totally-ordered, exactly-once append. As written, the tamper-evidence guarantee was unimplementable.

**2. Architectural change.** Decouple the ledger from the bus. The audit row is now written **synchronously and transactionally by the service that owns the state transition**, taking the next per-tenant monotonic `tenant_seq`; the hash is computed as `H(prev_hash || tenant_seq || canonical(payload))` over that sequence. The bus still carries `audit.*` events, but only as *derived* projections for notifications/metrics — never the source of truth. A dropped or reordered bus message can no longer corrupt the ledger.

**3. Trade-offs.** The audit write moves onto the transactional critical path (a small latency cost) and introduces per-*tenant* serialization for sequence allocation. This is bounded (per org, not global) and batchable; if a whale org ever makes it a hotspot, the chain migrates to periodic Merkle anchoring with no table-shape change. We give up the elegant "audit is pure projection" story in exchange for a guarantee that actually holds.

**4–9. Artifacts updated.** Domain model ([02 §3.5](02-domain-model.md)) rewrites Audit-vs-events and adds `AuditEvent.tenant_seq`; database ([05 §6.1, §6.2](05-database-design.md)) makes the write transactional, adds `tenant_seq` + `UNIQUE(org_id, tenant_seq)`, and updates the store diagram + Dynamo audit key; event catalog ([03 §4.1, §4.4b](03-event-catalog.md)) relabels the audit consumer as a derived projection and adds the correctness note; sequences ([10 §10.1](10-sequence-diagrams.md)) show audit written in the same txn as the job row. No API change.

---

## C4 — Air-gapped ≠ cloud chat (was GF-1)

**1. Why it exists.** Slack, Discord, and Teams are cloud SaaS requiring outbound internet. The deployment matrix listed them for **every** profile, including air-gapped — where there is no egress, so those channels physically cannot work. The "one artifact, all profiles" claim was false for the flagship channel.

**2. Architectural change.** Classify channels as **cloud** (Slack/Discord/Teams) vs **self-hostable** (Mattermost/Rocket.Chat/Matrix, internal SMTP, internal webhooks). All implement the existing `NotificationChannelPort`, so the air-gapped profile simply **enables the self-hostable set and disables the cloud set by configuration**. No core change — this is exactly the swap the hexagonal design already anticipated; we add a Mattermost adapter as the air-gapped reference channel and make the constraint explicit. Escalation targets follow the same rule (internal Alertmanager/webhook/email air-gapped).

**3. Trade-offs.** Air-gapped customers get a self-hosted chat, not Slack, with minor presentation differences across channel card formats; we must build and support the Mattermost adapter. The original vision is preserved — one codebase, profile-by-config — it is just made honest about which channels each profile can run.

**4–9. Artifacts updated.** Notification ([07 §8.8, §8.9](07-notification-architecture.md)) adds the channel-class model + Mattermost adapter; deployment ([11 §11.1 diagram, §11.2](11-deployment.md)) corrects the external-channel node, adds the chat-channels matrix row, and states the air-gapped strategy; README ([principle 8](README.md#3-design-principles)) records it at the vision level; folders ([12](12-folder-structure.md)) add `mattermost_adapter.py`. No domain, API, or event change.

---

## Backward compatibility

| Aspect | Compatible? | Note |
|---|---|---|
| Existing `/v1` read endpoints (`/status`, `/jobs`, `/history`, `/report`) | ✅ Unchanged | Shapes preserved. |
| Integration event envelope + `.v1` types | ✅ Additive | New `command.rejected.v1`; existing events unchanged. |
| Domain model | ✅ Additive | New `Asset`/`Installation`; new fields (`asset_id`, `tenant_seq`, `verification_status`) added, none removed. |
| Persistence (Postgres/DynamoDB via DAO) | ✅ Preserved | New tables/items only; no provider change. |
| Notification ports/adapters | ✅ Preserved | New adapter + a config flag; port unchanged. |
| **Job creation** | ⚠️ **Breaking** | `asset_id` now required. Deliberate security fix — the one intentional break. |

---

## Change Summary

Every document modified in this remediation:

| Document | C1 | C2 | C3 | C4 | What changed |
|---|:--:|:--:|:--:|:--:|---|
| [README.md](README.md) | | | | ● | Design principles 7 & 8 (authorize what/who; deployment-aware channels); deliverables-map rows. |
| [01-bounded-contexts.md](01-bounded-contexts.md) | ● | ● | ● | | Context map + table: Asset Registry context; verified identity in Identity & Access; transactional Audit; ubiquitous-language `Asset`. |
| [02-domain-model.md](02-domain-model.md) | ● | ● | ● | | Class diagram + tables: `Asset`, `Installation`, `Job.asset_id`, `ChatIdentity.verification_status`, `AuditEvent.tenant_seq`; rewritten Audit-vs-events; new §3.6. |
| [03-event-catalog.md](03-event-catalog.md) | ● | ● | ● | | §4.1 audit relabelled derived; new §4.4b `command.rejected.v1` + audit-ledger correctness note. |
| [04-api-design.md](04-api-design.md) | ● | ● | | | `asset_id` on job create + 403 admission; `/run` mapping; new §5.6 asset + identity-linking endpoints + admission rule. |
| [05-database-design.md](05-database-design.md) | ● | ● | ● | | `assets` + `installations` tables; `verification_status`; transactional audit with `tenant_seq` + `UNIQUE`; store diagram; Dynamo access patterns. |
| [07-notification-architecture.md](07-notification-architecture.md) | | | | ● | Mattermost adapter; new §8.9 cloud vs self-hostable channel classes. |
| [08-chatops-architecture.md](08-chatops-architecture.md) | ● | ● | | | May/may-not table; §9.3 command lifecycle now shows admission + rejection; installation→org scoping. |
| [10-sequence-diagrams.md](10-sequence-diagrams.md) | ● | ● | ● | | §10.1 admission + audit-in-txn; new §10.6 verified linking + rejected target. |
| [11-deployment.md](11-deployment.md) | | | | ● | External-channel node; chat-channels matrix row; air-gapped channel-strategy note. |
| [12-folder-structure.md](12-folder-structure.md) | ● | ● | ● | ● | `services/assets`, `services/identity`, `assets_dao`/`installations_dao`, `assets_router`, `mattermost_adapter`; audit-dao note. |
| [.ai/decisions/0004-...md](../../.ai/decisions/0004-chatops-platform-architecture.md) | ● | ● | ● | ● | New "Critical remediations applied" section. **Status unchanged: Proposed.** |
| [14-critical-remediations.md](14-critical-remediations.md) | ● | ● | ● | ● | This document (new). |

**Unchanged** by this remediation: [06-queue-and-scalability.md](06-queue-and-scalability.md), [09-observability.md](09-observability.md), [13-extensions-tech-risks.md](13-extensions-tech-risks.md) — none of the four Criticals touch queue/streaming, observability, or the tech/risk register. Their High/Medium findings remain open by design.

---

## What is explicitly NOT fixed here

Per the "Criticals only" scope, these review-board items remain open and are **not** resolved: multi-tenant token storage (H), derived idempotency key (H), progress-through-outbox (H), Dynamo outbox semantics (H), Redis SPOF (H), cross-producer ordering (H), at-least-once *execution* of scans (H), DR/multi-region/residency (H), Prometheus cardinality (H), migrations framework (H), single-vs-multi bus (H), and all Medium/Low items. They must be addressed before GA, but they do not block the architecture decision the way the four Criticals did.
