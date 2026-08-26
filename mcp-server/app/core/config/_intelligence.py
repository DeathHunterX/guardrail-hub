"""Intelligence Layer settings mixin.

Adds registry paths for the Intelligence Layer. Defaults point to the unified
llm.yaml as the single source of truth.
"""

from __future__ import annotations


class IntelligenceMixin:
    # =====================================================
    # Intelligence Layer — Registry paths
    # =====================================================

    # Path to the unified LLM configuration YAML. This is the single source of
    # truth for all provider and model configuration. Defaults to a file shipped
    # in mcp-server/config.
    registry_llm_config_path: str = "config/llm.yaml"

    # When True (default), the runtime fails fast at startup if the
    # registry config file is missing. When False, an empty catalog is built
    # (useful for local dev where LLM work isn't enabled yet).
    registry_require_files: bool = True
