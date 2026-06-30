import logging

from app.core.config import settings
from app.services.llm.ai_server_provider import AIServerProvider
from app.services.llm.base import LLMProvider, LLMProviderError
from app.services.llm.claude_provider import ClaudeProvider
from app.services.llm.fallback_provider import FallbackLLMProvider
from app.services.llm.openai_provider import OpenAIProvider

logger = logging.getLogger("convopilot.llm")

_provider_instance: LLMProvider | None = None

# Order matters: settings.llm_provider names the preferred provider, tried first.
# "ai-server" added in the self-hosted-models merge — see ai_server_provider.py. It has no
# required config (just a URL, which always has a default), so it's always "available" in
# the sense get_llm_provider() checks below; if it's actually unreachable that surfaces as a
# connection error on first real call, same as any other provider going down, and the
# fallback chain's circuit breaker (see fallback_provider.py) routes around it from there.
_PROVIDER_BUILDERS = {"ai-server": AIServerProvider, "openai": OpenAIProvider, "claude": ClaudeProvider}


def get_llm_provider() -> LLMProvider:
    """Builds a fallback chain from whichever providers are actually usable — ai-server
    always counts (it just needs a reachable URL, no API key), openai/claude only count if
    their API key is set — preferred provider first. Gemini isn't wired yet — same pattern as
    Claude when it is: one new file implementing LLMProvider, one entry in
    _PROVIDER_BUILDERS, no other code changes anywhere else in the app."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    order = [settings.llm_provider] + [name for name in _PROVIDER_BUILDERS if name != settings.llm_provider]
    available: list[LLMProvider] = []
    for name in order:
        builder = _PROVIDER_BUILDERS.get(name)
        if not builder:
            continue
        try:
            available.append(builder())
        except LLMProviderError as exc:
            logger.info("LLM provider %s not available: %s", name, exc)

    if not available:
        raise LLMProviderError(
            "No LLM provider is configured — this shouldn't happen since ai-server has no "
            "required config, but if it's somehow missing: set OPENAI_API_KEY and/or "
            "ANTHROPIC_API_KEY in .env as a fallback."
        )

    _provider_instance = available[0] if len(available) == 1 else FallbackLLMProvider(available)
    return _provider_instance


__all__ = ["LLMProvider", "LLMProviderError", "get_llm_provider"]
