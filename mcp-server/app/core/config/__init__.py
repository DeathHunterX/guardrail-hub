"""
Settings assembly.

Each mixin file owns one category of settings + its validators.
Add a new tool by:
  1. Creating app/core/config/tools/_mytool.py with a MyToolMixin class.
  2. Adding MyToolMixin to the Settings base list below.

All code that currently does:
    from app.core.config import settings
continues to work unchanged.
"""
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config._app import AppMixin
from app.core.config._auth import AuthMixin
from app.core.config._database import DatabaseMixin
from app.core.config._security import SecurityMixin
from app.core.config._server import ServerMixin
from app.core.config.tools._zap import ZapMixin


class Settings(
    AppMixin,
    AuthMixin,
    DatabaseMixin,
    SecurityMixin,
    ServerMixin,
    ZapMixin,
    BaseSettings,  # BaseSettings must be last in MRO
):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Cross-category validators (fields that span multiple mixins)
    # ------------------------------------------------------------------

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
    def _normalize_uppercase_enum(cls, value):
        if isinstance(value, str):
            return value.strip().upper()
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
