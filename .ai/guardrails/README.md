# Guardrails
## Cross-Cutting Policy Layer

Status: **Active.** The Tier G rule set is [`core.md`](core.md), activated through [RFC-0002](../governance/rfcs/0002-activate-core-guardrails.md). Domain-scoped guardrail categories are added only when needed.

## Purpose
The authoritative source of safety and security policy — what the AI is never allowed to do, regardless of task, Agent, or how confidently a plan is reasoned. Distinct from [Standards](../standards/README.md) (mandatory *quality/consistency* rules) and from [Kernel/Guardrails](../kernel/guardrails/README.md) (the Kernel's *checkpoints* that consult this layer).

## Structure: Core vs. Domain

Mirrors [Standards](../standards/README.md#categories--hierarchy)'s core/category split, for the same reason: a single flat guardrail set would eventually violate the "Tier G stays small" invariant ([kernel/README.md](../kernel/README.md#context-budget--loading-strategy)).

```
guardrails/
├── core.md         # Tier G — loaded every session, unconditionally. Bounded (~50 lines even at scale):
│                     universal "never do X" rules that apply regardless of task or Domain.
└── <domain>/        # Tier 1/2 — loaded like Standards, only when the matched Domain needs it
                      # (e.g., guardrails/security/, guardrails/infrastructure/)
```

Only `core.md` is unconditional. A rule belongs in `core.md` only if it must hold for *every* task regardless of Domain — anything narrower belongs in a `<domain>/` file, keeping the always-loaded surface bounded no matter how many domain-specific guardrails accumulate.

> **Frontmatter (machine half):** every guardrail unit carries frontmatter validated against [schema/guardrail.schema.json](../schema/guardrail.schema.json) (base + Guardrail extension — note it omits the `Stale` status and adds `checkpoint`/`enforcement`). See [schema/README.md](../schema/README.md).

## Responsibility
Author and version policy rules; answer allow/deny/escalate queries from [Kernel/Guardrails](../kernel/guardrails/README.md) at each of its four checkpoints (Boot activation, Routing dispatch, Validation security check, Recovery safety-relevance determination).

## Inputs
Governance decisions, human-set security posture requirements (this is a DevSecOps platform — its own tooling cannot have a weaker policy layer than the product it ships).

## Outputs
Allow/deny/escalate decisions.

## Dependencies
None — foundational, alongside Standards.

## Consumers
[Kernel/Guardrails](../kernel/guardrails/README.md) exclusively. No other module queries Policy directly; everything routes through the Kernel's checkpoints so policy enforcement can't be bypassed by a module that forgets to check.

## Owner
Architecture/governance owners, with security sign-off.

## Acceptance Criteria

Per [RFC-0001](../governance/rfcs/0001-acceptance-criteria.md), a guardrail unit that has passed Review must additionally meet these readiness checks before reaching `Active`:

- **A1** A **security sign-off** by a human with security authority is recorded (a guardrail is a security control; readiness includes human security attestation).
- **A2** Each rule states its checkpoint(s), `block`-vs-`escalate`, and a concrete violation example.
- **A3** The change merged through a full [RFC](../governance/README.md#rfc-process) (guardrails have no informal-edit path).
- **A4** `aios validate` passes (correctness precondition).

## Lifecycle
Near-immutable, like the Kernel itself — changes here have the same blast radius as a Kernel change and go through the same governance review. Per [Decision 0001](../decisions/0001-aios-bootstrap-roadmap.md) and [governance/README.md](../governance/README.md#rfc-process), **every** change to `core.md` or a `<domain>/` guardrail file — including what would elsewhere count as Patch — requires a full RFC; there is no informal-edit path. Guardrails also has no `Stale` state: a guardrail is changed only through an explicit, reviewed RFC.
