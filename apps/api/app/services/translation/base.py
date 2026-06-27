from abc import ABC, abstractmethod
from dataclasses import dataclass


class TranslationProviderError(Exception):
    """Configuration or runtime failure — same error-visibility principle as every other
    provider in this codebase: a failed translation should be a visible error to whoever's
    waiting on it, not a silently-empty or silently-original-language subtitle."""


@dataclass
class TranslatedSegment:
    speaker: str
    source_text: str
    translated_text: str
    source_language: str | None
    target_language: str
    start_timestamp_ms: int
    end_timestamp_ms: int


class StreamingTranslationProvider(ABC):
    """Contract for a real-time translation backend. Implement this once for whichever
    specialized MT system is actually adopted (self-hosted NLLB-200/SeamlessM4T, or a paid
    Google/Azure/DeepL streaming account) and nothing in app/services/translation/coordinator.py
    needs to change — same pattern as LLMProvider/TranscriptionProvider elsewhere in this
    codebase. See TRANSLATION_ARCHITECTURE.md for why no such implementation exists yet."""

    name: str

    @abstractmethod
    async def translate(self, text: str, *, source_language: str | None, target_language: str) -> str:
        """Raises TranslationProviderError on failure."""
