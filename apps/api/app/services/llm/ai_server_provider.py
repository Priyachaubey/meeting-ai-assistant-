import time
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.security import create_access_token
from app.services.llm.base import LLMProvider, LLMProviderError, LLMResponse


class AIServerProvider(LLMProvider):
    """Calls the self-hosted apps/ai-server (Qwen2.5 by default, or whatever LLM_MODEL/
    AI_LLM_PROVIDER is configured there) over HTTP instead of a paid cloud API. Same
    LLMProvider interface as OpenAIProvider/ClaudeProvider, so it slots into the existing
    fallback chain in services/llm/__init__.py with no other code changes.

    Auth: ai-server's /chat endpoints require a bearer JWT (see its app/core/security.py —
    it has a create_internal_token() helper meant for exactly this). apps/api mints a
    short-lived token with its own create_access_token() instead of duplicating that logic —
    both services verify with the same JWT_SECRET/HS256, so a token minted here is accepted
    there with no changes needed on the ai-server side.

    Deliberately does NOT raise LLMProviderError just because the configured base URL is
    unset — unlike OpenAIProvider (which requires an API key), there's nothing to "configure
    wrong" here beyond a URL, and the real failure mode (ai-server not running/unreachable)
    is already surfaced as a connection error on first use, which the fallback chain's
    circuit breaker handles the same way it handles a cloud provider going down.
    """

    name = "ai-server"

    def __init__(self) -> None:
        self._base_url = settings.ai_server_url.rstrip("/")
        self._timeout = settings.llm_timeout_seconds

    def _auth_headers(self) -> dict[str, str]:
        # 5-minute token, minted fresh per request — these are short, frequent, server-to-
        # server calls, not something worth caching/refreshing logic for.
        token = create_access_token(subject="api-service", minutes=5)
        return {"Authorization": f"Bearer {token}"}

    async def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> LLMResponse:
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/api/ai/chat", json=payload, headers=self._auth_headers()
                )
        except httpx.RequestError as exc:
            raise LLMProviderError(f"ai-server unreachable at {self._base_url}: {exc}") from exc
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code != 200:
            raise LLMProviderError(f"ai-server returned {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMProviderError(f"ai-server returned a non-JSON response: {resp.text[:300]}") from exc

        return LLMResponse(
            text=data.get("content", ""),
            provider=self.name,
            model=data.get("model", "unknown"),
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            latency_ms=data.get("latency_ms", latency_ms),
        )

    async def stream(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 400) -> AsyncIterator[str]:
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST", f"{self._base_url}/api/ai/chat/stream", json=payload, headers=self._auth_headers()
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise LLMProviderError(f"ai-server returned {resp.status_code}: {body[:300]!r}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        chunk = line[len("data: ") :]
                        if chunk == "[DONE]":
                            return
                        yield chunk
        except httpx.RequestError as exc:
            raise LLMProviderError(f"ai-server unreachable at {self._base_url}: {exc}") from exc
