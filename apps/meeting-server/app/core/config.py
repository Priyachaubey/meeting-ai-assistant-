"""Meeting Server configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# __file__ = apps/meeting-server/app/core/config.py
_SERVICE_DIR = Path(__file__).resolve().parents[2]  # apps/meeting-server
_REPO_ROOT = Path(__file__).resolve().parents[4]  # repo root

# See apps/ai-server/app/core/config.py's comment on this same pattern — checking the
# repo-root .env (in addition to a literal apps/meeting-server/.env) means a standalone run
# of this service picks up the same JWT_SECRET as apps/api and apps/ai-server, instead of
# silently falling back to a different default and producing inter-service 401s.


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _SERVICE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    service_name: str = "convopilot-meeting-server"
    service_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8002
    debug: bool = False

    # Business API
    business_api_url: str = "http://localhost:8000"
    ai_server_url: str = "http://localhost:8001"
    internal_api_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/2"

    # Database
    database_url: str = "sqlite+aiosqlite:///./meeting_server.db"

    # JWT
    jwt_secret: str = "change-me-with-32-byte-secret"
    jwt_algorithm: str = "HS256"

    # Meeting limits
    max_participants_per_room: int = 100
    max_rooms_per_user: int = 10
    meeting_idle_timeout_seconds: int = 3600

    # Observability
    log_level: str = "INFO"
    sentry_dsn: str = ""


settings = Settings()
