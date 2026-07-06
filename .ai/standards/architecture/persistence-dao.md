---
id: standards/architecture/persistence-dao
title: Persistence via Hand-Written DAO
version: 1.0.0
status: Active
owner: backend-owner
category: architecture
scope: data persistence in mcp-server
severity_default: blocking
applies_to: [mcp-server/app/dao/**, mcp-server/app/services/**]
enforced_by: []
depends_on: [standards/architecture/backend-layering]
validated_against: [standards/architecture/backend-layering@1.0.0]
---

# Persistence via Hand-Written DAO

> Distilled from [intelligence/conventions.md](../../intelligence/conventions.md) and [intelligence/database-map.md](../../intelligence/database-map.md). Status `Review` pending M4 activation.

## Scope
All persisted-data access in `mcp-server/`. Assumes the layering rules of [backend-layering](backend-layering.md) (declared as a dependency).

## Rule Definitions
- **R1** Persistence goes through `app/dao/`, never via an ORM (no SQLAlchemy models).
- **R2** A common interface (`app/dao/base.py`) is implemented per backend (`postgres/`, `dynamodb/`).
- **R3** The backend is selected at runtime by configuration (`DATABASE_PROVIDER`), not hard-coded at the call site.
- **R4** Services depend on the DAO interface, never on a concrete backend implementation.

## Mandatory Rules
R1–R4 are all Mandatory (blocking).

## Optional Recommendations
Keep DAO methods coarse (one method per persisted operation) rather than exposing query fragments upward.

## Exceptions
A read-only diagnostic script may query directly, but nothing in the request path may bypass the DAO interface.

## Anti-patterns
- Importing `sqlalchemy` and defining ORM models.
- A service importing `PostgresDAO` directly instead of the `base` interface, breaking backend-swappability.
- Hard-coding the provider (`if True: use postgres`) instead of honoring `DATABASE_PROVIDER`.

## Examples
`app/dao/base.py` with `postgres/` and `dynamodb/` implementations selected by config is the reference — see [intelligence/database-map.md](../../intelligence/database-map.md).
