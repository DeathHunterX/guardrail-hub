# GuardRail Hub

GuardRail Hub is a developer-focused **security testing and QA orchestration platform** that connects multiple security and testing tools into one controlled workflow.

The project focuses on helping developers, teams, and organizations validate security, system behavior, and release readiness across:

* Web applications
* APIs
* Mobile applications
* Containers
* Dependencies
* Secrets
* Infrastructure as Code
* E2E security flows
* MCP-based internal tools

GuardRail Hub is not designed to be a wrapper around one scanner. It is designed as a **multi-tool security and testing orchestration platform**.

---

## Project Vision

GuardRail Hub provides a unified way to run, control, and report security/testing tools across different environments.

The core idea is:

> A security testing MCP/platform that orchestrates multiple security and QA tools across web, API, mobile, container, dependency, secret, IaC, and E2E testing.

Instead of asking developers to manually run many tools separately, GuardRail Hub provides:

* Tool orchestration
* Runner management
* Token-based access control
* Policy enforcement
* Queue-based execution
* Audit logging
* Unified reports
* Public and self-hosted execution modes
* MCP integration for AI/client-driven tool interaction

---

## MVP Toolset

For the MVP, GuardRail Hub does not try to support 50 tools.

The first version focuses on a small but strong set of security and QA tools:

| Category          | Suggested First Tool            |
| ----------------- | ------------------------------- |
| Web DAST          | OWASP ZAP                       |
| API scan          | ZAP API Scan or Schemathesis    |
| SAST              | Semgrep                         |
| Dependency scan   | OSV-Scanner or Dependency-Check |
| Secret scan       | Gitleaks                        |
| Container scan    | Trivy                           |
| IaC scan          | Checkov                         |
| Mobile scan       | MobSF                           |
| E2E security test | Playwright                      |
| Report format     | SARIF + JSON + Markdown + HTML         |

This gives the project a clear message:

> GuardRail Hub is a security testing MCP/platform that orchestrates multiple security and QA tools across web, API, mobile, container, dependency, secret, IaC, and E2E testing.

---

## Why This Toolset?

The MVP toolset is selected to cover the most common security/testing areas developers face in real projects.

### Web DAST

OWASP ZAP is used for web application dynamic security testing.

It can support:

* Passive scan
* Baseline scan
* Active scan
* API scan
* Security misconfiguration detection

However, ZAP is treated as a **heavy scanner**, not a default public realtime scan engine.

---

### API Scan

GuardRail Hub can use either:

* ZAP API Scan
* Schemathesis

This category focuses on API security and behavior testing, such as:

* OpenAPI-based API testing
* Invalid input testing
* Auth-related API behavior
* Status code validation
* Unexpected response detection

---

### SAST

Semgrep is used for static code analysis.

It can detect:

* Insecure code patterns
* Dangerous API usage
* Injection-prone patterns
* Framework-specific security issues
* Custom team rules

---

### Dependency Scan

OSV-Scanner or Dependency-Check can be used for dependency vulnerability scanning.

This helps detect vulnerable packages in:

* Node.js projects
* Python projects
* Java projects
* Other package ecosystems

---

### Secret Scan

Gitleaks is used for detecting secrets inside source code or repository history.

It can detect:

* API keys
* Private tokens
* Cloud credentials
* Database URLs
* SSH keys
* Accidentally committed secrets

---

### Container Scan

Trivy is used for container and filesystem scanning.

It can detect:

* Vulnerable OS packages
* Vulnerable application dependencies
* Container image issues
* Misconfigurations

---

### IaC Scan

Checkov is used for Infrastructure as Code scanning.

It can detect issues in:

* Terraform
* Kubernetes manifests
* CloudFormation
* Dockerfiles
* CI/CD configuration
* Cloud security configuration

---

### Mobile Scan

MobSF is used for mobile application security analysis.

It can support:

* Android APK scanning
* iOS IPA scanning
* Static mobile analysis
* Permission review
* Hardcoded secret detection
* Mobile security misconfiguration checks

---

### E2E Security Test

Playwright is used for E2E security and system behavior testing.

It can validate:

* Login flow
* Logout flow
* Private route protection
* RBAC behavior
* Ownership-based access
* Auth bypass attempts
* Sensitive field exposure
* User A cannot access User B’s data

