# Deployment Map

## Purpose

Describe how the implemented system runs and what operational infrastructure is absent.

## Scope

Docker, Compose, startup, configuration, logging and repository automation.

## AI Usage Guidance

Use actual Dockerfiles, Compose and settings as deployment truth. Do not infer production readiness from the existence of containers.

## Main Content

### Container topology

`docker-compose.yml` defines:

| Service | Role | Scaling/state |
|---|---|---|
| `mcp-server` | FastAPI + MCP control plane | Single application service in Compose |
| `postgres` | Optional relational persistence | Durable named volume |
| `zap` | Self-registering ZAP worker | Intended to scale horizontally |
| `jmeter-worker` | Isolated JMeter runtime | Intended to scale horizontally |

Compose uses an application network and a shared worker/control-plane network. The backend runs on Python 3.12 slim; ZAP uses the stable upstream image; JMeter is 5.6.3 on Temurin 21.

### Runtime startup

The server validates settings, initializes persistence/migrations, builds the LLM registry and credential/provider runtime, constructs shared operation and notification flows, and starts worker dispatch components. Production-mode configuration rejects unsafe or missing secret choices in several areas.

Credential backend behavior is platform-aware:

- Windows defaults to Windows Credential Manager.
- Non-Windows deployments must explicitly select mounted-file secrets or the environment backend; otherwise startup fails closed.
- The mounted-file backend defaults to `/run/secrets`.

### Observability

Application code primarily emits structured output through `MCPLogger`; Slack can receive user-facing lifecycle status. Health/liveness/readiness endpoints exist. There is no demonstrated metrics backend, distributed tracing stack, centralized log pipeline, SLO definition or production alerting configuration in this repository.

### Automation and delivery

`.github/workflows/aios-check.yml` validates AIOS structure, links, lint, architecture boundaries and intelligence drift. No product build/test/deploy workflow, Kubernetes manifests, Terraform, Helm, or release pipeline is present.

Repository workflow presence does not by itself make a check required: GitHub branch protection/rulesets must separately require the workflow's status check.

## Related Documents

[technology-stack.md](technology-stack.md) · [security-map.md](security-map.md) · [database-map.md](database-map.md)

## Last Updated

2026-08-28 — Compose, Dockerfiles, startup and CI re-reviewed.
