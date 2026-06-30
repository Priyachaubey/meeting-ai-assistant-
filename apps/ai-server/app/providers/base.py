"""Abstract base classes for all AI provider interfaces.

These interfaces are provider-independent – concrete implementations
(OpenAI, Anthropic, Deepgram, Whisper, Ollama, vLLM, Gemini, etc.)
are registered at runtime via the ProviderManager.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


# ── LLM ────────────────────────────────────────────────────────────────


@dataclass
class LLMMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    raw: dict = field(default_factory=dict)


class LLMProvider(abc.ABC):
    """Abstract LLM provider interface."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abc.abstractmethod
    def model_name(self) -> str: ...

    @abc.abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse: ...

    @abc.abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]: ...

    async def health_check(self) -> bool:
        """Return True if the provider is reachable."""
        try:
            await self.chat([LLMMessage(role="user", content="ping")], max_tokens=1)
            return True
        except Exception:
            return False


# ── Embedding ──────────────────────────────────────────────────────────


@dataclass
class EmbeddingResponse:
    vectors: list[list[float]]
    model: str
    provider: str
    token_count: int = 0
    latency_ms: float = 0.0


class EmbeddingProvider(abc.ABC):
    """Abstract embedding provider interface."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abc.abstractmethod
    def model_name(self) -> str: ...

    @abc.abstractmethod
    async def embed(self, texts: list[str]) -> EmbeddingResponse: ...

    async def health_check(self) -> bool:
        try:
            await self.embed(["ping"])
            return True
        except Exception:
            return False


# ── Speech / STT ───────────────────────────────────────────────────────


@dataclass
class TranscriptionSegment:
    text: str
    start: float = 0.0
    end: float = 0.0
    speaker: str | None = None
    confidence: float = 1.0


@dataclass
class TranscriptionResponse:
    segments: list[TranscriptionSegment]
    provider: str
    model: str
    duration_seconds: float = 0.0
    latency_ms: float = 0.0
    raw: dict = field(default_factory=dict)


class SpeechProvider(abc.ABC):
    """Abstract speech-to-text provider interface."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abc.abstractmethod
    def model_name(self) -> str: ...

    @abc.abstractmethod
    async def transcribe(
        self, audio_bytes: bytes, *, language: str = "en"
    ) -> TranscriptionResponse: ...

    @abc.abstractmethod
    async def stream(
        self, audio_stream: AsyncIterator[bytes], *, language: str = "en"
    ) -> AsyncIterator[TranscriptionSegment]: ...

    async def health_check(self) -> bool:
        return True


# ── Translation ────────────────────────────────────────────────────────


@dataclass
class TranslationResponse:
    translated_text: str
    source_language: str
    target_language: str
    provider: str
    model: str
    latency_ms: float = 0.0


class TranslationProvider(abc.ABC):
    """Abstract translation provider interface."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abc.abstractmethod
    def model_name(self) -> str: ...

    @abc.abstractmethod
    async def translate(
        self,
        text: str,
        *,
        source_language: str = "auto",
        target_language: str = "en",
    ) -> TranslationResponse: ...

    async def health_check(self) -> bool:
        return True


# ── Vision ─────────────────────────────────────────────────────────────


@dataclass
class VisionResponse:
    description: str
    provider: str
    model: str
    labels: list[str] = field(default_factory=list)
    confidence: float = 0.0
    latency_ms: float = 0.0
    raw: dict = field(default_factory=dict)


class VisionProvider(abc.ABC):
    """Abstract vision/image-analysis provider interface."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abc.abstractmethod
    def model_name(self) -> str: ...

    @abc.abstractmethod
    async def analyze(
        self,
        image_bytes: bytes,
        *,
        prompt: str = "Describe this image in detail.",
        content_type: str = "image/png",
    ) -> VisionResponse: ...

    async def health_check(self) -> bool:
        return True


# ── OCR ────────────────────────────────────────────────────────────────


@dataclass
class OCRResponse:
    text: str
    provider: str
    model: str
    language: str = "en"
    confidence: float = 0.0
    latency_ms: float = 0.0
    blocks: list[dict] = field(default_factory=list)


class OCRProvider(abc.ABC):
    """Abstract OCR provider interface."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abc.abstractmethod
    def model_name(self) -> str: ...

    @abc.abstractmethod
    async def extract_text(
        self,
        image_bytes: bytes,
        *,
        language: str = "en",
        content_type: str = "image/png",
    ) -> OCRResponse: ...

    async def health_check(self) -> bool:
        return True


# ── TTS (Text-to-Speech) ──────────────────────────────────────────────


@dataclass
class TTSResponse:
    audio_bytes: bytes
    provider: str
    model: str
    content_type: str = "audio/wav"
    latency_ms: float = 0.0


class TTSProvider(abc.ABC):
    """Abstract text-to-speech provider interface."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abc.abstractmethod
    def model_name(self) -> str: ...

    @abc.abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice: str = "default",
        language: str = "en",
        speed: float = 1.0,
    ) -> TTSResponse: ...

    async def health_check(self) -> bool:
        return True
