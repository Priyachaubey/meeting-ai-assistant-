import logging
from collections.abc import AsyncIterator

from app.services.speech.base import TranscriptionProvider, TranscriptionProviderError

logger = logging.getLogger("convopilot.speech.router")


class _TrackingAsyncIterator:
    """Wraps the real audio iterator to detect whether ANY item was ever pulled from it —
    not whether any transcript was yielded out, which is what FallbackLLMProvider tracks for
    its (replayable) text prompts. Audio is fundamentally different: once a chunk is pulled
    out of the shared queue-backed iterator (see routes/ws.py) to send to a provider, it's
    gone — there's no "try the same audio again" the way there is with a static string
    prompt. This is what makes speech-provider fallback a harder problem than LLM fallback,
    not just a smaller version of the same thing."""

    def __init__(self, source: AsyncIterator[bytes]) -> None:
        self._source = source
        self.any_consumed = False

    def __aiter__(self) -> "_TrackingAsyncIterator":
        return self

    async def __anext__(self) -> bytes:
        item = await self._source.__anext__()
        self.any_consumed = True
        return item


class FallbackTranscriptionProvider(TranscriptionProvider):
    """Falls back to the next provider ONLY if the current one fails before consuming any
    audio at all (e.g. connection refused, bad API key, DNS failure — the realistic common
    case). If a provider fails after already pulling audio out of the shared iterator, that
    audio cannot be safely replayed to a fallback — silently attempting to would mean
    transcribing a different (truncated) audio stream than what was actually spoken and
    presenting it as complete, which is worse than a visible failure. Surfaces an error
    instead in that case, rather than pretending a clean fallback happened."""

    name = "fallback"

    def __init__(self, providers: list[TranscriptionProvider]) -> None:
        if not providers:
            raise TranscriptionProviderError("FallbackTranscriptionProvider needs at least one configured provider.")
        self._providers = providers

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        wrapped = _TrackingAsyncIterator(audio)
        errors: list[str] = []
        for provider in self._providers:
            if wrapped.any_consumed:
                raise TranscriptionProviderError(
                    f"{provider.name} unavailable, but a previous provider already consumed "
                    f"audio from this stream — cannot safely fall back mid-stream. "
                    f"Errors so far: {'; '.join(errors)}"
                )
            try:
                async for text in provider.stream(wrapped):
                    yield text
                return
            except TranscriptionProviderError as exc:
                logger.warning("Speech provider %s failed, trying next: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
        raise TranscriptionProviderError(f"All speech providers failed — {'; '.join(errors)}")
