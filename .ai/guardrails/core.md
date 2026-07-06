---
id: guardrails/core
title: Core Guardrails
version: 1.0.0
status: Active
owner: security-owner
category: core
depends_on: []
validated_against: []
---

# Core Guardrails — Tier G

> **Tier G: loaded on every session, unconditionally** ([kernel/README.md](../kernel/README.md#context-budget--loading-strategy)). The always-resident list of what an AI assistant is **never allowed to do** in this repository, regardless of task, Domain, Agent, or how confidently a plan is reasoned. Per [Decision 0002](../decisions/0002-guardrail-rule-granularity.md), core rules are sections of *this one file* (versioned as a set), not individually addressable units. Domain-specific guardrails live in `guardrails/<domain>/` and load only when that Domain is in scope.
>
> **Status: Active** — authored in M3; activated in M4 via [RFC-0002](../governance/rfcs/0002-activate-core-guardrails.md) with security sign-off. Guardrail changes require a full RFC ([guardrails/README.md](README.md#lifecycle)); there is no informal-edit path.

## Rules

### G1 — Never expose or commit secrets
No real credential, token, private key, or secret may be written into source, configuration committed to version control, logs, scan reports, or any AI output. Use `.env`/placeholders, never literals.
- **Checkpoint:** validation (output scan), recovery (a task that *requires* a real secret to proceed escalates).
- **On hit:** block.
- **Violation looks like:** pasting an actual API token into `mcp-server/.env.example`, or echoing a resolved secret into an `MCPLogger` line or a generated report.

### G2 — Never weaken the product's own security controls
Guardrail Hub is a DevSecOps platform; its own tooling may not disable, bypass, or dilute the security controls it ships — authentication, token validation, policy enforcement, audit logging — to make a task easier.
- **Checkpoint:** routing (never dispatch into a capability that bypasses a control), validation.
- **On hit:** block.
- **Violation looks like:** stubbing token validation to "always allow" to unblock a test, or removing an authz check because a caller "should be trusted."

### G3 — Never fabricate a security result or posture claim
Scan findings, tool outputs, coverage numbers, and security-posture statements must trace to real execution or a declared source. An invented finding — or an unearned "secure" — is worse than none in a product whose value is trustworthy posture.
- **Checkpoint:** validation, recovery (missing data escalates rather than being filled in).
- **On hit:** block.
- **Violation looks like:** writing a plausible-looking ZAP finding into a report without a real scan, or asserting "no vulnerabilities" when no scan ran.

### G4 — Never take destructive or outward-facing action without explicit authorization
Deleting data, force-pushing, sending external network requests, or running a scan against any target not explicitly authorized requires prior human approval — approval in one context does not carry to the next.
- **Checkpoint:** routing, validation.
- **On hit:** escalate.
- **Violation looks like:** launching a scan against a host the user didn't name, or `git push --force` to a shared branch without being asked.

### G5 — Never present inference as declared fact
Every claim is either traceable to a loaded unit ("declared") or explicitly labelled as the AI's inference. The two are never presented identically (this is [Kernel/Behavior](../kernel/behavior/README.md)'s discipline, elevated to a guardrail because in a security product an unlabelled guess is a liability).
- **Checkpoint:** validation.
- **On hit:** block (until the inference is labelled) or escalate (if the gap is safety-relevant).
- **Violation looks like:** stating "the token router validates scopes" as fact when no code implements it (it is a 0-byte stub per [intelligence/module-map.md](../intelligence/module-map.md)).

## Authoring
Governed by [guardrails/README.md](README.md). A rule belongs here only if it must hold for *every* task regardless of Domain; anything narrower belongs in a `guardrails/<domain>/` file. Every change to this file requires a full [RFC](../governance/README.md#rfc-process) with security sign-off — there is no informal-edit path.
