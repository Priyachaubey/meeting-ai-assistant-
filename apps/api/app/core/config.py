from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# __file__ = apps/api/app/core/config.py
_API_DIR = Path(__file__).resolve().parents[2]  # apps/api
_REPO_ROOT = Path(__file__).resolve().parents[4]  # repo root

# Checks both locations so this works whether you run uvicorn from the repo root or from
# apps/api (README's Quick Start does the latter) and whether .env lives at the repo root
# (next to .env.example) or inside apps/api. If both exist, apps/api/.env wins.


class Settings(BaseSettings):
    app_env: str = "development"
    web_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    database_url: str = "sqlite:///./convopilot.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    jwt_secret: str = "change-me-with-32-byte-secret"  # matches ai-server's/meeting-server's default — see their config.py
    encryption_key: str | None = None

    # LLM (ai-server tried first as of the self-hosted-models merge; openai/claude are the
    # automatic fallback if it's unreachable — same fallback-chain mechanism as before, see
    # app/services/llm/__init__.py. Gemini key accepted so .env doesn't need to change when
    # it's wired — same pattern as Claude when it was added.)
    llm_provider: str = "ai-server"  # which provider to try first; the rest become the fallback chain
    ai_server_url: str = "http://localhost:8001"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    gemini_api_key: str | None = None
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 2

    # Speech (ai-server tried first, same reasoning as llm_provider above; deepgram/
    # assemblyai are the fallback — see app/services/speech)
    speech_provider: str = "ai-server"  # which to try first; the rest become the fallback chain
    deepgram_api_key: str | None = None
    deepgram_model: str = "nova-2"
    assemblyai_api_key: str | None = None
    audio_sample_rate_hz: int = 16000

    # Embedding provider for RAG / knowledge base.
    # "ai-server" calls apps/ai-server's /api/ai/embed (sentence-transformers, 384-dim).
    # "openai" calls OpenAI's text-embedding-3-small (1536-dim, requires OPENAI_API_KEY).
    # IMPORTANT: all Qdrant collections created under one provider setting are incompatible
    # with the other — vector size is encoded at collection-creation time. On a fresh
    # deployment (no existing Qdrant collections) you can switch freely; with existing data
    # you must delete the old collections and re-ingest after switching. The dimension is
    # derived automatically from this setting (see rag/pipeline.py).
    embedding_provider: str = "ai-server"

    # Billing — Stripe
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id_pro: str | None = None

    sentry_dsn: str | None = None

    # Storage — local filesystem by default (zero credentials, works out of the box for dev
    # and single-instance deployments); s3 covers AWS S3/Cloudflare R2/MinIO via the same API.
    storage_provider: str = "local"
    storage_local_dir: str = "./storage"
    storage_s3_bucket: str | None = None
    storage_s3_endpoint_url: str | None = None  # set for R2/MinIO, leave unset for real AWS S3
    storage_s3_region: str | None = None
    storage_s3_access_key_id: str | None = None
    storage_s3_secret_access_key: str | None = None

    # Comma-separated extra origins for CORS, e.g. a staging domain. The dev-mode fallback
    # list below (see cors_allowed_origins) covers the actual most common cause of "fetch
    # throws / Is the API running?" in local dev: Next.js silently shifts to port 3001+ if
    # 3000 is already taken, and CORS locked to exactly one hardcoded origin then blocks
    # every request with no readable error — the browser's fetch() just rejects, which looks
    # identical to "the backend isn't running" even though it's running fine.
    cors_allowed_origins_extra: str = ""

    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _API_DIR / ".env"),
        extra="ignore",
    )

    @property
    def cors_allowed_origins(self) -> list[str]:
        origins = {self.web_url}
        if self.app_env == "development":
            origins.update({"http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"})
        if self.cors_allowed_origins_extra:
            origins.update(o.strip() for o in self.cors_allowed_origins_extra.split(",") if o.strip())
        return sorted(origins)


settings = Settings()
