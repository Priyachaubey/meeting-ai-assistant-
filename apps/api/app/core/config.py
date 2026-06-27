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

    jwt_secret: str = "dev-secret"
    encryption_key: str | None = None

    # LLM (OpenAI + Claude wired; Gemini key accepted so .env doesn't need to change when
    # it's added — see app/services/llm)
    llm_provider: str = "openai"  # which provider to try first; the other becomes the fallback
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    gemini_api_key: str | None = None
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 2

    # Speech (Deepgram + AssemblyAI wired; see app/services/speech)
    speech_provider: str = "deepgram"  # which to try first; the other becomes the fallback
    deepgram_api_key: str | None = None
    deepgram_model: str = "nova-2"
    assemblyai_api_key: str | None = None
    audio_sample_rate_hz: int = 16000

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
