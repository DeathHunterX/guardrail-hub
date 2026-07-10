# Security Criticals — Prioritization (classification only, no solutions)

Purpose: classify the six security Criticals from [SECURITY-REVIEW.md](SECURITY-REVIEW.md) into a maturity tier, so remediation can be sequenced against business milestones rather than fixed all at once. **This document does not propose fixes** — it decides *when each finding must be solved and why*.

Owner: Loi Phan · Date: 2026-07-07

**Tiers (a gate ladder — each tier inherits everything below it):**

- **A — Must-have for Guardrail Hub MVP.** Cannot expose even a pilot without it.
- **B — Required before commercial SaaS GA.** Can pilot without it; cannot sell broadly without it.
- **C — Required only for Enterprise.** Needed for large non-regulated customers.
- **D — Required only for Regulated Enterprise (Finance/Government).** Market-access gate for regulated deals.

> Note on the number of `C`s: none of the six Criticals is a pure "large-enterprise-but-unregulated" concern. The classic C-tier items (stronger tenant isolation, mTLS, RBAC dual-control, data residency) live in the **High** list, not among these Criticals. So the six split A / B / D only.

---

## Summary matrix

| ID | Finding | Tier | Impl. complexity | Operational cost | Maintenance cost | Impact if postponed |
|---|---|:--:|:--:|:--:|:--:|---|
| **SEC-C1** | SSRF (scan-time egress / TOCTOU) | **A** | Med | Low–Med | Low | Catastrophic, immediate — self-credential theft |
| **SEC-C2** | Multi-tenant secret/token store | **B** | High | Med–High | Med | Bounded pre-scale; mass-takeover post-scale |
| **SEC-C5** | Supply-chain assurance (SBOM/signing) | **B** | Med–High | Med | Med | Blocks deals; latent RCE vector |
| **SEC-C6** | Prompt injection on MCP tool surface | **B** | Med–High | Low–Med | Med | Brand-defining; re-opens tool abuse |
| **SEC-C3** | WORM / externally-anchored audit | **D** | High | High | High | None for A/B/C; blocks regulated deals |
| **SEC-C4** | Notification data-classification / cloud egress | **D** | Med–High | Med | Med | None commercially; classification breach for regulated |

Gate reading: **SEC-C1 before any internet-exposed pilot → SEC-C2/C5/C6 before commercial GA → SEC-C3/C4 before selling to finance/government.**

---

## SEC-C1 — SSRF (scan-time egress / TOCTOU) → **Tier A (MVP)**

**Why.** The platform's core action is emitting scan traffic *to a target*. Without egress restriction enforced at execution time, any actor — or a simple misconfiguration — can aim that traffic at internal services or the cloud metadata endpoint (`169.254.169.254`), which returns the platform's own IAM credentials: a self-compromise that escalates to full data-plane takeover. This is exploitable **today**, against the single ZAP tool that already exists, and does not depend on scale. The shipped admission fix (verify asset ownership once) reduced the naive vector but does not cover run-time DNS rebinding or redirects, so residual exposure remains. A scanner exposed to the internet without this is not shippable, even as a pilot.

**Implementation complexity — Medium.** A basic private-range + metadata denylist and disabling redirect-following is Low effort; full time-of-use hardening (re-resolution, IP pinning, per-scan network policy at the sandbox) is Medium and touches the worker/execution network layer.

**Operational cost — Low–Medium.** Primarily enforced in the execution sandbox's network policy; minor runtime overhead; modest per-target egress configuration.

**Maintenance cost — Low.** Reserved-range and metadata-endpoint definitions are stable; occasional updates as cloud providers add metadata addresses.

**Impact if postponed — Catastrophic and immediate.** SSRF-to-metadata = credential theft = platform compromise. Adds legal exposure (the product used to attack third parties) and, for a security vendor, reputational ruin. Blocks MVP outright.

---

## SEC-C2 — Multi-tenant secret / token store → **Tier B (SaaS GA)**

**Why.** Some secure storage of OAuth bot tokens, JWT signing keys, and webhook secrets is needed from the first installation (basic encrypted-at-rest is already implied by guardrail G1). But the *designed* problem the review flagged — roughly 100k per-installation secrets, per-tenant keying, rotation, revocation, HSM — only materializes as tenant count grows, i.e., at commercial SaaS. An MVP with a handful of installations has a small blast radius and does not need the full subsystem. (FIPS 140-3 / HSM specifically is a regulated overlay → D.)

**Implementation complexity — High.** Envelope encryption, a per-tenant key hierarchy, rotation/revocation, and KMS integration form a cross-cutting security subsystem, not a localized change.

**Operational cost — Medium–High.** KMS / secret-backend infrastructure, key-rotation runbooks, incident on-call for key events.

**Maintenance cost — Medium.** Rotation schedules, key-version migrations, periodic access audits.

**Impact if postponed — High but bounded before scale.** With few tenants a store compromise is contained; as tenants multiply, one store breach becomes simultaneous takeover of every customer's chat workspace — an extinction event. Not MVP-blocking; firmly GA-blocking.

---

## SEC-C5 — Supply-chain assurance → **Tier B (SaaS GA)**

