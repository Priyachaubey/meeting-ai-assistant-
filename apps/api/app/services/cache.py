"""Redis has been configured (REDIS_URL) since the original scaffold but never actually used
for anything — no caching, no session storage (JWT is stateless by design), no rate-limit
backend. This is the first real use: embedding cache (services/rag/embedding_cache.py).

NOTE: written against redis-py's documented async API (redis.asyncio) from training knowledge
— not exercised against a live Redis instance (no network access in this sandbox). redis-py
has supported asyncio natively since v4.2; the pinned 6.2.0 is well past that, but verify the
basic get/set/expire call shape against the installed version before relying on this.
"""

from app.core.config import settings

_client = None


def get_redis_client():
    global _client
    if _client is None:
        import redis.asyncio as redis

        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client
