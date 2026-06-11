from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

class Settings(BaseSettings):
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

    # =====================================================
    # Token / Auth
    # =====================================================
    token_authority: Literal["SELF_MANAGED", "PLATFORM_ISSUED"] = "SELF_MANAGED"
    token_algorithm: Literal["HS256", "RS256"] = "HS256"

    internal_token_secret: str = "change-this-secret"
    token_issuer: str = "guardrail-mcp-local"
    token_audience: str = "guardrail-mcp"
    token_expires_in_days: int = 90

    token_private_key_path: str | None = None
    token_public_key_path: str | None = None
    jwks_url: str | None = None

    # =====================================================
    # Platform Connection
    # =====================================================
    platform_api_url: str | None = None
    platform_api_token: str | None = None
    platform_token_introspection_path: str = "/internal/tokens/introspect"
    platform_audit_path: str = "/internal/audit/events"
    platform_timeout_seconds: int = 10

    # =====================================================
    # Persistence
    # =====================================================
    # NONE | POSTGRES | DYNAMODB
    database_provider: Literal["NONE", "POSTGRES", "DYNAMODB"] = "NONE"
    database_url: str | None = None

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "guardrail_hub"
    postgres_user: str = "guardrail"
    postgres_password: str | None = None

    dynamodb_endpoint_url: str | None = None
    dynamodb_table_prefix: str = "guardrail_local"
    aws_region: str = "ap-southeast-1"

    # =====================================================
    # Tool Policy
    # =====================================================
    tool_policy_path: str = "./config/tool-policy.json"
    allowed_tools_path: str = "./config/allowed-tools.json"

    allow_dangerous_tools: bool = False
    require_approval_for_high_risk: bool = True
    require_approval_for_critical_risk: bool = True

    # =====================================================
    # Workspace / Filesystem
    # =====================================================
    workspace_dir: str = "./data/workspace"
    temp_dir: str = "./data/tmp"
    max_file_size_mb: int = 10

    allow_path_traversal: bool = False
    blocked_file_patterns: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [".env", "*.pem", "*.key", "id_rsa", "id_ed25519"]
    )
    allowed_file_extensions: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [".txt", ".md", ".json", ".yaml", ".yml", ".log"]
    )

    # =====================================================
    # Audit Log
    # =====================================================
    # LOCAL | PLATFORM | BOTH | NONE
    audit_mode: Literal["LOCAL", "PLATFORM", "BOTH", "NONE"] = "LOCAL"
    audit_log_path: str = "./logs/audit.log"
    audit_log_format: Literal["jsonl", "json"] = "jsonl"
    audit_include_arguments: bool = False
    audit_mask_secrets: bool = True

    # =====================================================
    # Security Guard
    # =====================================================
    enable_secret_guard: bool = True
    enable_command_guard: bool = True
    enable_path_guard: bool = True

    disable_shell_execution: bool = True
    command_timeout_seconds: int = 30
    max_tool_execution_seconds: int = 60

    # =====================================================
    # Rate Limit
    # =====================================================
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # =====================================================
    # CORS
    # =====================================================
    cors_enabled: bool = False
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    cors_allow_credentials: bool = False

    # =====================================================
    # Logging
    # =====================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "json"
    log_file_path: str = "./logs/server.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator(
        "mcp_mode",
        "mcp_deployment_mode",
        "token_authority",
        "token_algorithm",
        "database_provider",
        "audit_mode",
        "log_level",
        mode="before",
    )
    @classmethod
    def normalize_uppercase_enum(cls, value):
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("audit_log_format", "log_format", mode="before")
    @classmethod
    def normalize_lowercase_enum(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator(
        "token_private_key_path",
        "token_public_key_path",
        "jwks_url",
        "platform_api_url",
        "platform_api_token",
        "database_url",
        "postgres_password",
        "dynamodb_endpoint_url",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value):
        if value == "":
            return None
        return value

    @field_validator("blocked_file_patterns", "allowed_file_extensions", mode="before")
    @classmethod
    def parse_csv_list(cls, value):
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]

        return value

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if value is None or value == "":
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]

        return value

    @field_validator("internal_token_secret")
    @classmethod
    def validate_internal_token_secret(cls, value: str):
        if value == "change-this-secret":
            # Allow in development, but you need to change in production.
            return value

        if len(value) < 32:
            raise ValueError("INTERNAL_TOKEN_SECRET must be at least 32 characters")

        return value

    @model_validator(mode="after")
    def enable_cors_when_origins_are_set(self):
        if self.cors_allow_origins:
            self.cors_enabled = True
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
