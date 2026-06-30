from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


class LLMProviderError(Exception):
    """Raised for both configuration problems (no key set) and runtime failures
    (timeout, rate limit exhausted, API error) so callers can handle both without
    importing a specific provider's SDK exceptions."""


@dataclass
class LLMResponse:
    """Token counts are real, read from each provider's own response object — never
    estimated — so cost tracking downstream is computed from what the provider actually
    billed for, not guessed from text length."""

    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> LLMResponse:
        """Single non-streaming completion. Raises LLMProviderError on failure."""

    @abstractmethod
    async def stream(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> AsyncIterator[str]:
        """Yields text deltas as they arrive. Raises LLMProviderError on failure.
        Deliberately still plain text, not LLMResponse: usage totals for a streamed
        response only arrive in the final chunk (provider-specific extra step), and
        nothing in this codebase actually calls stream() yet — see meeting routes,
        which use complete(). Worth doing when something real consumes it."""
