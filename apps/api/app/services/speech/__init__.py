import logging

from app.core.config import settings
from app.services.speech.ai_server_provider import AIServerSpeechProvider
from app.services.speech.assemblyai_provider import AssemblyAIProvider
from app.services.speech.base import TranscriptionProvider, TranscriptionProviderError
from app.services.speech.deepgram_provider import DeepgramProvider
from app.services.speech.fallback_provider import FallbackTranscriptionProvider

logger = logging.getLogger("convopilot.speech")

_provider_instance: TranscriptionProvider | None = None

# "ai-server" added in the self-hosted-models merge — see ai_server_provider.py. Like
# AIServerProvider on the LLM side, it has no required config (just a URL with a default),
# so it always counts as "available" below; an unreachable ai-server surfaces as a
# TranscriptionProviderError on first real use and the fallback chain routes around it.
_PROVIDER_BUILDERS = {"ai-server": AIServerSpeechProvider, "deepgram": DeepgramProvider, "assemblyai": AssemblyAIProvider}


def get_speech_provider() -> TranscriptionProvider:
    """Builds a fallback chain from whichever speech providers are actually usable —
    ai-server always counts (no API key needed, just a reachable URL), deepgram/assemblyai
    only count if their API key is set — preferred provider first, same pattern as
    get_llm_provider(). Note this `ai-server` provider (ai_server_provider.py, added in the
    self-hosted-models merge) is unrelated to the still-unimplemented whisper_provider.py in
    this same directory — that file calls local faster-whisper in-process, which still isn't
    wired up; this one calls out to the separate apps/ai-server service over HTTP, which is."""
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
            "No speech provider is configured — this shouldn't happen since ai-server has no "
            "required config, but if it's somehow missing: set DEEPGRAM_API_KEY and/or "
            "ASSEMBLYAI_API_KEY in .env as a fallback."
        )

    _provider_instance = available[0] if len(available) == 1 else FallbackTranscriptionProvider(available)
    return _provider_instance


__all__ = ["TranscriptionProvider", "TranscriptionProviderError", "get_speech_provider"]
