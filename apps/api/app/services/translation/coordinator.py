import asyncio
import logging

from app.services.translation.base import StreamingTranslationProvider, TranslatedSegment, TranslationProviderError
from app.services.translation.buffer import BufferedUtterance, UtteranceBuffer

logger = logging.getLogger("convopilot.translation")


class LiveTranslationCoordinator:
    """Ties the buffering strategy to a translation provider and fans a single buffered
    utterance out to every distinct target language requested across all participants —
    deduplicated, so 5 participants who all chose Spanish cost one translation call, not five,
    and run concurrently (asyncio.gather) so requesting 4 different languages doesn't take 4x
    as long as requesting 1."""

    def __init__(self, provider: StreamingTranslationProvider, *, max_gap_ms: int = 1500, max_chars: int = 280) -> None:
        self._provider = provider
        self._buffer = UtteranceBuffer(max_gap_ms=max_gap_ms, max_chars=max_chars)

    async def add_utterance(
        self, speaker: str, text: str, timestamp_ms: int, *, target_languages: set[str]
    ) -> list[TranslatedSegment]:
        """Feed one finalized transcript utterance in. Returns [] most of the time (the
        utterance merged into an open buffer) — only returns translated segments when a flush
        actually happens, which is when callers should push subtitles to participants."""
        ready = self._buffer.add(speaker, text, timestamp_ms)
        if ready is None:
            return []
        return await self._translate_buffered(ready, target_languages)

    async def flush_speaker(self, speaker: str, *, target_languages: set[str]) -> list[TranslatedSegment]:
        """Call when a speaker stops talking for a while (e.g. another speaker starts) or the
        session ends, so their last few words don't sit untranslated forever."""
        ready = self._buffer.flush(speaker)
        if ready is None:
            return []
        return await self._translate_buffered(ready, target_languages)

    async def flush_all(self, *, target_languages: set[str]) -> list[TranslatedSegment]:
        results: list[TranslatedSegment] = []
        for utterance in self._buffer.flush_all():
            results.extend(await self._translate_buffered(utterance, target_languages))
        return results

    async def _translate_buffered(
        self, utterance: BufferedUtterance, target_languages: set[str]
    ) -> list[TranslatedSegment]:
        async def _one(lang: str) -> TranslatedSegment | None:
            try:
                translated = await self._provider.translate(utterance.text, source_language=None, target_language=lang)
            except TranslationProviderError as exc:
                logger.warning("Translation to %s failed for speaker %s: %s", lang, utterance.speaker, exc)
                return None
            return TranslatedSegment(
                speaker=utterance.speaker,
                source_text=utterance.text,
                translated_text=translated,
                source_language=None,
                target_language=lang,
                start_timestamp_ms=utterance.start_timestamp_ms,
                end_timestamp_ms=utterance.end_timestamp_ms,
            )

        results = await asyncio.gather(*(_one(lang) for lang in target_languages))
        return [r for r in results if r is not None]
