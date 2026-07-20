# GuardRail Hub

GuardRail Hub is a developer-focused **security testing and QA orchestration platform** that connects multiple security and testing tools into one controlled workflow. It targets security, system-behavior, and release-readiness validation across web applications, APIs, mobile apps, containers, dependencies, secrets, infrastructure as code, and E2E flows, exposed to both direct API clients and AI assistants via MCP. GuardRail Hub is designed as a multi-tool orchestration platform, not a wrapper around a single scanner.

> ⚠️ **Alpha Release**
>
> GuardRail Hub is currently under active development.
>
> The core MCP runtime, worker orchestration, Slack notifications, and OWASP ZAP integration are available.
> Additional integrations (Apache JMeter, LLM providers, Semgrep, Trivy, Checkov, etc.) are planned.
>
> APIs and project structure may evolve before v1.0.

---

## Current Status

### Implemented

* MCP Server (FastAPI, tools exposed via the Model Context Protocol)
* Worker orchestration (self-registering ZAP worker pool with heartbeat and drain/remove management)
* Queue-based execution (background dispatcher assigns queued operations to idle workers)
* Slack notifications (scan lifecycle and progress posted and updated in place)
* 3 working OWASP ZAP tools: `scan_api`, `scan_api_scenario`, `scan_api_suite`

### In Progress

