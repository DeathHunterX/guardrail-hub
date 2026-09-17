# Technology Stack

## Purpose

Record the technologies and declared versions currently used by the product.

## Scope

Backend, web, workers, persistence and local tooling. Version constraints come from manifests and images, not installed developer environments.

## AI Usage Guidance

Use project manifests as final authority before adding a dependency. Prefer existing libraries and patterns.

## Main Content

### Backend

| Technology | Declared version/range | Use |
|---|---|---|
| Python | `>=3.12` | Backend and AIOS tooling |
| FastAPI | `>=0.136.3` | HTTP API |
| Uvicorn | `>=0.49.0` | ASGI server |
| FastAPI-MCP | `>=0.4.0` | MCP exposure |
| Pydantic Settings | `>=2.14.1` | Typed configuration |
| HTTPX | `>=0.28.0` | Async HTTP integrations/providers |
| boto3 | `>=1.38.0` | AWS Bedrock and DynamoDB access |
| psycopg2-binary | `>=2.9.10` | PostgreSQL access |
| PyYAML | `>=6.0.3` | LLM provider/model configuration loading |
| zaproxy | `>=0.5.0` | OWASP ZAP client |
| PyJWT / bcrypt | `>=2.13.0` / `>=5.0.0` | Security primitives present in dependencies |

The project uses `uv.lock`; tests and quality tooling are declared in the backend's development configuration/lockfile rather than being runtime requirements.

### Web

| Technology | Declared version/range |
|---|---|
| Next.js | `^16.2.10` |
| React / React DOM | `^19.2.7` |
| TypeScript | `^5.9.3` |
| Tailwind CSS | `^3.4.19` |
| ESLint | `^9.39.4` |
| GSAP | `^3.15.0` |
| Radix UI | Component packages at current declared ranges |

The web scripts are `dev`, `build`, `start`, `lint`, and `typecheck`.

### Runtime infrastructure

| Technology | Use |
|---|---|
| Docker Compose | Local multi-service orchestration |
| PostgreSQL | Durable operations and conversations |
| DynamoDB | Alternative operation store |
| OWASP ZAP stable image | DAST workers |
| Apache JMeter 5.6.3 / Temurin 21 | Performance workers |
| Ollama, OpenAI-compatible APIs, AWS Bedrock | LLM providers |
| Slack Web API | Optional notifications |

No Kubernetes, Terraform, Helm or application observability SDK is evidenced in the repository.

## Related Documents

[deployment-map.md](deployment-map.md) · [dependency-graph.md](dependency-graph.md) · [conventions.md](conventions.md)

## Last Updated

2026-09-17 — dependency manifests and container definitions re-reviewed at `3632394`.
