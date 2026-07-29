# Security Map

## Purpose
Document Guardrail Hub's own security posture — authentication, authorization, secret management, and scanner coverage — as it actually exists, since this is a security product and the gap between claimed and actual posture matters more here than in most repos.

## Scope
Security-relevant implementation in `mcp-server/` and `web/`. Does not cover the security *product features* Guardrail Hub intends to offer (those are documented as scanner integrations below) versus the security *of Guardrail Hub itself* — both are covered, kept clearly separated.

## AI Usage Guidance
Read this before implementing anything auth-related — the config and schemas suggest more security exists than actually does. Do not build features on top of `internal_token_secret`/JWT settings assuming a working auth dependency exists; it doesn't yet. Flag any task that would ship a new endpoint without addressing this gap.

## Main Content

### Authentication — Guardrail Hub's Own

**Not implemented**, despite scaffolding:

| Scaffolding present | Missing |
|---|---|
| `AuthMixin` settings (`app/core/config/_auth.py`): `token_authority` (`SELF_MANAGED`/`PLATFORM_ISSUED`), `token_algorithm`, `internal_token_secret` (validated ≥32 chars), `token_issuer`, `token_audience`, `token_expires_in_days` | No code reads or validates a token on any request |
| `pyjwt` declared as a dependency | Zero call sites for `jwt.encode`/`jwt.decode` anywhere in `app/` |
| `TokenVerifyRequest`/`TokenVerifyResponse` schemas (`app/schemas/internal/token_request.py`) | `app/routers/internal/token_router.py` is a 0-byte file — no handler implements these schemas |
| `mcp-server/dependencies/` directory reserved for FastAPI `Depends()`-based auth | Directory is empty |

**Every endpoint currently listed in [api-map.md](api-map.md) is open, unauthenticated.**

### Authorization

Not implemented. No role/permission model, no policy-check code found. `app/policies/` exists as a directory but contains zero files. The root README's "Policy Enforcement" concept for the MCP tool gateway is aspirational.

### Secret Management

| Mechanism | Status |
|---|---|
| `.env` files | Implemented — `mcp-server/.env.example` (template, committed) and `mcp-server/.env` (real values, correctly git-ignored per `mcp-server/.gitignore`) |
| Vault / AWS Secrets Manager / similar | Not used |
| `blocked_file_patterns` (`SecurityMixin`, `app/core/config/_security.py`) | Config default blocks `.env`, `*.pem`, `*.key`, `id_rsa`, `id_ed25519` from tool access — this is a config value, not confirmed to be enforced by any code path (no reference found outside the setting definition itself) |
| `enable_secret_guard` flag (`SecurityMixin`) | Defined, defaults `True` — no corresponding implementation found; `app/security/` is an empty directory |
| `AUDIT_MASK_SECRETS` env var | Defined in `.env.example` — no audit implementation exists to apply it (`mcp-server/audit/` is empty) |

**Conclusion: secret-handling intent is well captured in config, but enforcement code does not yet exist.**

### CORS

`CORSMiddleware` is wired in `app/main.py`, driven by `CORS_ALLOW_ORIGINS` (`.env.example` default `*`) — wide open by default in the example configuration. Verify the real `.env` value before assuming any origin restriction is in effect.

### Security Scanner Coverage (the product feature, applied to itself)

| Scanner | README claims it | Implemented | Used against Guardrail Hub's own code? |
|---|---|---|---|
| OWASP ZAP (DAST) | Yes | **Yes** — full path: schema → router → service → integration client → Docker → real reports | Evidence of local runs exists (`mcp-server/public/report/`, `mcp-server/logs/`), but no CI-integrated scan of Guardrail Hub itself |
| Semgrep (SAST) | Yes | No | No |
| Gitleaks (secrets) | Yes | No | No |
| Trivy (containers) | Yes | No | No |
| Checkov (IaC) | Yes | No | No |
| MobSF (mobile) | Yes | No | No (no mobile app exists yet either) |
| OSV-Scanner / Dependency-Check | Yes | No | No |
| Schemathesis (API) | Yes | No | No |
| Playwright / Selenium (E2E) | Yes | Router stubs only (`app/routers/mcp/playwrights_router.py`, `selenium_router.py`), not wired into `endpoints.py`, no service/integration code | No |
| JMeter | Not in MVP table, appears elsewhere | **Executes real load** as of Phase 3. MCP-exposed (`run_jmeter`, `analyze_jmeter_result`) with no auth, like every other tool here — and unlike a scan, a completed run generates real traffic volume at the target, so an authorization mistake here is a denial of service. **G4, two enforcement points:** `JMeterTestRequest` rejects any non-absolute or non-http(s) target at the boundary; `JMeterPlanValidator` then rejects any plan whose samplers address a host other than that target, before a worker is engaged. **Caller-supplied `.jmx` plans are OFF by default** (`jmeter_allow_supplied_plan`): a plan is executable content that can carry JSR223/BeanShell scripts and OS process samplers which run on the worker. The validator rejects those element types, but that is a denylist over a large format — a weaker guarantee than generating the plan ourselves, which is why the path is opt-in and should be security-reviewed before any operator enables it. See [architecture/jmeter-engine/](../../architecture/jmeter-engine/README.md), ADR-0010/0011 | No |

### Security Workflows

None. No CI-gated security scanning, no `.github/workflows/` at all (see [deployment-map.md](deployment-map.md)). There is no automated process today that scans Guardrail Hub's own codebase for the vulnerability classes the product itself is built to detect elsewhere.

## Related Documents
[api-map.md](api-map.md) · [deployment-map.md](deployment-map.md) · [system-overview.md](system-overview.md) · [`.ai/guardrails/README.md`](../guardrails/README.md)

## Last Updated
2026-07-03 — verified against commit `10bd79b`.