---

### Report Format

GuardRail Hub normalizes output into:

* SARIF
* JSON
* Markdown

The goal is to allow reports to be used in:

* Web dashboard
* Pull requests
* Merge requests
* CI/CD artifacts
* Security review documents
* Audit history

---

## Production Scanning Strategy

Production scanning must be handled carefully.

Not all security tools are safe to run directly against production systems, especially when many users can trigger scans at the same time.

GuardRail Hub separates scanning modes based on environment and risk level.

| Mode                    | Safe Tools                                                   |
| ----------------------- | ------------------------------------------------------------ |
| Production passive scan | Header scan, TLS scan, passive ZAP, availability-safe checks |
| Staging active scan     | ZAP active scan, Burp, fuzzing, auth bypass tests            |
| CI/CD scan              | SAST, SCA, secret scan, IaC scan, container scan             |
| Runtime monitoring      | Falco, WAF logs, SIEM, CSP reports, error monitoring         |

---

## Scanning Modes

### 1. Production Passive Scan

Production passive scan is designed to be safe for live systems.

It should avoid aggressive payloads, fuzzing, destructive behavior, or high request volume.

Recommended checks:

* Security headers
* TLS configuration
* HTTPS redirect
* Cookie flags
* CORS basic checks
* Passive ZAP scan
* Availability-safe checks
* Basic exposure checks
* Public metadata checks

Production passive scan should be:

* Low impact
* Rate-limited
* Queue-controlled
* Safe for public-facing systems
* Suitable for scheduled monitoring

---

### 2. Staging Active Scan

Staging active scan is used for deeper security testing.

This mode can include more aggressive tools and techniques because it should run against a staging or test environment.

Recommended tools/checks:

* ZAP active scan
* Burp Suite
* API fuzzing
* Auth bypass tests
* Business logic tests
* Broken access control tests
* Injection payload tests
* File upload abuse tests

Staging active scan should require:

* Explicit target approval
* Correct environment selection
* Strong rate limits
* Timeout limits
* Clear audit logs

---

### 3. CI/CD Scan

CI/CD scan is designed to run before code reaches production.

Recommended tools:

* Semgrep for SAST
* OSV-Scanner or Dependency-Check for dependency scanning
* Gitleaks for secret scanning
* Checkov for IaC scanning
* Trivy for container scanning
* Playwright for E2E security tests

CI/CD scans are useful because they catch issues before deployment.

They can block merge or deployment when critical issues are found.

---

### 4. Runtime Monitoring

Runtime monitoring is not the same as active scanning.

It focuses on observing security signals from running systems.

Recommended sources:

* Falco
* WAF logs
* SIEM logs
* CSP violation reports
* Error monitoring
* Application logs
* Infrastructure logs

Runtime monitoring is useful for detecting suspicious behavior after deployment.

---

## OWASP ZAP Scaling Consideration

OWASP ZAP is a powerful DAST tool, but it can become expensive and difficult to scale if used incorrectly.

A major concern is public usage.

If every public scan request starts a new ZAP container, the system can quickly run into problems:

* High CPU usage
* High memory usage
* Long scan queues
* Timeout issues
* Poor user experience
* Expensive infrastructure
* Risky production scanning behavior

This may not be obvious with 10 users, but it becomes a serious architecture problem with 100+ users.

Therefore, GuardRail Hub treats ZAP as a **high-cost tool**.

ZAP should be executed through:

* Queue-based jobs
* Runner capability checks
* Concurrency limits
* Timeout limits
* Target verification
* Self-hosted runners for private or heavy scans

---

## Public vs Self-hosted ZAP Usage

### Public Web/Mobile Usage

For public users, GuardRail Hub should not start a ZAP container for every request.

Public users should use lightweight checks by default.

Recommended public mode:

* Header scan
* TLS scan
* Cookie flag scan
* Basic CORS check
* Passive checks
* Availability-safe checks
* Limited ZAP baseline only if queued and verified

ZAP active scan should not be a default public feature.

---

### Self-hosted Customer Usage

For customers using a self-hosted MCP server or self-hosted runner, ZAP can be scaled based on their own infrastructure.

In this mode, the customer controls:

* Number of ZAP containers
* Runner concurrency
* CPU limit
* Memory limit
* Network access
* Internal target access
* Scan timeout
* Scan scheduling

