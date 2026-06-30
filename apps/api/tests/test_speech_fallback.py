import pytest

from app.services.speech.base import TranscriptionProvider, TranscriptionProviderError
from app.services.speech.fallback_provider import FallbackTranscriptionProvider


async def fake_audio(n: int = 5):
    for i in range(n):
        yield f"chunk{i}".encode()


class FailsImmediately(TranscriptionProvider):
    name = "fails_immediately"

    async def stream(self, audio):
        raise TranscriptionProviderError("connection refused")
        yield ""  # pragma: no cover - unreachable, keeps this an async generator


class WorksFine(TranscriptionProvider):
    name = "works_fine"

    async def stream(self, audio):
        async for chunk in audio:
            yield f"transcribed:{chunk.decode()}"


class FailsAfterConsuming(TranscriptionProvider):
    name = "fails_after_consuming"

    async def stream(self, audio):
        async for _chunk in audio:
            raise TranscriptionProviderError("connection dropped mid-stream")
        yield ""  # pragma: no cover


@pytest.mark.asyncio
async def test_falls_back_when_primary_fails_before_consuming_audio():
    router = FallbackTranscriptionProvider([FailsImmediately(), WorksFine()])
    results = [t async for t in router.stream(fake_audio())]
    assert results == [f"transcribed:chunk{i}" for i in range(5)]


@pytest.mark.asyncio
async def test_does_not_fall_back_once_audio_has_already_been_consumed():
    router = FallbackTranscriptionProvider([FailsAfterConsuming(), WorksFine()])
    with pytest.raises(TranscriptionProviderError, match="cannot safely fall back mid-stream"):
        async for _ in router.stream(fake_audio()):
            pass


@pytest.mark.asyncio
async def test_raises_when_every_provider_fails():
    router = FallbackTranscriptionProvider([FailsImmediately(), FailsImmediately()])
    with pytest.raises(TranscriptionProviderError, match="All speech providers failed"):
        async for _ in router.stream(fake_audio()):
            pass