**Why.** The worker executes third-party scanner images and Python dependencies with credentials and network egress, so a poisoned dependency is a direct code-execution path (SolarWinds-class). Independently, every B2B security buyer now runs a vendor questionnaire demanding SBOM, pinned/signed artifacts, and build provenance — these are table stakes to *sell* SaaS, not merely to satisfy regulators. A minimal MVP slice (lockfiles / pinned digests — `uv.lock` already exists) is cheap and near-A, but the full program is a GA gate. FedRAMP SSDF attestation and signed offline-update provenance for air-gap are D overlays.

**Implementation complexity — Medium–High.** Requires SBOM generation, signature verification, digest pinning, and dependency-confusion controls — plus a CI/CD pipeline, which does not exist in the repo today.

**Operational cost — Medium.** Signing/registry infrastructure, build-pipeline gates, periodic re-scanning.

**Maintenance cost — Medium.** Continuous dependency/image updates and re-attestation.

**Impact if postponed — Medium pre-GA, High at/after GA.** Delays or fails enterprise deals on questionnaire grounds and leaves a high-severity remote-code-execution vector open in the worker tier. Tolerable for a tightly controlled pilot; must land before broad selling.

---

## SEC-C6 — Prompt injection on the MCP tool surface → **Tier B (SaaS GA)**

**Why.** This is an AI-security product; its credibility collapses if it is itself trivially prompt-injectable. The MCP tool gateway (the one built surface) lets an AI assistant invoke scans, so indirect injection via attacker-controlled scanned content can drive state-changing tool calls (launch/cancel jobs — overlapping SEC-C1's SSRF/cost impact) or corrupt evaluation verdicts (a false "secure" posture, a G3 concern). In a trusted-pilot MVP the likelihood is lower (fewer untrusted content paths reaching a tool-holding assistant), which is why it is B rather than A — but the subset "human confirmation on state-changing MCP tools" should be pulled forward to A **if** the MVP exposes such tools.

**Implementation complexity — Medium–High.** Content provenance/quarantine, tool-call allow-listing, and human-in-the-loop gating span the MCP and evaluation surfaces; the problem space is partly research-flavored and evolving.

**Operational cost — Low–Medium.** Mostly design-time controls plus some confirmation UX; modest runtime overhead.

**Maintenance cost — Medium.** Injection techniques evolve continuously; controls need ongoing tuning and red-teaming.

**Impact if postponed — High reputational, moderate technical.** A public "we prompt-injected the AI-security tool" result would be brand-defining; technically it re-opens scan/cost abuse through the tool path. Ship the HITL slice early; the full program before GA.

---

## SEC-C3 — WORM / externally-anchored audit → **Tier D (Regulated Enterprise)**

**Why.** The transactional per-tenant hash chain already designed provides tamper-*evidence* sufficient for commercial and general-enterprise trust. External notarization, WORM immutability, segregation of duties between the audit writer and DBAs, and SEC 17a-4 / CFTC retention are specifically financial-records and government requirements. Non-regulated customers neither require nor pay for external anchoring, and the existing chain already meets their needs.

**Implementation complexity — High.** WORM storage tier, an external anchoring/notarization mechanism, and organizational segregation of duties combine an architectural, operational, and process change.

**Operational cost — High.** WORM storage, a notarization/anchoring cadence, separated-duty roles, and compliance attestations.

**Maintenance cost — High.** Retention-policy management, periodic integrity verification, and support for audits/examinations.

**Impact if postponed — None for A/B/C; absolute blocker for D.** Postponing forecloses regulated finance/government deals until built, but creates **no** security exposure for non-regulated tenants (whose assurance need the current chain satisfies). This is a market-access decision, not a live risk.

---

## SEC-C4 — Notification data-classification / cloud egress → **Tier D (Regulated Enterprise)**

**Why.** Posting findings and alerts to third-party cloud chat (Slack/Teams) is the *desired feature* for commercial and most enterprise customers — not a defect. It becomes a violation only under data-classification and residency regimes (government IL4+, some financial data), where regulated data may not transit third-party clouds. Classification-aware channel governance and "no cloud egress for regulated data" is therefore a regulated-enterprise requirement. (A small hygiene slice — never post obvious secrets to broad/public channels — has general value and overlaps notification best practice, but the finding's substance is regulatory.)

**Implementation complexity — Medium–High.** Requires a data-classification tagging model, channel classification, and a residency-aware routing policy engine.

**Operational cost — Medium.** Policy administration, channel governance, and classification-catalog upkeep.

**Maintenance cost — Medium.** Policies evolve as each tenant's compliance scope changes.

**Impact if postponed — None commercially; a breach for regulated tenants.** Commercial SaaS and general enterprise are unaffected. But onboarding a regulated tenant before this exists would create a data-classification/residency breach, so it gates regulated go-to-market rather than exposing existing customers.

---

## What this classification implies for sequencing

1. **Before any internet-exposed MVP/pilot:** SEC-C1 (the only A). Non-negotiable; cheap relative to its blast radius.
2. **Before commercial SaaS GA:** SEC-C2, SEC-C5, SEC-C6 (the three Bs) — the "can we sell this" gate: don't-lose-all-tenants, pass-the-questionnaire, don't-embarrass-the-brand.
3. **Before selling to finance/government:** SEC-C3, SEC-C4 (the two Ds) — market-access gates with no bearing on non-regulated customers.
4. **No pure-C work here:** the Enterprise-only hardening (tenant isolation, mTLS, RBAC dual-control, residency) is in the High register, sequenced alongside the Bs and Ds as those customer tiers are pursued.

Deliberately excluded, per instruction: any description of *how* to remediate. Remediation design is the next step, once these tiers are agreed.
