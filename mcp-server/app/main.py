from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
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

# MCP
mcp = FastApiMCP(
    app,
    name="GuardRail MCP Server",
    description="Tools for security and testing",
    include_operations=[]
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
        "status": "running",
        "health": "/health",
        "mcp": "/mcp",
    }
