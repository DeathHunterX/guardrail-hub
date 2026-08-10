"""Provider type enum — the provider vendor/implementation."""

from enum import Enum


class ProviderType(str, Enum):
    """Classification of LLM provider types.

    These are the canonical provider categories. Specific providers
    (OpenAI, Anthropic, Ollama) extend these with their own identifiers.
    """

    OPENAI_COMPATIBLE = "openai_compatible"  # OpenAI API-compatible providers
    ANTHROPIC = "anthropic"  # Anthropic Claude API
    OLLAMA = "ollama"  # Ollama local inference
    BEDROCK = "bedrock"  # AWS Bedrock
    VERTEX = "vertex"  # Google Vertex AI
    AZURE = "azure"  # Azure OpenAI
    LOCAL = "local"  # Generic local inference
