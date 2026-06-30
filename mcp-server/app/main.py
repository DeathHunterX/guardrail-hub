"""
Main entry point for the GuardRail MCP Server.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_mcp import FastApiMCP

from app.constants.paths import ReportPaths
from app.core.config import settings
from app.routers.endpoints import MCP_OPERATIONS, tools_router
from app.routers.public.health_router import health_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.app_debug,
)

# FastAPI Middleware
if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Routers
app.include_router(health_router)
app.include_router(tools_router)

# Static files — generic public asset server (reports, future tools UI, etc.)
_public_dir = Path(ReportPaths.BASE_DIR)
_public_dir.mkdir(parents=True, exist_ok=True)
app.mount("/public", StaticFiles(directory=str(_public_dir), html=True), name="public")

# MCP — only expose tool endpoints (not health/root) as MCP tools
mcp = FastApiMCP(
    app,
    name="GuardRail MCP Server",
    description=(
        "Security testing tools powered by OWASP ZAP. "
        "Scan APIs and websites for vulnerabilities, run authenticated spider scans, "
        "and perform interactive browser-based security assessments."
    ),
    include_operations=MCP_OPERATIONS,
)

mcp.mount_http(mount_path="/mcp")
mcp.setup_server()


@app.get("/")
async def root():
    return {
        "name": "guardrail-mcp-server",
        "mode": settings.mcp_mode,
        "token_authority": settings.token_authority,
        "database_provider": settings.database_provider,
        "zap_container_prefix": settings.zap_container_name_prefix,
        "zap_containers": settings.zap_amount_of_containers,
        "status": "running",
        "health": "/health",
        "mcp": "/mcp",
        "tools": MCP_OPERATIONS,
    }
