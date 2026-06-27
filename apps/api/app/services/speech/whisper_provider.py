from collections.abc import AsyncIterator

from app.services.speech.base import TranscriptionProvider, TranscriptionProviderError


class WhisperProvider(TranscriptionProvider):
    """Local/offline transcription via Whisper needs model weights downloaded, a real audio
    decode pipeline, and either a GPU or tolerance for CPU inference latency — none of which
    exist in this codebase yet. Raising clearly here is the honest choice: the previous version
    of this file silently `yield`ed the string "simulated whisper transcript chunk" forever,
    which looks like working transcription in logs/UI until someone actually reads the text.
    Implement for real with faster-whisper or openai-whisper once you decide whether this is
    needed (Deepgram already covers the realtime case; Whisper is mainly useful as a fallback
    when there's no network/API access, e.g. fully offline mode)."""

    name = "whisper-local"

    def __init__(self) -> None:
        raise TranscriptionProviderError(
            "WhisperProvider is not implemented yet (needs local model weights + decode "
            "pipeline). Use DeepgramProvider, or implement this before selecting it."
        )

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        raise TranscriptionProviderError("WhisperProvider is not implemented yet.")
        yield ""  # pragma: no cover - unreachable, keeps this an async generator
