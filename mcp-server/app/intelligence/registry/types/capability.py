"""Capability enum — what a model or provider can do.

ModelType and Capability serve different purposes:
- ModelType: What the model fundamentally IS (chat model, embedding model, etc.)
- Capability: What the model CAN DO (support for specific operations)

A model can have one ModelType but multiple Capabilities.
Example: A "multimodal" ModelType might have CHAT + VISION capabilities.
"""

from enum import Enum


class Capability(str, Enum):
    """Capabilities a model or provider supports.

    Stored as frozenset[Capability] on models/providers to allow
    multiple capabilities per entity.

    ModelType and Capability are orthogonal:
    - ModelType classifies what the model IS (its primary purpose)
    - Capability declares what the model CAN DO (supported operations)

    Example combinations:
    - A vision model: ModelType.VISION, Capability={VISION}
    - A multimodal chat model: ModelType.CHAT, Capability={CHAT, VISION}
    - An embedding model: ModelType.EMBEDDING, Capability={EMBEDDING}
    """

    CHAT = "chat"  # Text chat completion
    EMBEDDING = "embedding"  # Text vectorization
    VISION = "vision"  # Image understanding
    SPEECH = "speech"  # Audio transcription/synthesis
    RERANK = "rerank"  # Document reranking
    HEALTH = "health"  # Health monitoring capability
