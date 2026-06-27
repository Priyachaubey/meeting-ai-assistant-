import asyncio
import time

import pytest

from app.services.translation.base import StreamingTranslationProvider, TranslationProviderError
from app.services.translation.coordinator import LiveTranslationCoordinator


class FakeTranslationProvider(StreamingTranslationProvider):
    name = "fake"

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def translate(self, text: str, *, source_language: str | None, target_language: str) -> str:
        self.calls.append((text, target_language))
        await asyncio.sleep(0.05)  # simulate provider latency
        if target_language == "fail":
            raise TranslationProviderError("simulated failure")
        return f"[{target_language}] {text}"


@pytest.mark.asyncio
async def test_identical_target_languages_are_deduplicated():
    provider = FakeTranslationProvider()
    coordinator = LiveTranslationCoordinator(provider)

    await coordinator.add_utterance("Alice", "Hello everyone", 1000, target_languages={"es"})
    segments = await coordinator.flush_speaker("Alice", target_languages={"es", "fr", "es"})

    assert sorted(s.target_language for s in segments) == ["es", "fr"]
    assert len(provider.calls) == 2  # not 3 — duplicate "es" requests collapsed into one call


@pytest.mark.asyncio
async def test_multiple_languages_translate_concurrently():
    provider = FakeTranslationProvider()
    coordinator = LiveTranslationCoordinator(provider)
    coordinator._buffer.add("Bob", "Testing concurrency", 1000)

    start = time.monotonic()
    segments = await coordinator.flush_speaker("Bob", target_languages={"es", "fr", "de"})
    elapsed = time.monotonic() - start

    assert len(segments) == 3
    assert elapsed < 0.12  # ~0.05s if concurrent; sequential would be ~0.15s


@pytest.mark.asyncio
async def test_one_language_failing_does_not_break_the_others():
    provider = FakeTranslationProvider()
    coordinator = LiveTranslationCoordinator(provider)
    coordinator._buffer.add("Carol", "test", 1000)

    segments = await coordinator.flush_speaker("Carol", target_languages={"es", "fail"})

    assert len(segments) == 1
    assert segments[0].target_language == "es"
