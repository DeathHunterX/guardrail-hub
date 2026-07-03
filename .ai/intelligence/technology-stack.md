# Technology Stack

## Purpose
List the concrete technologies, versions, and package managers in use, in one place, so an AI assistant doesn't have to reconstruct this from multiple config files.

## Scope
Runtime and tooling versions currently declared in the repository's own config files (`pyproject.toml`, `package.json`, Dockerfiles, `docker-compose.yml`). Does not include tools the root README lists as future/planned (see [system-overview.md](system-overview.md) for that distinction).

## AI Usage Guidance
Use this as the source of truth for "what version/framework are we on" instead of inferring from import statements. When adding a dependency, check here first for an existing package that already covers the need.

## Main Content

### Backend — `mcp-server/`

| Layer | Technology | Version | Source |
|---|---|---|---|
| Language | Python | ≥3.12 (`.python-version` = 3.12) | `pyproject.toml`, `.python-version` |
| Package manager | `uv` | — | `uv.lock`, Dockerfile |
| Web framework | FastAPI | ≥0.136.3 | `pyproject.toml` |
| MCP exposure | `fastapi-mcp` | ≥0.4.0 | `pyproject.toml` |
| ASGI server | `uvicorn` | — | `pyproject.toml` |
| Config | `pydantic-settings` | — | `pyproject.toml` |
| Postgres driver | `psycopg2-binary` | — | `pyproject.toml` |
| AWS SDK | `boto3` | — | `pyproject.toml` (DynamoDB backend) |
| JWT | `pyjwt` | — | `pyproject.toml` (declared, unused — see [security-map.md](security-map.md)) |
| Password hashing | `bcrypt` | — | `pyproject.toml` (declared, unused) |
| ZAP SDK | `zaproxy` | — | `pyproject.toml` |
| Container base | `python:3.12-slim` | — | `docker/fastapi/Dockerfile` |

### Frontend — `web/`

| Layer | Technology | Version | Source |
|---|---|---|---|
| Framework | Next.js | ^15.3.4 (App Router) | `package.json` |
| UI library | React / React DOM | ^19.1.0 | `package.json` |
| Language | TypeScript | ^5.8.3 | `package.json` (devDependency) |
| Package manager | `bun` | — | `bun.lock` present |
| Styling | Tailwind CSS | ^3.4.17 | `package.json` |
| Component primitives | Radix UI (via shadcn/ui) | various | `package.json`, `components.json` |
| Animation | GSAP + `@gsap/react` | — | `package.json` |
| Icons | `lucide-react` | — | `package.json` |
| Theming | `next-themes` | — | `package.json` |
| Linting | ESLint (`eslint-config-next`) | ^8.57.1 | `package.json` |
| Formatting | Prettier + `prettier-plugin-tailwindcss` | — | `package.json` |

### Data Storage

| Store | Version/Image | Role |
|---|---|---|
| PostgreSQL | `postgres:16-alpine` | One of two pluggable persistence backends (`DATABASE_PROVIDER=POSTGRES`) |
| DynamoDB | AWS or local (`DYNAMODB_ENDPOINT_URL`) | The other pluggable backend (`DATABASE_PROVIDER=DYNAMODB`) |

No ORM — raw `psycopg2` and `boto3` calls through a hand-written DAO layer (see [database-map.md](database-map.md)).

### Security Tooling

| Tool | Status |
|---|---|
| OWASP ZAP (`zaproxy/zap-stable` image) | Implemented — see [security-map.md](security-map.md) |
| Semgrep, Gitleaks, Trivy, Checkov, MobSF, OSV-Scanner, Schemathesis, Playwright, Selenium, JMeter | Not implemented — named in root README as MVP/target tools only |

### Infrastructure

| Aspect | Technology |
|---|---|
| Local orchestration | Docker Compose (`mcp-server/docker-compose.yml`) |
| Container runtime | Docker |
| Orchestration at scale | None yet (no Kubernetes/Helm — see [deployment-map.md](deployment-map.md)) |
| CI/CD | None yet |

### Mobile

No technology chosen yet — `mobile/android/` and `mobile/apple/` are empty scaffolds with no project files, dependency manifests, or build config of any kind.

## Related Documents
[dependency-graph.md](dependency-graph.md) · [deployment-map.md](deployment-map.md) · [project-map.md](project-map.md)

## Last Updated
2026-07-03 — verified against commit `10bd79b`.
