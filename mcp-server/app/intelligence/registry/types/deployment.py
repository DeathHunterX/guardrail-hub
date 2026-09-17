"""Deployment type enum — how the provider is hosted."""

from enum import Enum


class DeploymentType(str, Enum):
    """Where and how the LLM is deployed."""

    CLOUD = "cloud"  # SaaS API (OpenAI, Anthropic, etc.)
    SELF_HOSTED = "self_hosted"  # Self-hosted server (Ollama, vLLM, etc.)
    PROXY = "proxy"  # Local proxy/gateway
    LOCAL = "local"  # Local inference (llama.cpp, etc.)
