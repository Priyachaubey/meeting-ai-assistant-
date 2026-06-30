"""AI Server configuration – Phase 5.

All settings for self-hosted ML inference.
Hardware is auto-detected. Models are configurable via env vars.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("convopilot.config")

# __file__ = apps/ai-server/app/core/config.py
_SERVICE_DIR = Path(__file__).resolve().parents[2]  # apps/ai-server
_REPO_ROOT = Path(__file__).resolve().parents[4]  # repo root

# Same reasoning as apps/api/app/core/config.py: under Docker Compose, `env_file: .env` in
# docker-compose.yml already injects the repo-root .env as real container env vars, which
# pydantic-settings reads regardless of this literal-file-path setting — so this only matters
# when running this service standalone (uvicorn from apps/ai-server, no Docker). Previously
# this only checked a literal "./.env" relative to cwd, which silently missed the repo-root
# .env in that case and fell back to defaults below — meaning a standalone ai-server could
# end up on a different JWT_SECRET than apps/api, and every inter-service call would fail
# with 401s that look like an auth bug rather than a config-loading one. Checking both
# locations (repo-root .env first, apps/ai-server/.env as an override) closes that gap.


def _detect_hardware() -> dict:
    """Detect available hardware for model inference."""
    info: dict = {"has_gpu": False, "gpu_name": "", "gpu_vram_gb": 0.0, "device": "cpu"}
    try:
        import torch

        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            props = torch.cuda.get_device_properties(0)
            info["has_gpu"] = True
            info["gpu_name"] = props.name
            info["gpu_vram_gb"] = round(props.total_mem / 1e9, 1)
            info["device"] = "cuda"
            logger.info("hardware_detected", **info)
    except ImportError:
        pass
    return info


_HARDWARE = _detect_hardware()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _SERVICE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # ── Service identity ──────────────────────────────────────────────
    service_name: str = "convopilot-ai-server"
    service_version: str = "5.0.0"
    host: str = "0.0.0.0"
    port: int = 8001
    debug: bool = False

    # ── Business API ──────────────────────────────────────────────────
    business_api_url: str = "http://localhost:8000"
    business_api_internal_key: str = ""

    # ── Redis ──────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/1"

    # ── Database ───────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./ai_server.db"

    # ── JWT ────────────────────────────────────────────────────────────
    jwt_secret: str = "change-me-with-32-byte-secret"
    jwt_algorithm: str = "HS256"

    # ── Hardware (auto-detected) ──────────────────────────────────────
    device: str = _HARDWARE["device"]
    has_gpu: bool = _HARDWARE["has_gpu"]
    gpu_name: str = _HARDWARE["gpu_name"]
    gpu_vram_gb: float = _HARDWARE["gpu_vram_gb"]

    # ── LLM ───────────────────────────────────────────────────────────
    # "ml" for direct transformers, "ollama" for Ollama server
    llm_provider: str = "ml"
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_max_context: int = 32768
    ollama_base_url: str = ""
    ollama_model: str = "qwen2.5:7b-instruct"

    # ── Speech (STT) ─────────────────────────────────────────────────
    whisper_model_size: str = "large-v3-turbo"
    whisper_compute_type: str = "auto"
    whisper_language: str = "en"

    # ── Translation ──────────────────────────────────────────────────
    translation_model: str = "facebook/nllb-200-distilled-600M"

    # ── Embedding ────────────────────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ── Vision ───────────────────────────────────────────────────────
    vision_model: str = "vikhyatk/moondream2"

    # ── OCR ──────────────────────────────────────────────────────────
    ocr_language: str = "eng"

    # ── Speaker Diarization ──────────────────────────────────────────
    diarization_enabled: bool = True
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    huggingface_token: str = ""

    # ── TTS ──────────────────────────────────────────────────────────
    tts_voice: str = "en_US-lessac-medium"

    # ── Model storage ────────────────────────────────────────────────
    model_cache_dir: str = "/models"
    hf_home: str = "/models/huggingface"

    # ── Rate limiting ────────────────────────────────────────────────
    rate_limit_per_minute: int = 120

    # ── Observability ────────────────────────────────────────────────
    log_level: str = "INFO"
    sentry_dsn: str = ""


settings = Settings()
