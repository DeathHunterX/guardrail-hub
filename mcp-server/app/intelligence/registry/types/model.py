"""Model type enum — the class of model.

ModelType and Capability serve different purposes:
- ModelType: What the model fundamentally IS (its primary classification)
- Capability: What the model CAN DO (supported operations)

A model has one ModelType but can have multiple Capabilities.
A model's capabilities may extend beyond its primary type.
"""

from enum import Enum


class ModelType(str, Enum):
    """Classification of LLM model types by their primary purpose.

    ModelType is what the model fundamentally IS:
    - A CHAT model is primarily designed for conversation
    - An EMBEDDING model is primarily designed for vectorization
    - A VISION model is primarily designed for image understanding

    ModelType and Capability are orthogonal:
    - ModelType classifies the model's PRIMARY purpose
    - Capability declares the model's SUPPORTED operations

    Example: A vision-language model might be:
    - ModelType.VISION (its primary purpose)
    - Capability={CHAT, VISION} (what it can actually do)

    Example: An embedding model would be:
    - ModelType.EMBEDDING (its primary purpose)
    - Capability={EMBEDDING} (same as type, no extension)
    """

    CHAT = "chat"  # Instruction-following chat model
    COMPLETION = "completion"  # Text completion model
    EMBEDDING = "embedding"  # Text embedding model
    VISION = "vision"  # Vision-language model
    SPEECH_TO_TEXT = "speech_to_text"  # Audio transcription
    TEXT_TO_SPEECH = "text_to_speech"  # Audio synthesis
    RERANK = "rerank"  # Reranking model
    MULTIMODAL = "multimodal"  # General multimodal model
