import asyncio

import pytest

from app.services.llm.base import LLMProvider, LLMProviderError, LLMResponse
from app.services.llm.fallback_provider import FallbackLLMProvider


class FakeProvider(LLMProvider):
    """Always fails or always succeeds, on demand — no network, no API key."""

    def __init__(self, name: str, *, fails: bool = False):
        self.name = name
        self.fails = fails
        self.call_count = 0

    async def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> LLMResponse:
        self.call_count += 1
        if self.fails:
            raise LLMProviderError(f"{self.name} is configured to fail")
        return LLMResponse(
            text=f"response from {self.name}",
            provider=self.name,
            model="fake-model",
            prompt_tokens=10,
            completion_tokens=5,
            latency_ms=1.0,
        )

    async def stream(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400):
        if self.fails:
            raise LLMProviderError(f"{self.name} is configured to fail")
        yield f"stream from {self.name}"


@pytest.mark.asyncio
async def test_falls_back_to_second_provider_on_failure():
    primary = FakeProvider("primary", fails=True)
    backup = FakeProvider("backup", fails=False)
    router = FallbackLLMProvider([primary, backup])

    response = await router.complete("system", "user")

    assert response.provider == "backup"
    assert primary.call_count == 1
    assert backup.call_count == 1


@pytest.mark.asyncio
async def test_raises_when_all_providers_fail():
    router = FallbackLLMProvider([FakeProvider("a", fails=True), FakeProvider("b", fails=True)])
    with pytest.raises(LLMProviderError, match="All providers failed"):
        await router.complete("system", "user")


@pytest.mark.asyncio
async def test_circuit_breaker_skips_provider_after_threshold():
    primary = FakeProvider("primary", fails=True)
    backup = FakeProvider("backup", fails=False)
    # Low threshold and a reset window long enough that it won't flip mid-test.
    router = FallbackLLMProvider([primary, backup], circuit_failure_threshold=2, circuit_reset_seconds=30.0)

    await router.complete("system", "user")  # primary fails (1), backup succeeds
    await router.complete("system", "user")  # primary fails (2) -> circuit trips
    primary_calls_before = primary.call_count

    await router.complete("system", "user")  # circuit should be open now: primary skipped entirely
    assert primary.call_count == primary_calls_before  # not called again while circuit is open
    assert backup.call_count == 3


@pytest.mark.asyncio
async def test_circuit_resets_after_window_elapses():
    primary = FakeProvider("primary", fails=True)
    backup = FakeProvider("backup", fails=False)
    router = FallbackLLMProvider([primary, backup], circuit_failure_threshold=1, circuit_reset_seconds=0.05)

    await router.complete("system", "user")  # primary fails once -> circuit trips immediately
    assert primary.call_count == 1

    await asyncio.sleep(0.08)  # wait past the reset window

    await router.complete("system", "user")  # circuit closed again -> primary gets tried
    assert primary.call_count == 2
