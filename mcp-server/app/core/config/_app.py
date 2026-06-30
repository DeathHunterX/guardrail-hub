from typing import Literal


class AppMixin:
    # =====================================================
    # App / Server
    # =====================================================
    app_name: str = "GuardRail MCP Server"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_version: str = "0.1.0"

    mcp_server_host: str = "0.0.0.0"
    mcp_server_port: int = 8787
    mcp_server_public_url: str = "http://localhost:8787"

    # =====================================================
    # Deployment Mode
    # =====================================================
    mcp_mode: Literal["STANDALONE", "CONNECTED"] = "STANDALONE"
    mcp_deployment_mode: Literal["HOSTED_PUBLIC", "SELF_HOSTED_PRIVATE"] = (
        "SELF_HOSTED_PRIVATE"
    )
