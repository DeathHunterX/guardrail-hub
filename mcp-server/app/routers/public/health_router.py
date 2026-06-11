import socket
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from app.core.config import settings


health_router = APIRouter(prefix="/health", tags=["health"])


def _tcp_check(host: str, port: int, timeout_seconds: float = 1.5) -> dict:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return {"status": "ok", "host": host, "port": port}
    except OSError as exc:
        return {
            "status": "error",
            "host": host,
            "port": port,
            "message": str(exc),
        }


def _postgres_target() -> tuple[str, int]:
    if settings.database_url:
        parsed = urlparse(settings.database_url)
        if parsed.hostname:
            return parsed.hostname, parsed.port or 5432

    return settings.postgres_host, settings.postgres_port


def _dynamodb_target() -> tuple[str, int] | None:
    if not settings.dynamodb_endpoint_url:
        return None

    parsed = urlparse(settings.dynamodb_endpoint_url)
    if not parsed.hostname:
        return None

    default_port = 443 if parsed.scheme == "https" else 80
    return parsed.hostname, parsed.port or default_port


def _storage_check() -> dict:
    provider = settings.database_provider

    if provider == "NONE":
        return {"provider": provider, "status": "skipped"}

    if provider == "POSTGRES":
        host, port = _postgres_target()
        return {"provider": provider, **_tcp_check(host, port)}

    if provider == "DYNAMODB":
        target = _dynamodb_target()
        if target is None:
            return {
                "provider": provider,
                "status": "skipped",
                "mode": "aws",
                "region": settings.aws_region,
            }

        host, port = target
        return {"provider": provider, **_tcp_check(host, port)}

    return {"provider": provider, "status": "error", "message": "Unknown provider"}


@health_router.get("")
async def health_check():
    return await live_check()


@health_router.get("/live")
async def live_check():
    return {
        "status": "ok",
        "service": "guardrail-mcp-server",
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@health_router.get("/ready")
async def readiness_check():
    storage = _storage_check()
    payload = {
        "status": "ok" if storage["status"] in {"ok", "skipped"} else "error",
        "service": "guardrail-mcp-server",
        "storage": storage,
        "audit_mode": settings.audit_mode,
        "token_authority": settings.token_authority,
    }

    if payload["status"] != "ok":
        raise HTTPException(status_code=503, detail=payload)

    return payload
