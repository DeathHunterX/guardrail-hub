# Security Map

## Purpose

State the product's security posture candidly: implemented controls, trust assumptions and material gaps.

## Scope

Inbound APIs, outbound credentials, scanner execution, persistence, logging and repository checks.

## AI Usage Guidance

Treat missing controls as risks, not implied features. Security-sensitive changes must confirm enforcement in executable code, not only settings or documentation.

## Main Content

### Current controls

- Typed configuration validates several production secrets and unsafe defaults.
- LLM credentials are abstracted behind a credential store with Windows Credential Manager, mounted-file and environment backends.
- Non-Windows credential selection fails closed unless a backend is explicitly chosen.
- Provider secrets are resolved at runtime rather than stored in `config/llm.yaml`.
- Domain and isolated-runtime import boundaries are mechanically checked by AIOS tooling.
- ZAP/JMeter work is queued and assigned through worker services instead of arbitrary direct execution from MCP payloads.
- Conversation redaction exists as an explicit operation.

### Critical gaps

| Area | Current reality | Consequence |
|---|---|---|
| Authentication | No inbound auth middleware/dependency on main HTTP or MCP routes | Any network-reachable caller can invoke exposed operations |
| Authorization/policy | Settings and concepts exist, but no request-time enforcement pipeline | No tenant, role or tool-level access control |
| Rate limiting | Not enforced | Expensive scanner/LLM operations can be abused or exhausted |
| Audit | Conversation events are in-process; no durable audit subscriber or tamper-evident log found | Security investigations lack authoritative audit evidence |
| Secret backend | Environment backend is supported | Convenient but weaker than mounted/OS-managed secrets; environment leakage remains possible |
| Worker trust | Worker registration is network/API based without demonstrated mutual authentication | A reachable attacker may impersonate or manipulate workers |
| Generated reports | Served from `/public` without access control | Findings may be exposed if the server is reachable |

### Execution risks

ZAP and JMeter accept targets/workloads that can cause outbound network activity and resource consumption. Before Internet exposure, add authenticated principals, authorization, target allow/deny policy, SSRF protections, request/body limits, concurrency/quotas, artifact access control and durable audit trails. Apply network egress restrictions as defense in depth.

LLM provider calls may send conversation or scan-derived data to external systems. Data classification, provider allowlists, retention/redaction policy and tenant isolation are not currently enforced end to end.

### Supply chain and CI

The AIOS workflow checks repository governance artifacts, not dependency vulnerabilities, secret scanning, SAST, container scanning or signed releases. Those product-security pipeline controls remain absent.

## Related Documents

[api-map.md](api-map.md) · [deployment-map.md](deployment-map.md) · [database-map.md](database-map.md)

## Last Updated

2026-08-28 — security controls traced to executable enforcement points.
