"""Hexagonal ports for the Intelligence Layer.

These are the inbound/driving contracts that providers must implement.
Each port represents a specific capability (chat, embedding, vision, etc.).

Application code depends only on these contracts, never on a specific
provider implementation. Adding a new provider is only "implement these ports"
— no change to the Inference Service or Registry.
"""

from app.intelligence.ports.base import BaseProvider
from app.intelligence.ports.chat import ChatCapable
from app.intelligence.ports.embedding import EmbeddingCapable
from app.intelligence.ports.health import HealthCheckable
from app.intelligence.ports.rerank import RerankCapable
from app.intelligence.ports.speech import SpeechCapable
from app.intelligence.ports.vision import VisionCapable

__all__ = [
    "BaseProvider",
    "ChatCapable",
    "EmbeddingCapable",
    "HealthCheckable",
    "RerankCapable",
    "SpeechCapable",
    "VisionCapable",
]
