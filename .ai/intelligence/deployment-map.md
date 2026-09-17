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
- The mounted-file backend resolves `/run/secrets/<provider_id>` by default and is read-only; the environment backend is also read-only and externally managed.
- AWS/Bedrock remains isolated from the API-key credential store and uses the AWS SDK credential chain.

### Credential provisioning and consumption

Credential provisioning is a host/operator concern, separate from runtime consumption:

| Context | Contract |
|---|---|
| Windows local host | Masked input is tested before persistence to Windows Credential Manager as `GuardrailHub:<provider_id>`. |
| Recognized Guardrail Hub Compose host | Masked input is tested before an atomic write to `./secrets/<provider_id>`; POSIX hosts use directory/file modes `0700`/`0600`, and Windows hosts apply hardened ACLs. |
| Running MCP container | `ContainerFileCredentialBackend` reads `/run/secrets/<provider_id>` from the read-only `./secrets:/run/secrets:ro` mount; it cannot set or delete credentials. |
| Environment mode | `api_key_env` or its approved fallback names an externally managed environment variable; Guardrail Hub does not mutate it. |

Provider API-key values are not persisted to `.env`, `llm.yaml`, or Compose environment entries. Generic Linux hosts are not writable setup targets unless the Guardrail Hub Compose project is positively recognized.

### Observability

Application code primarily emits structured output through `MCPLogger`; Slack can receive user-facing lifecycle status. Health/liveness/readiness endpoints exist. There is no demonstrated metrics backend, distributed tracing stack, centralized log pipeline, SLO definition or production alerting configuration in this repository.

### Automation and delivery

`.github/workflows/aios-check.yml` validates AIOS structure, links, lint, architecture boundaries and intelligence drift. No product build/test/deploy workflow, Kubernetes manifests, Terraform, Helm, or release pipeline is present.

Repository workflow presence does not by itself make a check required: GitHub branch protection/rulesets must separately require the workflow's status check.

## Related Documents

[technology-stack.md](technology-stack.md) · [security-map.md](security-map.md) · [database-map.md](database-map.md)

## Last Updated

2026-09-17 — deployment, startup and automation sources re-reviewed at `3632394`; no content change required.
