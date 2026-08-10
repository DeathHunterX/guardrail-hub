"""Vision capability port — image understanding."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Sequence

from app.intelligence.registry.types.capability import Capability


@dataclass(frozen=True, slots=True)
class ImageContent:
    """An image to include in a vision request."""

    url: Optional[str] = None
    base64: Optional[str] = None
    detail: str = "auto"  # 'low', 'high', 'auto'


@dataclass(frozen=True, slots=True)
class VisionOptions:
    """Options for vision requests."""

    model: str
    max_tokens: Optional[int] = None


@dataclass(frozen=True, slots=True)
class VisionResponse:
    """Response from a vision request."""

    content: str
    model: str


class VisionCapable(ABC):
    """Contract for image understanding capability.

    Providers implementing this port can analyze images.
    """

    @property
    def capability(self) -> Capability:
        return Capability.VISION

    @abstractmethod
    async def vision(
        self,
        messages: Sequence[tuple[str, str]],  # (role, content with image refs)
        options: VisionOptions,
    ) -> VisionResponse:
        """Analyze images and return descriptions.

        Args:
            messages: Messages containing image references.
                Content may include image URLs or base64 data.
            options: Request options and model selection.

        Returns:
            VisionResponse with the model's analysis.

        Raises:
            LLMAuthenticationError: Invalid credentials.
            LLMRateLimitedError: Rate limit exceeded.
            LLMTimeoutError: Request timed out.
            LLMUnavailableError: Provider unavailable.
            LLMValidationError: Invalid request parameters.
        """