Example:

```env
ZAP_ENABLED=true
ZAP_MAX_CONCURRENT_JOBS=3
ZAP_CONTAINER_MEMORY_LIMIT=2g
ZAP_CONTAINER_CPU_LIMIT=1
ZAP_JOB_TIMEOUT_SECONDS=1800
```

This is safer because the customer owns the environment and resources.

---

## Architecture Overview

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

---

## Repository Structure

```txt
guardrail/
│
├── web/
│   ├── app/
│   ├── components/
│   ├── features/
│   ├── server/
│   ├── prisma/
│   ├── public/
│   ├── .env.example
│   ├── package.json
│   └── README.md
│
├── mobile/
│   ├── app/
│   ├── components/
│   ├── features/
│   ├── lib/
│   ├── assets/
│   ├── .env.example
│   ├── package.json
│   └── README.md
│
├── mcp-server/
│   ├── app/
│   │   ├── core/
│   │   ├── routers/
│   │   │   ├── public/
│   │   │   ├── mcp/
│   │   │   └── internal/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── dependencies/
│   │   ├── tools/
│   │   ├── policies/
│   │   ├── audit/
│   │   ├── clients/
│   │   ├── security/
│   │   └── main.py
│   │
│   ├── cli/
│   ├── config/
│   ├── examples/
│   ├── docs/
│   ├── tests/
│   ├── data/
│   ├── logs/
│   ├── scripts/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── pyproject.toml
│   └── README.md
│
├── runner/
│   ├── app/
│   │   ├── core/
│   │   ├── jobs/
│   │   ├── tools/
│   │   │   ├── zap/
│   │   │   ├── schemathesis/
│   │   │   ├── semgrep/
│   │   │   ├── osv_scanner/
│   │   │   ├── dependency_check/
│   │   │   ├── gitleaks/
│   │   │   ├── trivy/
│   │   │   ├── checkov/
│   │   │   ├── mobsf/
│   │   │   ├── playwright/
│   │   │   └── lightweight/
│   │   │
│   │   ├── orchestrator/
│   │   │   ├── tool_registry.py
│   │   │   ├── runner_selector.py
│   │   │   ├── concurrency_limiter.py
│   │   │   └── job_dispatcher.py
│   │   │
│   │   ├── reports/
│   │   │   ├── normalizer.py
│   │   │   ├── sarif.py
│   │   │   ├── json_report.py
│   │   │   └── markdown.py
│   │   │
│   │   └── policies/
│   │       ├── capability_policy.py
│   │       ├── quota_policy.py
│   │       └── target_policy.py
│   │
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   └── README.md
│
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   ├── mcp-server.md
│   ├── runner.md
│   ├── web.md
│   └── mobile.md
│
├── docker/
├── scripts/
├── README.md
└── LICENSE
```

---

## MCP Server

The MCP server is a standalone FastAPI service.

It can be deployed separately and given to customers as:

* A source folder
* A Docker image
* A docker-compose setup
* A copy-paste install command

The MCP server should not depend directly on the web platform source code.

It should only communicate with the web platform through API calls when running in connected mode.

### MCP Server Modes

```txt
STANDALONE
CONNECTED
```

### Token Authority

```txt
SELF_MANAGED
PLATFORM_ISSUED
```

### Example MCP Server Setup

```bash
cd mcp-server
cp .env.example .env
uv sync
uv run python run.py
```

Check health:

```bash
curl http://localhost:8787/health
```

Run with Docker:

```bash
cd mcp-server
cp .env.example .env
docker compose up -d --build
```

---

## Runner

The runner executes tools through jobs.

It should not run heavy tools directly inside web/mobile requests.

The runner is responsible for:

* Pulling or receiving scan jobs
* Checking tool capability
* Applying concurrency limits
* Running the selected tool
* Parsing tool output
* Normalizing findings
* Generating reports

### Example Runner Tool Metadata

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

---

## Tool Registry

GuardRail Hub uses a tool registry to define supported tools.

Each tool can define:

* Name
* Category
* Risk level
* Resource cost
* Execution mode
* Required permissions
* Required runner capability
* Timeout
* Concurrency limit
* Output parser
* Report mapping

Example categories:

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

---

## Report Normalization

