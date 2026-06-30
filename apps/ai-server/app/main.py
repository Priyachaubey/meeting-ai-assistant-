"""ConvoPilot AI Server – FastAPI application entry point.

Phase 5: Production self-hosted inference.
All providers execute real neural models. No heuristic logic.
Models are loaded lazily on first request.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.routes.gateway import router as gateway_router


def _setup_hf_cache():
    """Configure HuggingFace model cache directory."""
    hf_home = settings.hf_home
    if hf_home:
        os.makedirs(hf_home, exist_ok=True)
        os.environ["HF_HOME"] = hf_home
        os.environ["TRANSFORMERS_CACHE"] = hf_home
    model_cache = settings.model_cache_dir
    if model_cache:
        os.makedirs(model_cache, exist_ok=True)


def _init_providers(provider_manager) -> dict:
    """Initialize all production ML providers.

    Returns a status dict showing which providers are ready.
    Models are registered but not loaded yet – they load lazily
    on first inference request.
    """
    from app.providers.providers import (
        LLMInferenceProvider,
        SpeechInferenceProvider,
        TranslationInferenceProvider,
        EmbeddingInferenceProvider,
        VisionInferenceProvider,
        OCRInferenceProvider,
        TTSInferenceProvider,
    )

    status = {}
    device = settings.device

    # LLM
    if settings.llm_provider == "ollama" and settings.ollama_base_url:
        llm = LLMInferenceProvider(
            model_id=settings.ollama_model,
            ollama_url=settings.ollama_base_url,
            device=device,
        )
        status["llm"] = f"ollama:{settings.ollama_model}"
    else:
        llm = LLMInferenceProvider(
            model_id=settings.llm_model,
            device=device,
        )
        status["llm"] = f"ml:{settings.llm_model}"
    provider_manager.register_llm(llm)

    # Speech
    speech = SpeechInferenceProvider(
        model_size=settings.whisper_model_size,
        device=device,
        compute_type=settings.whisper_compute_type,
    )
    provider_manager.register_speech(speech)
    status["speech"] = f"ml:faster-whisper-{settings.whisper_model_size}"

    # Translation
    translation = TranslationInferenceProvider(
        model_id=settings.translation_model,
        device=device,
    )
    provider_manager.register_translation(translation)
    status["translation"] = f"ml:{settings.translation_model.split('/')[-1]}"

    # Embedding
    embedding = EmbeddingInferenceProvider(
        model_id=settings.embedding_model,
        device=device,
    )
    provider_manager.register_embedding(embedding)
    status["embedding"] = f"ml:{settings.embedding_model.split('/')[-1]}"

    # Vision
    vision = VisionInferenceProvider(device=device)
    provider_manager.register_vision(vision)
    status["vision"] = "ml:moondream2"

    # OCR
    ocr = OCRInferenceProvider(default_language=settings.ocr_language)
    provider_manager.register_ocr(ocr)
    status["ocr"] = "ml:tesseract-5"

    # TTS
    tts = TTSInferenceProvider(voice=settings.tts_voice)
    provider_manager.register_tts(tts)
    status["tts"] = "ml:tts"

    return status


def _register_models(provider_status: dict):
    """Register model metadata in the model manager."""
    from app.managers.model_manager import model_manager, ModelInfo

    models = [
        ModelInfo(
            model_id=settings.llm_model,
            provider=provider_status.get("llm", "").split(":")[0],
            capability="llm",
            display_name="LLM Engine",
            max_tokens=settings.llm_max_context,
            capabilities=[
                "chat",
                "streaming",
                "function-calling",
                "json-mode",
                "structured-output",
                "session-memory",
                "tool-calling",
            ],
        ),
        ModelInfo(
            model_id=f"whisper-{settings.whisper_model_size}",
            provider=provider_status.get("speech", "").split(":")[0],
            capability="speech",
            display_name="Speech Engine",
            capabilities=[
                "transcribe",
                "streaming",
                "vad",
                "word-timestamps",
                "noise-filter",
                "multi-language",
            ],
        ),
        ModelInfo(
            model_id=settings.translation_model,
            provider=provider_status.get("translation", "").split(":")[0],
            capability="translation",
            display_name="Translation Engine",
            capabilities=[
                "translate",
                "auto-detect",
                "streaming",
                "200-languages",
                "translation-cache",
            ],
        ),
        ModelInfo(
            model_id=settings.embedding_model,
            provider=provider_status.get("embedding", "").split(":")[0],
            capability="embedding",
            display_name="Embedding Engine",
            max_tokens=512,
            capabilities=[
                "embed",
                "semantic-search",
                "batch",
                "realtime",
                "rag",
                "knowledge-base",
            ],
        ),
        ModelInfo(
            model_id="moondream2",
            provider=provider_status.get("vision", "").split(":")[0],
            capability="vision",
            display_name="Vision Engine",
            capabilities=[
                "image-understanding",
                "chart-analysis",
                "document-understanding",
                "whiteboard-analysis",
            ],
        ),
        ModelInfo(
            model_id="tesseract-5",
            provider=provider_status.get("ocr", "").split(":")[0],
            capability="ocr",
            display_name="OCR Engine",
            capabilities=[
                "text-extraction",
                "layout-analysis",
                "table-extraction",
                "pdf-ocr",
                "multi-language",
            ],
        ),
        ModelInfo(
            model_id=settings.diarization_model
            if settings.diarization_enabled
            else "none",
            provider="ml-local" if settings.diarization_enabled else "none",
            capability="diarization",
            display_name="Speaker Engine",
            capabilities=[
                "diarize",
                "speaker-tracking",
                "timeline",
                "analytics",
            ],
        ),
        ModelInfo(
            model_id="tts",
            provider=provider_status.get("tts", "").split(":")[0],
            capability="tts",
            display_name="TTS Engine",
            capabilities=["synthesize", "multi-voice", "multi-language"],
        ),
    ]
    for m in models:
        model_manager.register(m)
    return len(models)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    setup_logging(settings.log_level)
    from app.core.logging_config import logger

    logger.info(
        "ai_server_starting",
        version=settings.service_version,
        port=settings.port,
        device=settings.device,
        has_gpu=settings.has_gpu,
    )

    _setup_hf_cache()

    # Initialize all production ML providers
    from app.managers.provider_manager import provider_manager

    provider_status = _init_providers(provider_manager)
    logger.info("providers_initialized", status=provider_status)

    model_count = _register_models(provider_status)
    logger.info("models_registered", count=model_count)

    # Register meeting intelligence agents
    from app.managers.agent_manager import agent_manager
    from app.services.meeting_agents import register_all_agents

    register_all_agents(agent_manager)
    logger.info("agents_registered", count=len(agent_manager.list_agents()))

    # Initialize speaker diarization if enabled
    if settings.diarization_enabled:
        try:
            from app.providers.providers import SpeakerDiarizationProvider

            diarizer = SpeakerDiarizationProvider(device=settings.device)
            import app.services.speaker_service as ss

            ss._diarizer = diarizer
            logger.info("diarization_initialized", model=settings.diarization_model)
        except Exception as exc:
            logger.warning("diarization_init_failed", error=str(exc))

    # Wire embedding provider into search service
    try:
        import app.services.search_service as search_mod

        search_mod._embedding_provider = provider_manager.embedding
        logger.info("search_embedding_wired")
    except Exception as exc:
        logger.warning("search_embedding_wire_failed", error=str(exc))

    # Initialize RAG engine
    try:
        from app.services.rag_engine import rag_engine

        rag_engine.set_embedding_provider(provider_manager.embedding)
        rag_engine.set_llm_provider(provider_manager.llm)
        logger.info("rag_engine_initialized")
    except Exception as exc:
        logger.warning("rag_engine_init_failed", error=str(exc))

    logger.info(
        "ai_server_started",
        status="ready",
        device=settings.device,
        gpu=settings.gpu_name if settings.has_gpu else "none",
    )
    yield
    logger.info("ai_server_stopping")


app = FastAPI(
    title="ConvoPilot AI Server",
    description="Self-hosted AI inference engine – Phase 5",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gateway_router, prefix="/api/ai", tags=["AI Gateway"])


@app.get("/health", tags=["Health"])
async def root_health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
        "device": settings.device,
        "has_gpu": settings.has_gpu,
    }


@app.get("/hardware", tags=["Status"])
async def hardware_info():
    return {
        "device": settings.device,
        "has_gpu": settings.has_gpu,
        "gpu_name": settings.gpu_name,
        "gpu_vram_gb": settings.gpu_vram_gb,
        "model_cache_dir": settings.model_cache_dir,
    }
