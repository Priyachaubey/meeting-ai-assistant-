import asyncio
import time
from collections.abc import AsyncIterator

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from app.core.config import settings
from app.services.llm.base import LLMProvider, LLMProviderError, LLMResponse

RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise LLMProviderError("OPENAI_API_KEY is not set — configure it in .env before using this provider.")
        self._client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds)
        self._model = settings.openai_model

    async def _with_retry(self, fn, *args, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except RETRYABLE as exc:
                last_exc = exc
                if attempt == settings.llm_max_retries:
                    break
                # Exponential backoff with a small fixed floor; this is meeting-time-latency
                # sensitive code, so we don't back off for long even on the last retries.
                await asyncio.sleep(min(0.5 * (2**attempt), 4.0))
            except APIStatusError as exc:
                # 4xx other than 429 (bad request, auth, etc.) won't succeed on retry.
                raise LLMProviderError(f"OpenAI API error ({exc.status_code}): {exc.message}") from exc
        raise LLMProviderError(f"OpenAI request failed after {settings.llm_max_retries + 1} attempts: {last_exc}")

    async def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> LLMResponse:
        async def _call():
            start = time.monotonic()
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            latency_ms = (time.monotonic() - start) * 1000
            usage = response.usage
            return LLMResponse(
                text=response.choices[0].message.content or "",
                provider=self.name,
                model=self._model,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                latency_ms=latency_ms,
            )

        return await self._with_retry(_call)

    async def stream(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> AsyncIterator[str]:
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                stream=True,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except RETRYABLE as exc:
            # Streaming responses can't be cleanly retried mid-stream once partial
            # content has been sent to the client — surface the failure instead.
            raise LLMProviderError(f"OpenAI stream interrupted: {exc}") from exc
        except APIStatusError as exc:
            raise LLMProviderError(f"OpenAI API error ({exc.status_code}): {exc.message}") from exc