Each tool has its own output format.

GuardRail Hub normalizes results into a common finding model.

Example:

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

Supported report outputs:

* SARIF
* JSON
* Markdown

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

Install pnpm:

```bash
npm install -g pnpm
```

Install uv:

```bash
pip install uv
```

---

## Setup Root Project

```bash
git clone <repository-url> guardrail
cd guardrail
```

---

## Setup Web Platform

```bash
cd web
cp .env.example .env
pnpm install
pnpm dev
```

Default URL:

```txt
http://localhost:3000
```

---

## Setup MCP Server

```bash
cd mcp-server
cp .env.example .env
uv sync
uv run python run.py
```

Default URL:

```txt
http://localhost:8787
```

Health check:

```bash
curl http://localhost:8787/health
```

---

## Setup Runner

```bash
cd runner
cp .env.example .env
docker compose up -d --build
```

Example runner `.env`:

```env
RUNNER_MODE=SELF_HOSTED
RUNNER_ID=local_runner

LIGHTWEIGHT_CHECK_ENABLED=true

ZAP_ENABLED=true
ZAP_MAX_CONCURRENT_JOBS=1
ZAP_JOB_TIMEOUT_SECONDS=900

SEMGREP_ENABLED=true
GITLEAKS_ENABLED=true
TRIVY_ENABLED=true
CHECKOV_ENABLED=true
MOBSF_ENABLED=false
```

---

## Development Flow

1. Start the MCP server.
2. Start the web platform.
3. Start the runner.
4. Register the runner in the web platform.
5. Configure available tools.
6. Create a project target.
7. Run a scan workflow.
8. Review normalized findings and reports.

---

## Example Scan Workflow

```txt
User selects scan workflow
        ↓
GuardRail API validates project and permission
        ↓
Policy engine checks tool risk and target environment
        ↓
Scan job is queued
        ↓
Runner selector finds a capable runner
        ↓
Runner executes tools
        ↓
Tool outputs are normalized
        ↓
SARIF / JSON / Markdown reports are generated
        ↓
Findings are shown in dashboard
```

---

## Security Principles

GuardRail Hub follows these principles:

* Do not run heavy security tools directly in public request handlers.
* Use queue-based execution for expensive tools.
* Use self-hosted runners for private or heavy scans.
* Require domain verification for active scans.
* Separate production passive scan from staging active scan.
* Use CI/CD scans to catch issues before deployment.
* Normalize reports from multiple tools.
* Audit sensitive actions.
* Do not expose private MCP tokens to web/mobile clients.
* Use policy checks before executing high-risk tools.

---

## Roadmap

### Phase 1: MCP Server MVP

* FastAPI MCP server
* Standalone mode
* Self-managed token
* Tool registry
* Basic policy check
* Local audit log
* Docker setup

### Phase 2: Runner MVP

* Lightweight web checks
* OWASP ZAP baseline scan
* Semgrep
* Gitleaks
* Trivy
* JSON and Markdown reports

### Phase 3: Web Control Plane

* Project management
* Token management
* Runner registration
* Tool registry UI
* Scan run dashboard
* Finding dashboard
* Report viewer

### Phase 4: Expanded Tool Support

* Schemathesis
* OSV-Scanner or Dependency-Check
* Checkov
* MobSF
* Playwright E2E security tests
* SARIF export

### Phase 5: Production-ready Orchestration

* Runner capability management
* Quota policy
* Domain verification
* Approval workflow
* Team/organization mode
* Connected MCP mode
* Self-hosted runner setup command

---

## License

GuardRail Hub Community Edition is licensed under the Apache License 2.0.

Enterprise features, hosted services, and advanced organization controls may be provided under a separate commercial license.

---

## Summary

GuardRail Hub is a multi-tool security and QA orchestration platform for developers and teams.

It integrates tools such as OWASP ZAP, Semgrep, Gitleaks, Trivy, Checkov, MobSF, Schemathesis, and Playwright into a controlled workflow with:

* MCP support
* Runner-based execution
* Token-based access control
* Policy enforcement
* Queue-based scanning
* Public and self-hosted modes
* Unified SARIF, JSON, and Markdown reports

The main goal is to help developers and teams safely validate system behavior and security across web, API, mobile, container, dependency, secret, IaC, and E2E testing.
