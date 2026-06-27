import logging
import time
from collections.abc import AsyncIterator

from app.services.llm.base import LLMProvider, LLMProviderError, LLMResponse

logger = logging.getLogger("convopilot.llm.router")

# Circuit breaker: after this many consecutive failures, a provider is skipped for
# CIRCUIT_RESET_SECONDS rather than retried on every single request. This is a real,
# locally-testable mechanism (see tests/test_fallback_provider.py) — it just has nothing
# to tune against yet, since "how many failures is too many" is a judgment call that
# should eventually be informed by real failure-rate data via the AI usage analytics
# (app/services/usage.py), not invented now.
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_RESET_SECONDS = 60.0


class FallbackLLMProvider(LLMProvider):
    """Tries each provider in order, falling through to the next on LLMProviderError.
    Deliberately just sequential fallback + a circuit breaker, not load balancing or
    cost/latency-based routing — those need real usage data to tune against, which doesn't
    exist yet. Sequential fallback with a circuit breaker is the part that's actually
    buildable and verifiable today without that data."""

    name = "fallback"

    def __init__(
        self,
        providers: list[LLMProvider],
        *,
        circuit_failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
        circuit_reset_seconds: float = CIRCUIT_RESET_SECONDS,
    ) -> None:
        if not providers:
            raise LLMProviderError("FallbackLLMProvider needs at least one configured provider.")
        self._providers = providers
        self._failure_threshold = circuit_failure_threshold
        self._reset_seconds = circuit_reset_seconds
        self._consecutive_failures: dict[str, int] = {p.name: 0 for p in providers}
        self._tripped_until: dict[str, float] = {p.name: 0.0 for p in providers}

    def _is_open(self, provider: LLMProvider) -> bool:
        """True if the circuit is open (provider should be skipped) right now."""
        return time.monotonic() < self._tripped_until[provider.name]

    def _record_success(self, provider: LLMProvider) -> None:
        self._consecutive_failures[provider.name] = 0

    def _record_failure(self, provider: LLMProvider) -> None:
        self._consecutive_failures[provider.name] += 1
        if self._consecutive_failures[provider.name] >= self._failure_threshold:
            self._tripped_until[provider.name] = time.monotonic() + self._reset_seconds
            logger.warning(
                "Circuit breaker tripped for provider %s after %d consecutive failures — "
                "skipping it for %.0fs",
                provider.name,
                self._consecutive_failures[provider.name],
                self._reset_seconds,
            )

    def _candidates(self) -> list[LLMProvider]:
        open_providers = [p for p in self._providers if not self._is_open(p)]
        # If every provider's circuit is open, try them all anyway — better to fail with a
        # real attempt than to refuse outright just because of past failures.
        return open_providers or self._providers

    async def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> LLMResponse:
        errors: list[str] = []
        for provider in self._candidates():
            try:
                response = await provider.complete(system_prompt, user_prompt, max_tokens=max_tokens)
                self._record_success(provider)
                return response
            except LLMProviderError as exc:
                self._record_failure(provider)
                logger.warning("Provider %s failed, trying next: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
        raise LLMProviderError(f"All providers failed — {'; '.join(errors)}")

    async def stream(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> AsyncIterator[str]:
        errors: list[str] = []
        for provider in self._candidates():
            started = False
            try:
                async for chunk in provider.stream(system_prompt, user_prompt, max_tokens=max_tokens):
                    started = True
                    yield chunk
                self._record_success(provider)
                return
            except LLMProviderError as exc:
                if started:
                    raise
                self._record_failure(provider)
                logger.warning("Provider %s failed before streaming started, trying next: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
        raise LLMProviderError(f"All providers failed — {'; '.join(errors)}")
