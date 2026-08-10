"""Intelligence Layer settings mixin.

Adds registry paths for the Intelligence Layer. Defaults match the empty
``config/providers.yaml`` and ``config/models.yaml`` placeholders shipped
in Phase 2. Phase 3 will use the same keys for real providers.
"""

from __future__ import annotations

from pathlib import Path


class IntelligenceMixin:
    # =====================================================
    # Intelligence Layer — Registry paths
    # =====================================================

    # Path to the provider registry YAML. Defaults to a file shipped in
    # mcp-server/config; production deployments override via env or .env.
    registry_providers_path: str = "config/providers.yaml"

    # Path to the model registry YAML. Same convention as providers.
    registry_models_path: str = "config/models.yaml"

    # When True (default), the runtime fails fast at startup if either
    # registry file is missing. When False, an empty catalog is built
    # (useful for local dev where LLM work isn't enabled yet).
    registry_require_files: bool = True