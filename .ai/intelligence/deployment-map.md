# Deployment Map

## Purpose
Document how the system runs today — containers, orchestration, CI/CD, monitoring, logging — and what's absent.

## Scope
Deployment and operational tooling for `mcp-server/` and `web/`. Does not cover application-level architecture (see [codegraph.md](codegraph.md)).

## AI Usage Guidance
Do not assume Kubernetes manifests, CI pipelines, or monitoring infrastructure exist — none were found in the repository. If a task requires any of these, they need to be created from scratch, not modified.

## Main Content

### Applications & Containers

```mermaid
graph TD
    subgraph "docker-compose.yml (mcp-server/)"
        MCPService[mcp-server<br/>build: docker/fastapi/Dockerfile<br/>port 8787]
        ZapService[zap<br/>build: docker/owasp_zap/Dockerfile<br/>profile: zap]
        PGService[postgres:16-alpine<br/>profile: postgres, local-db]
    end
    MCPService --> PGService
    MCPService --> ZapService
    WebApp[web/ — no Dockerfile,<br/>run via next dev/start directly]
    Mobile[mobile/ — not implemented]
```

| Service | Definition | Ports | Volumes | Profile | Always runs? |
|---|---|---|---|---|---|
| `mcp-server` | `docker-compose.yml`, build `docker/fastapi/Dockerfile` | `${MCP_SERVER_PORT:-8787}:8787` | `./app`, `./config`, `./data`, `./logs`, `./public` | default | Yes |
| `postgres` | `postgres:16-alpine` | `${POSTGRES_PORT:-5432}:5432` | `postgres-data:/var/lib/postgresql/data` | `postgres`, `local-db` | Only with profile |
| `zap` | build `docker/owasp_zap/Dockerfile` | 8080/8090 (container-internal only, not host-mapped) | anonymous `/zap/wrk`, `/zap/reports` (not host-path — see below) | `zap` | Only with profile |

Network: single bridge network `app-network`. Named volume: `postgres-data`.

**`zap` supports `docker compose --profile zap up --scale zap=N`** with no application configuration change. It has no `container_name` (a fixed name would collide across replicas under `--scale`), and its `/zap/wrk`/`/zap/reports` volumes are anonymous rather than host-path bind mounts — every replica needs its own working directory, not one shared across all of them. Each replica self-registers with `mcp-server` on startup (see Dockerfiles below); there is no `ZAP_CONTAINER_NAME_PREFIX`/`ZAP_AMOUNT_OF_CONTAINERS` config anywhere — the Worker Registry (`app/integrations/owasp_zap/registry.py`) is the single source of truth for how many workers exist and where they are. See `architecture/zap-worker-pool/README.md` at the repo root for the full design.

### Dockerfiles

| File | Base | Builds |
|---|---|---|
| `mcp-server/docker/fastapi/Dockerfile` | `python:3.12-slim` | Installs `uv`, runs `uv sync --frozen --no-dev` against `pyproject.toml`/`uv.lock`, copies `app/` + `config/`, creates `data/logs/reports` dirs, exposes 8787, runs `uvicorn app.main:app --reload` |
| `mcp-server/docker/owasp_zap/Dockerfile` | `zaproxy/zap-stable` | Creates `/zap/sessions` owned by uid/gid 1000; installs `curl`; sets `ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]`, which runs ZAP (the container's `command:`) alongside `register-worker.sh` — the self-registration/heartbeat sidecar (`POST /workers/register`, periodic `POST /workers/heartbeat`, `DELETE /workers/{id}` on graceful shutdown) |

**No Dockerfile exists for `web/`** — it is not containerized; it runs via `next dev`/`next start` directly. No Dockerfile exists at the repository root either.

### Kubernetes / Helm

None. No manifests, no Helm charts anywhere in the repository — this is still aspirational, not implemented. The ZAP worker pool's design (self-registration + heartbeat, no server-side hostname generation, Registry as source of truth) is deliberately orchestrator-agnostic so a future Kubernetes Deployment/StatefulSet of ZAP pods could reuse the same `/workers/register` and `/workers/heartbeat` protocol without server-side changes — but no manifests exist yet.

### CI/CD

None. No `.github/workflows/`, no `Jenkinsfile`, no `.gitlab-ci.yml`, no other CI config anywhere in the repository. There is currently no automated build, test, or deploy pipeline — and, notably, no automated security scanning of Guardrail Hub's own code despite that being the product's purpose (see [security-map.md](security-map.md)).

### Monitoring

None. No Prometheus, Grafana, or other observability tooling/config found. The root README's "Runtime Monitoring" scanning mode (Falco/WAF/SIEM sources) is described as a target capability, not something implemented against Guardrail Hub's own deployment.

### Logging

| Aspect | Implementation |
|---|---|
| Mechanism | `MCPLogger` (`app/core/mcp_logger.py`) — the app's only logging path, no structured/centralized log shipping |
| Output | File-based, written to `mcp-server/logs/` (observed: `OWASP ZAP_*.log`, `OwaspZapPool_*.log`, `PostgresDAO_*.log`, `PostgresOperationDAO_*.log`) |
| Configuration | `LOG_LEVEL`, `LOG_FORMAT`, `LOG_FILE_PATH` (`.env.example`) |
| Aggregation/shipping | None — logs stay local to the container/host filesystem; no ELK/Loki/CloudWatch integration found |

### Environments

Only a local/dev environment is evidenced (Docker Compose with `${VAR:-default}` fallbacks, `.env`/`.env.example`). No staging or production environment configuration (e.g., separate compose files, environment-specific `.env` templates) was found.

## Related Documents
[technology-stack.md](technology-stack.md) · [security-map.md](security-map.md) · [system-overview.md](system-overview.md)

## Last Updated
2026-07-10 — updated for the ZAP Worker Pool refactor (scalable `zap` service, self-registration sidecar).
