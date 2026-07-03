# Router
## Phase 10: Context Router

> The heart of the AIOS. Every other module (Agents, Knowledge, Skills, Standards, Workflows, Templates) is inert without the Router deciding what gets loaded and what doesn't. This phase makes the [Phase 1 contract](../foundation/architecture.md#router) concrete.

Status: Approved

---

## What the Router Decides

For a given task, the Router produces exactly one thing: an ordered list of addresses (category → unit, per module) that [Kernel/Loading](../kernel/loading/README.md) will fetch. It never fetches content itself, and it never decides *what to do* with the content — that's the dispatched [Agent](../agents/README.md)'s job.

## Routing Algorithm

```mermaid
flowchart TD
    Task[Task, scoped by Kernel/Behavior] --> Cap[Capability Detection]
    Cap --> AgentSel[Select primary Agent<br/>via Kernel/Routing]
    AgentSel --> Disc[Knowledge Discovery:<br/>walk Agent's declared<br/>Knowledge Sources / Skills / Standards / Workflows / Templates]
    Disc --> Order[Order addresses:<br/>required before related,<br/>dependencies inline]
    Order --> Cache{In routing cache<br/>for this task shape?}
    Cache -- Yes --> Return[Return cached address list]
    Cache -- No --> Build[Build address list from category indexes]
    Build --> Store[Store in cache keyed by task shape]
    Store --> Return
```

- **Capability detection** reuses [Kernel/Routing](../kernel/routing/README.md)'s dispatch decision — the Router doesn't redetect capability, it consumes the Agent selection already made.
- **Knowledge discovery** walks the selected Agent's contract (its declared Knowledge Sources, Skills Used, Standards Enforced, Workflows Used, Templates Used from the [Agent Contract](../agents/README.md#the-agent-contract)) and resolves each against that module's category index — never a full-module scan.
- **Dependency loading** — if a resolved unit's own contract declares a dependency (a Skill's Prerequisite, a Knowledge unit's Dependencies field), that dependency is inserted into the address list immediately after it, not appended at the end.
- **Priority loading** — addresses the Agent's contract marks as directly required for the detected task type sort before addresses that are merely related (e.g., Related Standards on a Knowledge unit are related, not required, unless the task is specifically about compliance).
- **Context budget** — the address list is capped at the ceiling [Kernel/Loading](../kernel/loading/README.md) enforces; if discovery produces more candidates than the budget allows, the Router keeps required-priority addresses and drops related-priority ones, never the reverse.
- **Lazy loading** — the Router resolves addresses; it does not pre-fetch them. Fetching happens only when Kernel/Loading actually calls for the next address in the sequence.

---

## Worked Routing Examples

**Implement API**

```mermaid
flowchart LR
    T1[Task: Implement API] --> A1[Backend Agent]
    A1 --> K1[Knowledge: FastAPI conventions]
    A1 --> S1[Skill: Python]
    A1 --> W1[Workflow: API Development]
    A1 --> Tp1[Template: Backend Service]
```

**Deploy Kubernetes**

```mermaid
flowchart LR
    T2[Task: Deploy Kubernetes] --> A2[Infrastructure Agent]
    A2 --> K2[Knowledge: Docker]
    A2 --> K3[Knowledge: Kubernetes]
    A2 --> W2[Workflow: Deployment]
    A2 --> Tp2[Template: Deployment/Kubernetes Resources]
```

In both cases the address list is short (4–5 entries) regardless of how large `knowledge/`, `skills/`, `templates/` grow overall — that's the scalability property this phase exists to guarantee.

---

## Routing Cache

Keyed by **task shape** (capability + the specific Knowledge/Skill/Standard/Workflow/Template categories the Agent's contract names), not by the literal task text — two differently-worded "implement an API endpoint" requests resolve to the same cache entry. The cache stores the *address list*, never the fetched content, so a cache hit still respects lazy loading downstream. Cache entries invalidate when the underlying Agent contract or a referenced module's index changes (a new/removed unit in a walked category).

## Fallback Strategy

```mermaid
flowchart TD
    Resolve[Resolve address] --> Found{Unit exists<br/>at that address?}
    Found -- Yes --> Use[Use it]
    Found -- No --> Related{Related unit exists<br/>in same category?}
    Related -- Yes --> Substitute[Use related unit,<br/>flagged as substitution]
    Related -- No --> Missing[Missing-knowledge path<br/>→ Kernel/Recovery]
```

## Missing Knowledge Strategy

A missing address is not silently skipped — it's handed to [Kernel/Recovery](../kernel/recovery/README.md) with the specific address that failed to resolve, so Recovery's existing missing-knowledge decision (safety-relevant → escalate; otherwise → infer-and-label) applies uniformly. The Router's only job here is to report *what* is missing precisely, not to decide what happens next.

## Unknown Request Handling

If Kernel/Routing cannot detect a capability at all (the task doesn't map to any registered Agent), the Router has nothing to resolve against and returns an empty address list with a reason code (`no-capability-match`). This is itself a Recovery case — treated as safety-relevant by default, since dispatching to a best-guess Agent for an undetected capability is exactly the "ungrounded action" failure mode Phase 0 exists to prevent.

---

## Sequence: Full Resolution Path

```mermaid
sequenceDiagram
    participant KR as Kernel/Routing
    participant R as Router
    participant Idx as Module Category Indexes
    participant KL as Kernel/Loading

    KR->>R: capability = Backend, task = "implement API"
    R->>R: check routing cache for this task shape
    alt cache miss
        R->>Idx: walk Backend Agent's declared sources
        Idx-->>R: candidate addresses per category
        R->>R: order by priority, insert dependencies, apply budget
        R->>R: store in cache
    end
    R-->>KL: ordered address list
    KL->>KL: fetch one address at a time (lazy)
```

---

## Consumers & Dependencies

Consumes: [Kernel/Routing](../kernel/routing/README.md)'s capability decision, and every module's category index (Knowledge, Skills, Standards, Workflows, Templates — see each module's Index section). Produces for: [Kernel/Loading](../kernel/loading/README.md).

## Lifecycle

The Router itself is Kernel-adjacent (near-immutable, per [Architecture](../foundation/architecture.md)); its cache and indexes are live and update continuously as modules gain units — no governance review needed for cache/index churn, only for changes to the resolution algorithm above.
