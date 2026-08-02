# 0012 — Runtime Boundaries: a category, not a new backend role

Status: **Proposed** — requires backend-owner ratification.
Owner: Loi Phan
Date: 2026-07-29
Relates to: [Decision 0007](0007-domain-layer-justification.md) (the evidentiary standard this ADR is held to, and the worked precedent for introducing a role), [Decision 0009](0009-execution-capability.md) (the same refusal to abstract over a set of one), [Decision 0006](0006-service-package-design-standard.md) (the dumping-ground failure this must not reproduce).
Implemented by: [standards/architecture/runtime-boundary](../standards/architecture/runtime-boundary.md) 1.0.0, [backend-layering](../standards/architecture/backend-layering.md) 1.2.0.

---

## 1. Context

Implementing the JMeter worker produced a component with no legal home.

[backend-layering](../standards/architecture/backend-layering.md) R1 fixes the set of architectural roles — `routers/`, `services/`, `integrations/`, `dao/`, `schemas/`, `helpers/`, `constants/`, `core/`, `domain/` — and its Exceptions clause makes adding one a Decision-level change. The JMeter worker agent is none of them:

- It is **not** a router: `routers/` is the MCP server's HTTP surface, and the agent's endpoints are served by a different process on a different host.
- It is **not** a service: services are the MCP server's application logic, and the agent runs in a container the server never imports.
- It is **not** an integration: `integrations/jmeter/` correctly holds the *adapters* the agent composes (`JMeterWorker`, `JMeterProcessRunner`), but the deployed process that hosts them is a different kind of thing.

The verified facts, as built:

| Property | JMeter worker | MCP server |
|---|---|---|
| Container image | `docker/jmeter/Dockerfile` | `docker/fastapi/Dockerfile` |
| Process lifecycle | own; scaled with `--scale jmeter=N` | own |
| External interface | `/assignments`, `/health/live` | `/tools/**`, `/mcp` |
| Imports the other? | **no** | **no** |
| Python files in image | 35 | 143 |

The agent was first placed at `app/jmeter_worker_main.py`, beside `main.py` and `bootstrap.py`. That is *legal* — root modules are existing precedent — but it says nothing. Nothing marks it as a separate deployable, nothing states which imports would break it, and nothing stops the next contributor from restoring `COPY app ./app` and quietly dissolving the isolation.

## 2. Options considered

**(a) Add `workers/` to R1's role set.** Rejected — see §3.

**(b) Leave it at `app/jmeter_worker_main.py` and rely on the Dockerfile plus a test.** This is the status quo. It works today and costs nothing, but the *rule* exists only as a comment in a Dockerfile and an assertion in one test file. Neither is discoverable from the AIOS, so an AI or a contributor loading the Standards would not find it. A second such process would be placed by guesswork.

**(c) Introduce a `runtime/` category that is explicitly not a backend layer, governed by its own Standard.** Chosen.

**(d) Move the worker into a separate top-level project** (`jmeter-worker/` beside `mcp-server/`) with a shared package. Rejected as premature — it requires a packaging story, two `uv` projects, two CI builds and a version-sync mechanism between them, on the evidence of one worker. Option (c) reaches the same isolation guarantee without any of that, and does not foreclose (d) later.

## 3. Why `workers/` is the wrong abstraction

Adding `workers/` to R1 fails on two counts, and the second is the more serious.

**It is factually wrong about what the thing is.** "Worker" names a *role in a job-processing pattern*. But `integrations/owasp_zap/` already contains a worker registry, a worker pool and worker scheduling — server-side code, correctly placed, that would have every right to a folder called `workers/`. The name would collide with an existing, different meaning on its first day. What distinguishes the JMeter agent from all of that is not that it is a worker; it is that it is **independently deployed**.

**It admits an unbounded category into a bounded list.** R1's value is that its list is short and closed. `workers/` has no definition that excludes anything: any code someone chooses to call a worker qualifies, which makes it precisely the "concept doesn't fit anywhere" folder R1's own Anti-patterns forbid, and the dumping ground [ADR-0006](0006-service-package-design-standard.md) was written to prevent. Within a year it would hold queue consumers, cron jobs and background threads — three things that are *not* independently deployed and that belong in `services/`.

The four-condition Scope test in [runtime-boundary](../standards/architecture/runtime-boundary.md) is the fix: own image, own lifecycle, own interface, local execution. All four, or it is application code. That is a definition something can fail.

## 4. Why this is not premature abstraction

This ADR is held to the standard [ADR-0007](0007-domain-layer-justification.md) §2.4 set and [ADR-0009](0009-execution-capability.md) applied: present verified evidence, never a roadmap. There is exactly **one** runtime boundary today, and ADR-0009 rejected an Execution capability at exactly that count. The distinction has to be argued, not assumed.

