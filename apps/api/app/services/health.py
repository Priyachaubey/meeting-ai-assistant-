"""Real health checks. The plain GET /health in main.py stays fast and dependency-free
(no DB/Qdrant calls) since that's what a load balancer pings constantly — making it slow or
flaky because Qdrant is having a bad day would cascade into the LB thinking the whole API is
down. This module backs a separate, authenticated /health/detailed for actually diagnosing
"why isn't X working" — it makes real connections, so it's slower and shouldn't be polled
every few seconds."""

import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


def check_database(db: Session) -> dict:
    start = time.monotonic()
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True, "latency_ms": round((time.monotonic() - start) * 1000, 1)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_qdrant() -> dict:
    start = time.monotonic()
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=settings.qdrant_url, timeout=3)
        collections = client.get_collections().collections
        return {"ok": True, "latency_ms": round((time.monotonic() - start) * 1000, 1), "collections": len(collections)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": settings.qdrant_url}


def configured_providers() -> dict:
    """Booleans only — never the actual key values, even partially."""
    return {
        "openai": bool(settings.openai_api_key),
        "anthropic": bool(settings.anthropic_api_key),
        "deepgram": bool(settings.deepgram_api_key),
        "stripe": bool(settings.stripe_secret_key),
    }


def get_detailed_health(db: Session) -> dict:
    return {
        "app_env": settings.app_env,
        "database": check_database(db),
        "qdrant": check_qdrant(),
        "providers_configured": configured_providers(),
    }
