import hashlib
import json
import logging

from app.services.cache import get_redis_client

logger = logging.getLogger("convopilot.rag.embedding_cache")

# Embeddings are deterministic for a given (model, text) pair — re-uploading the same
# document, or re-running the same search query, costs nothing the second time. 30 days, not
# forever: unbounded cache growth for content that might never be looked up again isn't free
# either, and nothing here claims embeddings would ever meaningfully change for stable text,
# so this is just a "don't keep paying for stale chunks of a deleted document" backstop.
DEFAULT_TTL_SECONDS = 30 * 24 * 3600


def _cache_key(model: str, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embedding:{model}:{digest}"


async def get_cached_embedding(model: str, text: str) -> list[float] | None:
    """Returns None on a cache miss OR on any Redis failure — a cache that can't be reached
    must degrade to "just call the real embeddings API," never raise and break ingestion/
    search. Logged at debug level, not warning: an unreachable cache is routine/expected if
    Redis isn't running in a given environment, not an error worth alarming about."""
    try:
        client = get_redis_client()
        raw = await client.get(_cache_key(model, text))
    except Exception as exc:
        logger.debug("Embedding cache unavailable (falling back to a real embedding call): %s", exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None  # corrupt cache entry — treat as a miss, don't propagate a parse error


async def store_embedding(model: str, text: str, embedding: list[float], *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """Best-effort — a failed cache write must never fail the caller's actual embedding
    request, which already succeeded by the time this is called."""
    try:
        client = get_redis_client()
        await client.set(_cache_key(model, text), json.dumps(embedding), ex=ttl_seconds)
    except Exception as exc:
        logger.debug("Could not write to embedding cache: %s", exc)
