"""Provider Manager – registry and lifecycle for all AI providers.

Providers are registered at startup based on configuration. The manager
exposes a uniform interface for selecting the active provider for each
capability (LLM, embedding, speech, translation, vision, OCR, TTS).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.config import settings
from app.providers.base import (
    EmbeddingProvider,
    LLMProvider,
    OCRProvider,
    SpeechProvider,
    TTSProvider,
    TranslationProvider,
    VisionProvider,
)

logger = structlog.get_logger()


class ProviderManager:
    """Central registry for all AI provider instances."""

    def __init__(self) -> None:
        self._llm: LLMProvider | None = None
        self._embedding: EmbeddingProvider | None = None
        self._speech: SpeechProvider | None = None
        self._translation: TranslationProvider | None = None
        self._vision: VisionProvider | None = None
        self._ocr: OCRProvider | None = None
        self._tts: TTSProvider | None = None
        self._registry: dict[str, Any] = {}

    # ── Registration ──────────────────────────────────────────────────

    def register_llm(self, provider: LLMProvider) -> None:
        self._llm = provider
        self._registry["llm"] = provider
        logger.info(
            "llm_provider_registered",
            provider=provider.provider_name,
            model=provider.model_name,
        )

    def register_embedding(self, provider: EmbeddingProvider) -> None:
        self._embedding = provider
        self._registry["embedding"] = provider
        logger.info("embedding_provider_registered", provider=provider.provider_name)

    def register_speech(self, provider: SpeechProvider) -> None:
        self._speech = provider
        self._registry["speech"] = provider
        logger.info("speech_provider_registered", provider=provider.provider_name)

    def register_translation(self, provider: TranslationProvider) -> None:
        self._translation = provider
        self._registry["translation"] = provider
        logger.info("translation_provider_registered", provider=provider.provider_name)

    def register_vision(self, provider: VisionProvider) -> None:
        self._vision = provider
        self._registry["vision"] = provider
        logger.info("vision_provider_registered", provider=provider.provider_name)

    def register_ocr(self, provider: OCRProvider) -> None:
        self._ocr = provider
        self._registry["ocr"] = provider
        logger.info("ocr_provider_registered", provider=provider.provider_name)

    def register_tts(self, provider: TTSProvider) -> None:
        self._tts = provider
        self._registry["tts"] = provider
        logger.info("tts_provider_registered", provider=provider.provider_name)

    # ── Accessors ─────────────────────────────────────────────────────

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            raise RuntimeError("No LLM provider configured")
        return self._llm

    @property
    def embedding(self) -> EmbeddingProvider:
        if self._embedding is None:
            raise RuntimeError("No embedding provider configured")
        return self._embedding

    @property
    def speech(self) -> SpeechProvider:
        if self._speech is None:
            raise RuntimeError("No speech provider configured")
        return self._speech

    @property
    def translation(self) -> TranslationProvider:
        if self._translation is None:
            raise RuntimeError("No translation provider configured")
        return self._translation

    @property
    def vision(self) -> VisionProvider:
        if self._vision is None:
            raise RuntimeError("No vision provider configured")
        return self._vision

    @property
    def ocr(self) -> OCRProvider:
        if self._ocr is None:
            raise RuntimeError("No OCR provider configured")
        return self._ocr

    @property
    def tts(self) -> TTSProvider:
        if self._tts is None:
            raise RuntimeError("No TTS provider configured")
        return self._tts

    # ── Introspection ─────────────────────────────────────────────────

    def get_status(self) -> dict[str, dict[str, str | None]]:
        """Return the status of all registered providers."""
        status: dict[str, dict[str, str | None]] = {}
        for capability, provider in self._registry.items():
            status[capability] = {
                "provider": provider.provider_name,
                "model": provider.model_name,
                "status": "configured",
            }
        # Mark unconfigured capabilities
        for cap in (
            "llm",
            "embedding",
            "speech",
            "translation",
            "vision",
            "ocr",
            "tts",
        ):
            if cap not in status:
                status[cap] = {
                    "provider": None,
                    "model": None,
                    "status": "not_configured",
                }
        return status

    async def health_check_all(self) -> dict[str, bool]:
        """Run health checks on all configured providers."""
        results: dict[str, bool] = {}
        for capability, provider in self._registry.items():
            try:
                results[capability] = await provider.health_check()
            except Exception:
                results[capability] = False
        return results


# Singleton
provider_manager = ProviderManager()