* Apache JMeter
* LLM provider integrations
* Additional security tools (Semgrep, Trivy, Checkov, Gitleaks, MobSF, OSV-Scanner/Dependency-Check, Schemathesis, Playwright)
* Full browser-based ZAP web/interactive scanning (`scan_website_application`, `scan_interactive_web_session` endpoints exist but are stubbed — "in development")
* Web dashboard and mobile app (see [Roadmap](#roadmap))

The architecture is considered stable; the project is in Alpha because tool and feature coverage is still limited.

---

## Project Vision

GuardRail Hub provides a unified way to run, control, and report security/testing tools across different environments.

The core idea is:

> A security testing MCP/platform that orchestrates multiple security and QA tools across web, API, mobile, container, dependency, secret, IaC, and E2E testing.

Instead of asking developers to manually run many tools separately, GuardRail Hub is designed to provide:

* Tool orchestration
* Runner/worker management
* Token-based access control
* Policy enforcement
* Queue-based execution
* Audit logging
* Unified, normalized reports
* Public and self-hosted execution modes
* MCP integration for AI/client-driven tool interaction

Some of these (queue-based execution, worker management, MCP integration) are implemented today; others (token-based access control, policy enforcement, audit logging) are design targets — see [Current Status](#current-status).

---

## Key Features

* **MCP-native.** Tools are exposed via the Model Context Protocol, alongside a plain HTTP API, so both AI assistants/MCP clients and regular API clients can invoke scans.
* **Asynchronous, queue-based execution.** Scans run as background operations tracked by an `operation_id`, not inline in the request path.
* **Self-registering worker pool.** Worker containers register and heartbeat automatically; scale horizontally with `docker compose --profile zap up --scale zap=N`, no server-side reconfiguration needed.
* **Live Slack notifications.** Scan lifecycle and progress events are posted to Slack and updated in place as a scan runs.
* **Pluggable persistence.** PostgreSQL and DynamoDB behind a common DAO interface, selected via `DATABASE_PROVIDER`.
* **Extensible tool architecture.** A typed operation registry with handler/execution-strategy abstractions lets new tools plug into the same dispatcher and reporting pipeline without server rework — the foundation the roadmap's additional integrations build on.
* **Multi-format reporting.** Normalized findings are exported as Markdown, JSON, and SARIF 2.1.0.

---

## Current Supported Tools

The MCP server currently exposes OWASP ZAP as three working, queue-backed MCP tools:

| Tool | Category | Status | Description |
| --- | --- | --- | --- |
| `scan_api` | API DAST | ✅ Implemented | Security-scan a single API endpoint (quick or full mode), with bearer/JWT or cookie authentication. |
| `scan_api_scenario` | API DAST | ✅ Implemented | Replay an authenticated, ordered API workflow (e.g. login → get profile → create order), propagating variables/cookies/tokens between steps. |
| `scan_api_suite` | API DAST | ✅ Implemented | Scan a whole application composed of multiple API services: expands each service's OpenAPI spec into child `scan_api` scans, fans them out across the worker pool, and aggregates one application report. |
| `scan_website_application` | Web DAST | 🚧 Stubbed, not implemented | Endpoint exists; browser-automation architecture is still under evaluation. |
| `scan_interactive_web_session` | Web DAST | 🚧 Stubbed, not implemented | Endpoint exists; not yet implemented. |

All three implemented tools run asynchronously via the queue dispatcher, execute on the horizontally scalable ZAP worker pool, and produce Markdown, JSON, and SARIF reports.

Everything else described below — SAST, dependency scanning, secret scanning, container scanning, IaC scanning, mobile scanning, and E2E testing — is planned tooling, not yet implemented. See [Roadmap](#roadmap).

---

## Architecture Overview

The diagram below shows GuardRail Hub's target platform architecture. Today, the **MCP Server** and the **ZAP path inside the Runner** are implemented; the Web Platform and Mobile App are design targets tracked in [Roadmap](#roadmap) Phase 3.

```txt
GuardRail Hub
│
├── Web Platform
│   ├── Dashboard
│   ├── Project Management
│   ├── Token Management
│   ├── Runner Management
│   ├── Tool Registry
│   ├── Scan Runs
│   ├── Findings
│   └── Reports
│
├── Mobile App
│   ├── Scan Status
│   ├── Alerts
│   ├── Approval Flow
│   └── Report Viewer
│
├── MCP Server
│   ├── Tool Gateway
│   ├── Token Validation
│   ├── Policy Enforcement
│   ├── MCP Tool Exposure
│   ├── Audit Logging
│   └── Runner/Platform Integration
│
└── Runner
    ├── OWASP ZAP
    ├── Schemathesis
    ├── Semgrep
    ├── OSV-Scanner / Dependency-Check
    ├── Gitleaks
    ├── Trivy
    ├── Checkov
    ├── MobSF
    ├── Playwright
    └── Report Normalizer
```

### MCP Server

The MCP server is a standalone FastAPI service. It can be deployed separately and given to customers as a source folder, a Docker image, a docker-compose setup, or a copy-paste install command. It is designed to not depend directly on the web platform source code, communicating with it only through API calls when running in connected mode.

Two deployment modes and two token-authority models are part of the target design:

```txt
Modes:          STANDALONE, CONNECTED
Token Authority: SELF_MANAGED, PLATFORM_ISSUED
```

Token validation and policy enforcement (referenced above) are configuration/schema scaffolding today, not enforced — see [Current Status](#current-status).

### Runner / Worker

Execution of tools is designed to happen through jobs, not inline in web/mobile requests. Today this is realized as the self-registering **ZAP worker pool**: worker containers register and heartbeat, and are responsible for picking up queued operations, running the scan, parsing tool output, normalizing findings, and generating reports. Future tools are expected to plug into the same worker/dispatch model.

---

## Repository Structure

```txt
guardrail-hub/
│
├── mcp-server/                  # Implemented — FastAPI MCP server + ZAP worker
│   ├── app/
│   │   ├── core/                # Config, logging, exceptions
│   │   ├── routers/
│   │   │   ├── mcp/              # MCP-exposed tool routers (owasp_zap_router.py)
│   │   │   └── public/           # health, history, worker registration/heartbeat
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── tools/             # per-tool services (owasp_zap/*)
│   │   │   ├── operations/        # operation orchestration, dispatcher
│   │   │   ├── notification/      # event bus, Slack rendering/dispatch
│   │   │   ├── platform/          # lifecycle reporting
│   │   │   └── evaluations/
│   │   ├── integrations/
│   │   │   ├── owasp_zap/        # ZAP client, worker registry
│   │   │   └── chat/slack/       # Slack channel adapter
│   │   ├── dao/                  # Postgres / DynamoDB DAOs
│   │   ├── domain/, helpers/, constants/
│   │   └── main.py
│   │
│   ├── dependencies/
│   ├── config/
│   ├── docs/
│   ├── tests/
│   ├── changelog/
│   ├── docker-compose.yml
│   ├── pyproject.toml
│   ├── CHANGELOG.md
│   └── README.md
│
├── web/                          # Scaffold — marketing site (Next.js), no dashboard yet
├── mobile/                       # Empty scaffold (android/, apple/)
├── api/                          # Empty, reserved
├── docs/                         # Project documentation site
├── architecture/                 # Design docs (chatops, zap-worker-pool, ...)
├── AGENTS.md
├── README.md
└── LICENSE
```

`web/` and `mobile/` are scaffolds today (a marketing page and an empty app shell, respectively) — see [Current Status](#current-status).

---

## Quick Start

The fastest way to run the implemented part of the stack (MCP server + a ZAP worker):

```bash
git clone <repository-url> guardrail-hub
cd guardrail-hub/mcp-server
cp .env.example .env
docker network create guardrail-shared   # first time only
docker compose --profile zap up -d --build
```

Check health:

```bash
curl http://localhost:8787/health
```

Default URL: `http://localhost:8787`

---

## Setup

### Requirements

Recommended:

* Node.js 20+
* Python 3.12+
* Docker
* Docker Compose
* pnpm
* uv

```bash
npm install -g pnpm
pip install uv
```

### Root Project

```bash
git clone <repository-url> guardrail
cd guardrail
```

### MCP Server

Local (without Docker) — no ZAP worker, useful for API-only development:

```bash
cd mcp-server
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload --port 8787
```

Default URL: `http://localhost:8787`

With Docker (MCP server + a ZAP worker):

```bash
cd mcp-server
cp .env.example .env
docker network create guardrail-shared   # first time only
docker compose --profile zap up -d --build --scale zap=2
```

Health check:

```bash
curl http://localhost:8787/health
```

Key `.env` settings (see `docs/configuration.md` for the full reference):

```env
MCP_MODE=STANDALONE            # STANDALONE | CONNECTED
TOKEN_AUTHORITY=SELF_MANAGED   # SELF_MANAGED | PLATFORM_ISSUED
DATABASE_PROVIDER=NONE         # NONE | POSTGRES | DYNAMODB

ZAP_API_KEY=change-this-zap-key
ZAP_SCAN_TIMEOUT_SECONDS=600

SLACK_ENABLED=false
SLACK_BOT_TOKEN=
SLACK_DEFAULT_CHANNEL=
```

### Web Platform

```bash
cd web
pnpm install
pnpm dev
```

Default URL: `http://localhost:3000`

`web/` is currently a marketing/landing page, not a product dashboard — see [Current Status](#current-status).

---

## Development Flow

1. Start the MCP server (and its ZAP worker container(s) via docker-compose).
2. Submit a scan through one of the three implemented ZAP tools (`scan_api`, `scan_api_scenario`, `scan_api_suite`), directly over HTTP or via an MCP client.
3. Poll `GET /tools/history/get-result` for the operation, or watch progress via Slack if notifications are configured.
4. Review the normalized Markdown/JSON/SARIF report.

```txt
Client submits scan request (HTTP or MCP)
        ↓
Router validates the request, enqueues a QUEUED operation
        ↓
Background dispatcher matches the operation to an idle worker
        ↓
Worker executes the ZAP scan
        ↓
Results are normalized into the finding model
        ↓
SARIF / JSON / Markdown reports are generated
        ↓
Slack is notified of progress and completion (if configured)
```

---

## Tool Registry

New tools are designed to plug into a shared operation registry rather than being hard-wired into the dispatcher — this is how the three ZAP tools already coexist behind one dispatch path, and how future tools (JMeter, Semgrep, Trivy, Checkov, etc.) are intended to be added.

The target per-tool metadata model looks like this:

```json
{
  "name": "owasp_zap_baseline",
  "displayName": "OWASP ZAP Baseline Scan",
  "category": "DAST",
  "riskLevel": "HIGH",
  "resourceCost": "HIGH",
  "executionMode": "ASYNC_QUEUE",
  "allowedRunners": ["SELF_HOSTED", "HOSTED_PAID"],
  "requiresApproval": true,
  "requiresDomainVerification": true,
  "defaultTimeoutSeconds": 900,
  "maxConcurrencyPerRunner": 1
}
```

Target tool categories:

```txt
DAST
API_SCAN
SAST
SCA
SECRET_SCAN
CONTAINER_SCAN
IAC_SCAN
MOBILE_SCAN
E2E_SECURITY_TEST
RUNTIME_MONITORING
```

Fields such as `requiresApproval` and `requiresDomainVerification` describe the target policy model; policy enforcement is not yet wired up (see [Current Status](#current-status)).

---

## Report Normalization

Each tool has its own output format. GuardRail Hub normalizes results into a common finding model so reports can be used in a web dashboard, pull/merge requests, CI/CD artifacts, security review documents, and audit history.

Example finding:

```json
{
  "id": "finding_123",
  "sourceTool": "owasp_zap",
  "severity": "HIGH",
  "category": "Security Misconfiguration",
  "title": "Missing Content Security Policy Header",
  "description": "The target does not define a Content-Security-Policy header.",
  "evidence": {
    "url": "https://example.com",
    "method": "GET"
  },
  "recommendation": "Configure a Content-Security-Policy header to reduce the risk of XSS attacks.",
  "status": "OPEN"
}
```

Supported report outputs today: **SARIF 2.1.0, JSON, and Markdown** (produced by the OWASP ZAP tools' aggregation and reporting pipeline).

---

## Production Scanning Strategy

Not all security tools are safe to run directly against production systems, especially when many users can trigger scans at once. This section describes GuardRail Hub's intended scanning-safety model; most of it is guidance the platform is designed around rather than policy the server currently enforces.

| Mode | Safe Tools |
| --- | --- |
| Production passive scan | Header scan, TLS scan, passive ZAP, availability-safe checks |
| Staging active scan | ZAP active scan, Burp, fuzzing, auth bypass tests |
| CI/CD scan | SAST, SCA, secret scan, IaC scan, container scan |
| Runtime monitoring | Falco, WAF logs, SIEM, CSP reports, error monitoring |

### 1. Production Passive Scan

Designed to be safe for live systems — no aggressive payloads, fuzzing, destructive behavior, or high request volume. Recommended checks: security headers, TLS configuration, HTTPS redirect, cookie flags, basic CORS checks, passive ZAP scan, availability-safe checks, basic exposure checks, public metadata checks. Should be low impact, rate-limited, queue-controlled, and suitable for scheduled monitoring of public-facing systems.

### 2. Staging Active Scan

Deeper, more aggressive testing intended for a staging/test environment: ZAP active scan, Burp Suite, API fuzzing, auth bypass tests, business logic tests, broken access control tests, injection payload tests, file upload abuse tests. Should require explicit target approval, correct environment selection, strong rate limits, timeout limits, and clear audit logs.

### 3. CI/CD Scan

Designed to run before code reaches production: Semgrep (SAST), OSV-Scanner/Dependency-Check (SCA), Gitleaks (secrets), Checkov (IaC), Trivy (containers), Playwright (E2E security tests). Useful for catching issues before deployment and can block merge or deployment when critical issues are found. None of these tools are implemented yet — see [Roadmap](#roadmap).

### 4. Runtime Monitoring

Distinct from active scanning — observing security signals from running systems via sources like Falco, WAF logs, SIEM logs, CSP violation reports, error monitoring, application/infrastructure logs. Useful for detecting suspicious behavior after deployment. Not implemented; not currently on the near-term roadmap.

### OWASP ZAP Scaling Consideration

OWASP ZAP is a powerful DAST tool but can become expensive and hard to scale if used incorrectly — if every public scan request started a new ZAP container, the system would quickly hit high CPU/memory usage, long queues, timeouts, and expensive infrastructure. This is not obvious at 10 users but becomes a serious problem at 100+. GuardRail Hub therefore treats ZAP as a **high-cost tool**, executed through queue-based jobs, worker capability checks, concurrency limits, timeout limits, target verification, and (for private or heavy scans) self-hosted workers.

### Public vs. Self-hosted ZAP Usage

For public users, GuardRail Hub is designed to avoid starting a ZAP container per request — public usage should default to lightweight checks (header/TLS/cookie/CORS scans, passive checks, availability-safe checks, limited baseline ZAP only if queued and verified). ZAP active scan is not intended to be a default public feature.

For self-hosted deployments, the operator controls worker count (`docker compose --profile zap up --scale zap=N`), standard Docker resource limits, network access, and scan timeouts, e.g.:

```env
ZAP_API_KEY=change-this-zap-key
ZAP_SCAN_TIMEOUT_SECONDS=600
ZAP_WORKER_HEARTBEAT_TIMEOUT_SECONDS=60
```

This is safer because the operator owns the environment and resources.

### Security Principles

* Do not run heavy security tools directly in public request handlers.
* Use queue-based execution for expensive tools.
* Use self-hosted workers for private or heavy scans.
* Require domain verification for active scans.
* Separate production passive scan from staging active scan.
* Use CI/CD scans to catch issues before deployment.
* Normalize reports from multiple tools.
* Audit sensitive actions.
* Do not expose private MCP tokens to web/mobile clients.
* Use policy checks before executing high-risk tools.

---

## Roadmap

### Phase 1: MCP Server MVP — done

* FastAPI MCP server, standalone mode
* Self-managed token model (declared; enforcement in progress)
* Tool/operation registry
* Local audit log
* Docker setup

### Phase 2: Runner MVP — done

* Self-registering ZAP worker pool
* OWASP ZAP API scan, scenario scan, and suite scan
* JSON, Markdown, and SARIF reports

### Phase 3: Web Control Plane

* Project management
* Token management
* Runner/worker registration UI
* Tool registry UI
* Scan run dashboard
* Finding dashboard
* Report viewer

### Phase 4: Expanded Tool Support

Planned tool categories, condensed from the platform's original tool-selection rationale:

| Category | Target Tool(s) | What it covers |
| --- | --- | --- |
| API scan | Schemathesis (in addition to ZAP) | OpenAPI-based testing, invalid input testing, auth-related behavior, status code validation |
| SAST | Semgrep | Insecure code patterns, dangerous API usage, injection-prone code, framework-specific issues, custom rules |
| Dependency scan (SCA) | OSV-Scanner or Dependency-Check | Vulnerable packages across Node.js, Python, Java, and other ecosystems |
| Secret scan | Gitleaks | API keys, private tokens, cloud credentials, database URLs, SSH keys, accidentally committed secrets |
| Container scan | Trivy | Vulnerable OS packages, vulnerable app dependencies, container image issues, misconfigurations |
| IaC scan | Checkov | Terraform, Kubernetes manifests, CloudFormation, Dockerfiles, CI/CD config, cloud security config |
| Mobile scan | MobSF | Android APK / iOS IPA static analysis, permission review, hardcoded secrets, mobile misconfigurations |
| E2E security test | Playwright | Login/logout flow, private route protection, RBAC, ownership-based access, auth bypass, cross-user data isolation |
| Full browser-based Web DAST | OWASP ZAP (context creation, form auth) | `scan_website_application` / `scan_interactive_web_session` completion |
| Performance | Apache JMeter | Not yet scoped in detail |
| LLM evaluation | LLM providers | Not yet scoped in detail |

### Phase 5: Production-ready Orchestration

* Worker/runner capability management
* Quota policy
* Domain verification
* Approval workflow
* Team/organization mode
* Connected MCP mode
* Self-hosted worker setup command

---

## License

GuardRail Hub Community Edition is licensed under the Apache License 2.0.

Enterprise features, hosted services, and advanced organization controls may be provided under a separate commercial license.
