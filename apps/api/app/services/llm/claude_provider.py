import asyncio
import time
from collections.abc import AsyncIterator

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    RateLimitError,
)

from app.core.config import settings
from app.services.llm.base import LLMProvider, LLMProviderError, LLMResponse

RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError)


class ClaudeProvider(LLMProvider):
    """Written against the documented Anthropic Python SDK shape from training knowledge —
    not exercised against a live API key (no network access in this sandbox). Verify the
    `anthropic` package version in requirements.txt actually exposes these exception names
    and the `messages.create(... system=..., messages=[...])` call shape before relying on
    this; the SDK has been stable on this shape for a long time, but "should be right" isn't
    "confirmed right" without actually running it."""

    name = "claude"

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY is not set — configure it in .env before using this provider.")
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=settings.llm_timeout_seconds)
        self._model = settings.anthropic_model

    async def _with_retry(self, fn, *args, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except RETRYABLE as exc:
                last_exc = exc
                if attempt == settings.llm_max_retries:
                    break
                await asyncio.sleep(min(0.5 * (2**attempt), 4.0))
            except APIStatusError as exc:
                raise LLMProviderError(f"Claude API error ({exc.status_code}): {exc.message}") from exc
        raise LLMProviderError(f"Claude request failed after {settings.llm_max_retries + 1} attempts: {last_exc}")

    async def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> LLMResponse:
        async def _call():
            start = time.monotonic()
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            latency_ms = (time.monotonic() - start) * 1000
            text = "".join(block.text for block in response.content if block.type == "text")
            # Anthropic's usage object uses input_tokens/output_tokens, NOT OpenAI's
            # prompt_tokens/completion_tokens — normalized here so callers never need to
            # know which provider answered.
            return LLMResponse(
                text=text,
                provider=self.name,
                model=self._model,
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
                latency_ms=latency_ms,
            )

        return await self._with_retry(_call)

    async def stream(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> AsyncIterator[str]:
        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except RETRYABLE as exc:
            raise LLMProviderError(f"Claude stream interrupted: {exc}") from exc
        except APIStatusError as exc:
            raise LLMProviderError(f"Claude API error ({exc.status_code}): {exc.message}") from exc
