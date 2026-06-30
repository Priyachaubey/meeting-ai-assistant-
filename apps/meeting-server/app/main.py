"""ConvoPilot Meeting Server – FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.routes.meetings import router as meetings_router
from app.services.translation_pipeline import translation_pipeline
from app.services.ai_translate_client import translate_via_ai_server


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    from app.core.logging_config import logger

    logger.info(
        "meeting_server_starting", version=settings.service_version, port=settings.port
    )
    # Initialize connection store
    app.state.meeting_connections = {}
    # The actual fix: translation_pipeline existed fully built but with no real translation
    # function ever injected — every translate_transcript() call was silently raising
    # RuntimeError. This wires it to apps/ai-server's real /translate endpoint (NLLB-200).
    translation_pipeline.set_translate_fn(translate_via_ai_server)
    logger.info("translation_pipeline_wired", target="ai-server")
    logger.info("meeting_server_started", status="ready")
    yield
    logger.info("meeting_server_stopping")


app = FastAPI(
    title="ConvoPilot Meeting Server",
    description="Enterprise meeting engine for the Microtechnique platform",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────
app.include_router(meetings_router, prefix="/api/meetings", tags=["Meetings"])


@app.get("/health", tags=["Health"])
async def root_health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
    }
