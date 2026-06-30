"""Wires translation_pipeline's injection point to apps/ai-server's real /translate endpoint.

translation_pipeline.py was fully built — per-user language preferences, caching, room-level
language tracking, the translate_transcript orchestration — but its actual call out to a real
translation provider was left as a `set_translate_fn()` injection point that nothing in the
codebase ever called. Every real translation request was silently raising RuntimeError
("Translation function not configured") the entire time. This module is that missing call.
"""

from __future__ import annotations

import time

import httpx
import structlog

from app.core.config import settings
from app.services.service_auth import mint_ai_server_token

logger = structlog.get_logger()


async def translate_via_ai_server(text: str, source_lang: str, target_lang: str) -> str:
    """Calls apps/ai-server's /api/ai/translate (NLLB-200 by default — see ai-server's own
    config for which model is actually loaded). Raises on failure rather than silently
    returning the original text — translation_pipeline.translate_text() already has its own
    cache-or-raise contract; swallowing a real failure here would mean a participant sees
    English captions and has no idea their selected language silently failed.
    """
    token = mint_ai_server_token()
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.ai_server_url.rstrip('/')}/api/ai/translate",
                json={"text": text, "source_language": source_lang, "target_language": target_lang},
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as exc:
        logger.error("translation_request_failed", error=str(exc), target_lang=target_lang)
        raise RuntimeError(f"ai-server unreachable for translation: {exc}") from exc

    if resp.status_code != 200:
        logger.error("translation_bad_status", status=resp.status_code, body=resp.text[:300])
        raise RuntimeError(f"ai-server /translate returned {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
        translated = data["translated_text"]
    except (ValueError, KeyError) as exc:
        raise RuntimeError(f"ai-server /translate returned unexpected shape: {exc}") from exc

    logger.info(
        "translation_completed",
        target_lang=target_lang,
        latency_ms=round((time.monotonic() - start) * 1000, 1),
    )
    return translated