**What ADR-0009 rejected was an abstraction *over* implementations** — an interface, a strategy enum, a capability layer that generalises N cases into one shape. Its evidence was 1/0/0 implementations of three substrates, and its warning was concrete: the last speculative execution abstraction in this codebase shipped five `ExecutionStrategy` members of which three were never used.

**This ADR introduces no such thing.** There is no base class, no interface, no registry, no plugin point, and no runtime is polymorphic with another. `runtime/` is a **placement rule plus a dependency constraint**. Nothing is generalised; something is classified and then restricted. Ask the ADR-0009 question directly — *what would be wrong if there is never a second runtime boundary?* — and the answer is: nothing. The rules for the one that exists remain exactly as true and as enforceable.

**The evidence is a present, verified gap, not a predicted need.** Every fact in §1's table is checkable in the repository today. The gap is that a component which *already exists* has no home the Standards can name, and its isolation — real, and mechanically enforced by a selective `COPY` and an import-closure test — is written down nowhere an AI or a contributor would look. That is a defect in the standards, present tense.

**Implement → Observe → Extract, honestly applied.** We implemented (Phase 3), observed (the agent, its image, its import closure, and a placement attempt that turned out to violate R1), and are now extracting **the rule we actually followed** — not a shape we imagine a future worker will want. The scope is deliberately the narrowest thing that covers the observed case.

**Stated cost, so it is not hidden:** with n=1, the *shape* `runtime/<name>/main.py` is generalised from a single sample and may not fit runtime boundary #2. That is accepted, and it is cheap: the shape is a directory convention, so correcting it is a file move plus a version bump, not a refactor of anything's dependencies.

## 5. Decision

1. **`app/runtime/` is a category, not a backend layer.** [backend-layering](../standards/architecture/backend-layering.md) carves it out of scope at 1.2.0 (Minor: additive, and no rule text weakens for anything R1 still governs — mirroring how `domain/` was *added* at 1.1.0, also Minor).
2. **R1's whitelist is unchanged and stays blocking.** `workers/` is not added. Nothing is admitted to the role set.
3. **A new Standard, [runtime-boundary](../standards/architecture/runtime-boundary.md) 1.0.0**, owns the concept: a four-condition Scope test, and rules RB1–RB6 covering placement, ownership, forbidden imports, contract-only communication, the four required deliverables, and the `runtime.py` naming ban.
4. **RB3 is mechanically enforced.** `aios arch` now scans `app/runtime/**` for imports of `app.dao`, `app.services`, `app.routers` and `app.bootstrap`, alongside the Domain D2/D3 checks it already ran. Prose an AI can rationalise past becomes a gate it cannot.
5. **The JMeter agent moves** from `app/jmeter_worker_main.py` to `app/runtime/jmeter/main.py`, becoming the reference implementation.

## 6. Consequences

**Gained:**

- A component that exists has a home the Standards can name, and the next one is placed by a rule instead of by guesswork.
- The isolation that was already true becomes *stated and enforced*: RB3 is checked by `aios arch` on every run, and RB5 requires the Dockerfile's selective copy plus the closure test that stops it drifting back.
- R1 keeps its short closed list. The pressure that would have been released by adding `workers/` is instead absorbed by a definition with a failing condition.

**Accepted:**

- A third meaning of the word "runtime" enters the codebase, alongside `integrations/<tool>/runtime.py` (process singletons) and `services/tools/<tool>/execution/runtime.py` (per-operation orchestration). Mitigated by RB6, which forbids `runtime.py` inside `app/runtime/`, and by each site documenting which meaning it carries — but the word is now overloaded three ways and that is a real readability cost, recorded rather than argued away.
- One more Standard for a contributor to load. Bounded: it is reached only from `backend-layering`'s Scope, so a task that never touches `app/runtime/` never pays for it.
- `aios arch` grows a second scan. Small, and it reuses the existing mechanism.

**Revisit trigger:** the **second** runtime boundary. At that point re-examine whether `runtime/<name>/main.py` is the right shape, whether RB3's forbidden list is right, and — only if the two boundaries turn out to share real code rather than only contracts — whether option (d), a separate project, has earned its cost. Do not pre-empt any of that now.

## 7. Governance note

Not an RFC-tier change: it adds a unit within an existing module (`standards/`) and applies a Minor bump to one unit. Per [governance](../governance/README.md#impact-analysis), a Minor bump flags consumers Informational only — `domain-layer`, `persistence-dao` and `service-package-design` depend on `backend-layering` and are unaffected, since none of R1–R4 changed.

**Not authorized by this ADR:** admitting any role to R1's list, relaxing any R1–R4 rule, creating a second runtime boundary, or moving any code the MCP server imports into `app/runtime/`.
