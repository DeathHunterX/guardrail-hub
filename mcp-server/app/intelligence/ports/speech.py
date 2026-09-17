"""Speech capability port — audio transcription and synthesis."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.intelligence.registry.types.capability import Capability


@dataclass(frozen=True, slots=True)
class TranscriptionOptions:
    """Options for speech transcription."""

    model: str
    language: Optional[str] = None
    prompt: Optional[str] = None
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class TranscriptionResponse:
    """Response from a transcription request."""

    text: str
    language: Optional[str] = None
    duration: Optional[float] = None


@dataclass(frozen=True, slots=True)
class SynthesisOptions:
    """Options for speech synthesis."""

    model: str
    voice: str = "alloy"
    speed: float = 1.0


@dataclass(frozen=True, slots=True)
class SynthesisResponse:
    """Response from a speech synthesis request."""

    audio: bytes
    format: str = "mp3"  # 'mp3', 'opus', 'aac', 'flac'


class SpeechCapable(ABC):
    """Contract for speech transcription and synthesis capability.

    Providers implementing this port can transcribe audio and synthesize speech.
    """

    @property
    def capability(self) -> Capability:
        return Capability.SPEECH

    @abstractmethod
    async def transcribe(
        self,
        audio: bytes,
        options: TranscriptionOptions,
    ) -> TranscriptionResponse:
        """Transcribe audio to text.

        Args:
            audio: Raw audio bytes.
            options: Request options and model selection.

        Returns:
            TranscriptionResponse with transcribed text.

        Raises:
            LLMAuthenticationError: Invalid credentials.
            LLMRateLimitedError: Rate limit exceeded.
            LLMTimeoutError: Request timed out.
            LLMUnavailableError: Provider unavailable.
            LLMValidationError: Invalid request parameters.
        """

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        options: SynthesisOptions,
    ) -> SynthesisResponse:
        """Synthesize speech from text.

        Args:
            text: Text to synthesize.
            options: Request options and voice selection.

        Returns:
            SynthesisResponse with audio bytes.

        Raises:
            LLMAuthenticationError: Invalid credentials.
            LLMRateLimitedError: Rate limit exceeded.
            LLMTimeoutError: Request timed out.
            LLMUnavailableError: Provider unavailable.
            LLMValidationError: Invalid request parameters.
        """
