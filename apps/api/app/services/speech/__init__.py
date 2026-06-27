import logging

from app.core.config import settings
from app.services.speech.assemblyai_provider import AssemblyAIProvider
from app.services.speech.base import TranscriptionProvider, TranscriptionProviderError
from app.services.speech.deepgram_provider import DeepgramProvider
from app.services.speech.fallback_provider import FallbackTranscriptionProvider

logger = logging.getLogger("convopilot.speech")

_provider_instance: TranscriptionProvider | None = None

_PROVIDER_BUILDERS = {"deepgram": DeepgramProvider, "assemblyai": AssemblyAIProvider}


def get_speech_provider() -> TranscriptionProvider:
    """Builds a fallback chain from whichever speech providers actually have an API key
    configured, preferred provider first — same pattern as get_llm_provider(). Whisper isn't
    here: it needs local model weights and a real decode pipeline neither of which exist (see
    services/speech/whisper_provider.py's docstring), so it's not a real provider to include
    in a fallback chain yet."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    order = [settings.speech_provider] + [name for name in _PROVIDER_BUILDERS if name != settings.speech_provider]
    available: list[TranscriptionProvider] = []
    for name in order:
        builder = _PROVIDER_BUILDERS.get(name)
        if not builder:
            continue
        try:
            available.append(builder())
        except TranscriptionProviderError as exc:
            logger.info("Speech provider %s not available: %s", name, exc)

    if not available:
        raise TranscriptionProviderError(
            "No speech provider is configured — set DEEPGRAM_API_KEY and/or ASSEMBLYAI_API_KEY in .env."
        )

    _provider_instance = available[0] if len(available) == 1 else FallbackTranscriptionProvider(available)
    return _provider_instance


__all__ = ["TranscriptionProvider", "TranscriptionProviderError", "get_speech_provider"]
