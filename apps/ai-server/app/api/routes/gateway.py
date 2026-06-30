"""AI Gateway – main API routes for the AI Server."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, status
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse

from app.core.security import get_current_user
from app.managers.provider_manager import provider_manager
from app.managers.model_manager import model_manager
from app.managers.agent_manager import agent_manager
from app.managers.memory_manager import memory_manager
from app.managers.health_manager import health_manager
from app.managers.logging_manager import logging_manager
from app.providers.base import LLMMessage
from app.schemas.models import (
    ChatRequest,
    ChatResponse,
    EmbedRequest,
    EmbedResponse,
    TranslateRequest,
    TranslateResponse,
    VisionRequest,
    VisionResponse,
    OCRRequest,
    OCRResponse,
    AgentExecuteRequest,
    AgentExecuteResponse,
    HealthResponse,
    ProviderStatusResponse,
    ModelListResponse,
    AuditLogResponse,
    MemoryAddRequest,
    MemoryGetRequest,
)
from app.services.speaker_service import speaker_service
from app.services.search_service import search_service
from app.services.email_service import email_service
from app.services.export_service import export_service

router = APIRouter()


# ── LLM Gateway ───────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse, tags=["LLM"])
async def chat(
    request: ChatRequest, user: dict = Depends(get_current_user)
) -> ChatResponse:
    """Send messages to the LLM inference provider.

    Supports: session memory, JSON mode, tool calling, structured output.
    """
    messages = [
        LLMMessage(role=m["role"], content=m["content"]) for m in request.messages
    ]

    start = time.monotonic()
    provider = provider_manager.llm
    response = await provider.chat(
        messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        session_id=request.session_id,
    )
    latency = (time.monotonic() - start) * 1000

    logging_manager.log_llm_call(
        operation="chat",
        provider=response.provider,
        model=response.model,
        tokens_in=response.prompt_tokens,
        tokens_out=response.completion_tokens,
        latency_ms=latency,
        user_id=user.get("sub"),
        session_id=request.session_id,
    )

    return ChatResponse(
        content=response.content,
        model=response.model,
        provider=response.provider,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        latency_ms=latency,
    )


@router.post("/chat/stream", tags=["LLM"])
async def chat_stream(request: ChatRequest, user: dict = Depends(get_current_user)):
    """Stream LLM response via SSE."""
    from fastapi.responses import StreamingResponse

    messages = [
        LLMMessage(role=m["role"], content=m["content"]) for m in request.messages
    ]

    async def generate():
        try:
            provider = provider_manager.llm
            async for chunk in provider.stream(
                messages, temperature=request.temperature, max_tokens=request.max_tokens
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except RuntimeError as exc:
            yield f'data: {{"error": "{str(exc)}"}}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Embedding Gateway ─────────────────────────────────────────────────


@router.post("/embed", response_model=EmbedResponse, tags=["Embedding"])
async def embed(
    request: EmbedRequest, user: dict = Depends(get_current_user)
) -> EmbedResponse:
    """Generate embeddings for texts."""
    start = time.monotonic()
    try:
        provider = provider_manager.embedding
        response = await provider.embed(request.texts)
        latency = (time.monotonic() - start) * 1000

        logging_manager.log_llm_call(
            operation="embedding",
            provider=response.provider,
            model=response.model,
            tokens_in=response.token_count,
            latency_ms=latency,
            user_id=user.get("sub"),
        )

        return EmbedResponse(
            vectors=response.vectors,
            model=response.model,
            provider=response.provider,
            token_count=response.token_count,
            latency_ms=latency,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ── Translation Gateway ───────────────────────────────────────────────


@router.post("/translate", response_model=TranslateResponse, tags=["Translation"])
async def translate(
    request: TranslateRequest, user: dict = Depends(get_current_user)
) -> TranslateResponse:
    """Translate text using the configured translation provider."""
    start = time.monotonic()
    try:
        provider = provider_manager.translation
        response = await provider.translate(
            request.text,
            source_language=request.source_language,
            target_language=request.target_language,
        )
        latency = (time.monotonic() - start) * 1000

        return TranslateResponse(
            translated_text=response.translated_text,
            source_language=response.source_language,
            target_language=response.target_language,
            provider=response.provider,
            model=response.model,
            latency_ms=latency,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ── Speech Gateway ────────────────────────────────────────────────────


@router.post("/transcribe", tags=["Speech"])
async def transcribe(
    file: UploadFile = File(...),
    language: str = "en",
    user: dict = Depends(get_current_user),
):
    """Transcribe audio file using the configured speech provider."""
    start = time.monotonic()
    try:
        provider = provider_manager.speech
        audio_bytes = await file.read()
        response = await provider.transcribe(audio_bytes, language=language)
        latency = (time.monotonic() - start) * 1000

        logging_manager.log_llm_call(
            operation="transcribe",
            provider=response.provider,
            model=response.model,
            latency_ms=latency,
            user_id=user.get("sub"),
        )

        return {
            "text": " ".join(s.text for s in response.segments),
            "segments": [
                {
                    "text": s.text,
                    "start": s.start,
                    "end": s.end,
                    "speaker": s.speaker,
                    "confidence": s.confidence,
                }
                for s in response.segments
            ],
            "provider": response.provider,
            "model": response.model,
            "duration_seconds": response.duration_seconds,
            "latency_ms": latency,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ── Vision Gateway ────────────────────────────────────────────────────


@router.post("/vision", response_model=VisionResponse, tags=["Vision"])
async def vision(
    file: UploadFile = File(...),
    prompt: str = "Describe this image in detail.",
    user: dict = Depends(get_current_user),
) -> VisionResponse:
    """Analyze an image using the configured vision provider."""
    start = time.monotonic()
    try:
        provider = provider_manager.vision
        image_bytes = await file.read()
        response = await provider.analyze(
            image_bytes,
            prompt=prompt,
            content_type=file.content_type or "image/png",
        )
        latency = (time.monotonic() - start) * 1000

        return VisionResponse(
            description=response.description,
            labels=response.labels,
            provider=response.provider,
            model=response.model,
            latency_ms=latency,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ── OCR Gateway ───────────────────────────────────────────────────────


@router.post("/ocr", response_model=OCRResponse, tags=["OCR"])
async def ocr(
    file: UploadFile = File(...),
    language: str = "en",
    user: dict = Depends(get_current_user),
) -> OCRResponse:
    """Extract text from an image using the configured OCR provider."""
    start = time.monotonic()
    try:
        provider = provider_manager.ocr
        image_bytes = await file.read()
        response = await provider.extract_text(
            image_bytes,
            language=language,
            content_type=file.content_type or "image/png",
        )
        latency = (time.monotonic() - start) * 1000

        return OCRResponse(
            text=response.text,
            blocks=response.blocks,
            provider=response.provider,
            model=response.model,
            latency_ms=latency,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ── Agent Gateway ─────────────────────────────────────────────────────


@router.post("/agents/execute", response_model=AgentExecuteResponse, tags=["Agents"])
async def execute_agent(
    request: AgentExecuteRequest, user: dict = Depends(get_current_user)
) -> AgentExecuteResponse:
    """Execute a registered AI agent."""
    result = await agent_manager.execute(request.agent_name, request.context)
    return AgentExecuteResponse(
        agent_name=result.agent_name,
        output=result.output,
        latency_ms=result.latency_ms,
        success=result.success,
        error=result.error,
    )


@router.get("/agents", tags=["Agents"])
async def list_agents(user: dict = Depends(get_current_user)):
    """List all registered agents."""
    return {"agents": agent_manager.list_agents(), "stats": agent_manager.get_stats()}


# ── Memory Gateway ────────────────────────────────────────────────────


@router.post("/memory/add", tags=["Memory"])
async def memory_add(request: MemoryAddRequest, user: dict = Depends(get_current_user)):
    """Add an entry to a memory session."""
    from app.managers.memory_manager import MemoryEntry

    mem = memory_manager.get_or_create(request.session_id)
    entry = MemoryEntry(
        key=str(uuid.uuid4()),
        content=request.content,
        role=request.role,
        metadata=request.metadata,
    )
    mem.add(entry)
    return {
        "status": "ok",
        "session_id": request.session_id,
        "total_entries": len(mem.entries),
    }


@router.post("/memory/get", tags=["Memory"])
async def memory_get(request: MemoryGetRequest, user: dict = Depends(get_current_user)):
    """Get messages from a memory session."""
    mem = memory_manager.get(request.session_id)
    if mem is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": request.session_id,
        "messages": mem.get_messages(limit=request.limit),
    }


@router.delete("/memory/{session_id}", tags=["Memory"])
async def memory_delete(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a memory session."""
    memory_manager.delete(session_id)
    return {"status": "deleted", "session_id": session_id}


# ── Health & Status ───────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health() -> HealthResponse:
    """AI Server health check."""
    status = await health_manager.check()
    return HealthResponse(
        status=status.status,
        version=status.version,
        uptime_seconds=status.uptime_seconds,
        components=status.components,
    )


@router.get("/providers", response_model=ProviderStatusResponse, tags=["Status"])
async def provider_status(user: dict = Depends(get_current_user)):
    """Get status of all AI providers."""
    return ProviderStatusResponse(providers=provider_manager.get_status())


@router.get("/models", response_model=ModelListResponse, tags=["Status"])
async def list_models(user: dict = Depends(get_current_user)):
    """List all registered models."""
    return ModelListResponse(models=model_manager.get_status())


@router.get("/audit", response_model=AuditLogResponse, tags=["Status"])
async def audit_log(limit: int = 100, user: dict = Depends(get_current_user)):
    """Get AI operation audit log."""
    return AuditLogResponse(
        entries=logging_manager.get_entries(limit=limit),
        summary=logging_manager.get_summary(),
    )


@router.get("/ws/status", tags=["Status"])
async def ws_status(user: dict = Depends(get_current_user)):
    """Get WebSocket connection status."""
    from app.managers.ws_manager import ws_manager

    return ws_manager.get_status()


# ── Speaker Service ──────────────────────────────────────────────────


@router.post("/speakers/register", tags=["Speaker"])
async def register_speaker(data: dict, user: dict = Depends(get_current_user)):
    """Register a speaker in a meeting room."""
    room_id = data.get("room_id", "")
    speaker_id = data.get("speaker_id", "")
    display_name = data.get("display_name", "Speaker")
    if not room_id or not speaker_id:
        raise HTTPException(status_code=400, detail="room_id and speaker_id required")
    profile = speaker_service.register_speaker(room_id, speaker_id, display_name)
    return {
        "speaker_id": profile.speaker_id,
        "display_name": profile.display_name,
        "color": profile.color,
    }


@router.post("/speakers/segment", tags=["Speaker"])
async def add_speaker_segment(data: dict, user: dict = Depends(get_current_user)):
    """Add a speaker segment to the timeline."""
    room_id = data.get("room_id", "")
    speaker_id = data.get("speaker_id", "")
    speaker_name = data.get("speaker_name", "Speaker")
    text = data.get("text", "")
    if not room_id or not speaker_id or not text:
        raise HTTPException(
            status_code=400, detail="room_id, speaker_id, and text required"
        )
    segment = speaker_service.add_segment(
        room_id=room_id,
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        text=text,
        start_ms=data.get("start_ms"),
        end_ms=data.get("end_ms"),
        confidence=data.get("confidence", 0.95),
    )
    return {"segment": segment.to_dict()}


@router.get("/speakers/timeline/{room_id}", tags=["Speaker"])
async def get_speaker_timeline(room_id: str, user: dict = Depends(get_current_user)):
    """Get the full speaker timeline for a meeting."""
    timeline = speaker_service.get_timeline(room_id)
    speakers = speaker_service.get_speakers(room_id)
    return {"timeline": timeline, "speakers": speakers}


@router.get("/speakers/stats/{room_id}", tags=["Speaker"])
async def get_speaker_stats(room_id: str, user: dict = Depends(get_current_user)):
    """Get speaking statistics for a meeting."""
    stats = speaker_service.get_statistics(room_id)
    return {"statistics": stats}


@router.get("/speakers/color/{room_id}/{speaker_id}", tags=["Speaker"])
async def get_speaker_color(
    room_id: str, speaker_id: str, user: dict = Depends(get_current_user)
):
    """Get the assigned color for a speaker."""
    color = speaker_service.get_speaker_color(room_id, speaker_id)
    return {"color": color}


# ── Search Service ───────────────────────────────────────────────────


@router.post("/search", tags=["Search"])
async def enterprise_search(data: dict, user: dict = Depends(get_current_user)):
    """Enterprise search across meetings, transcripts, documents, and more."""
    query = data.get("query", "")
    workspace_id = data.get("workspace_id", "default")
    doc_types = data.get("doc_types")
    limit = data.get("limit", 20)
    if not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    results = search_service.search(
        query=query,
        workspace_id=workspace_id,
        doc_types=doc_types,
        limit=limit,
        user_id=user.get("sub"),
    )
    return {"results": results, "total": len(results)}


@router.post("/search/index", tags=["Search"])
async def index_document(data: dict, user: dict = Depends(get_current_user)):
    """Index a document for search."""
    doc_id = data.get("doc_id", str(uuid.uuid4()))
    doc_type = data.get("doc_type", "document")
    title = data.get("title", "")
    content = data.get("content", "")
    workspace_id = data.get("workspace_id", "default")
    if not content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    search_service.index_document(
        doc_id=doc_id,
        doc_type=doc_type,
        title=title,
        content=content,
        workspace_id=workspace_id,
        user_id=user.get("sub", ""),
        metadata=data.get("metadata"),
    )
    return {"status": "indexed", "doc_id": doc_id}


@router.get("/search/stats", tags=["Search"])
async def search_stats(
    workspace_id: str = "default", user: dict = Depends(get_current_user)
):
    """Get search index statistics."""
    return search_service.get_stats(workspace_id)


# ── Email Service ────────────────────────────────────────────────────


@router.post("/email/generate", tags=["Email"])
async def generate_email(data: dict, user: dict = Depends(get_current_user)):
    """Generate a follow-up email for a meeting."""
    meeting_id = data.get("meeting_id", "")
    meeting_title = data.get("meeting_title", "Meeting")
    participants = data.get("participants", [])
    summary = data.get("summary", "")
    action_items = data.get("action_items", [])
    decisions = data.get("decisions", [])
    transcript = data.get("transcript", "")
    duration_minutes = data.get("duration_minutes", 0)
    follow_ups = data.get("follow_ups", [])
    risks = data.get("risks", [])
    ai_insights = data.get("ai_insights", "")

    if not meeting_id:
        raise HTTPException(status_code=400, detail="meeting_id is required")

    draft = email_service.generate_email(
        meeting_id=meeting_id,
        meeting_title=meeting_title,
        participants=participants,
        summary=summary,
        action_items=action_items,
        decisions=decisions,
        transcript=transcript,
        duration_minutes=duration_minutes,
        follow_ups=follow_ups,
        risks=risks,
        ai_insights=ai_insights,
    )
    return {"draft": draft.to_dict()}


@router.get("/email/drafts/{meeting_id}", tags=["Email"])
async def get_email_drafts(meeting_id: str, user: dict = Depends(get_current_user)):
    """Get all email drafts for a meeting."""
    drafts = email_service.get_meeting_drafts(meeting_id)
    return {"drafts": drafts}


@router.post("/email/send/{draft_id}", tags=["Email"])
async def send_email(draft_id: str, user: dict = Depends(get_current_user)):
    """Mark an email draft as sent."""
    success = email_service.mark_sent(draft_id)
    if not success:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"status": "sent", "draft_id": draft_id}


@router.put("/email/recipients/{draft_id}", tags=["Email"])
async def update_email_recipients(
    draft_id: str, data: dict, user: dict = Depends(get_current_user)
):
    """Update email recipients."""
    recipients = data.get("recipients", [])
    cc = data.get("cc", [])
    success = email_service.update_recipients(draft_id, recipients, cc)
    if not success:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"status": "updated", "draft_id": draft_id}


# ── Export Service ───────────────────────────────────────────────────


@router.post("/export/{format}", tags=["Export"])
async def export_meeting(
    format: str,
    data: dict,
    user: dict = Depends(get_current_user),
):
    """Export a meeting in the specified format (json, txt, markdown, html)."""
    if format not in ("json", "txt", "markdown", "html"):
        raise HTTPException(
            status_code=400, detail="format must be json, txt, markdown, or html"
        )

    meeting_id = data.get("meeting_id", "")
    meeting_title = data.get("meeting_title", "Meeting")
    if not meeting_id:
        raise HTTPException(status_code=400, detail="meeting_id is required")

    if format == "json":
        result = export_service.export_json(meeting_id, meeting_title, data)
    elif format == "txt":
        result = export_service.export_txt(meeting_id, meeting_title, data)
    elif format == "markdown":
        result = export_service.export_markdown(meeting_id, meeting_title, data)
    elif format == "html":
        result = export_service.export_html(meeting_id, meeting_title, data)
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

    if format == "html":
        return HTMLResponse(content=result.content)
    elif format == "txt" or format == "markdown":
        return PlainTextResponse(content=result.content)
    else:
        return JSONResponse(
            content=json.loads(result.content)
            if format == "json"
            else {"content": result.content},
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"'
            },
        )


# ── Batch Analysis ───────────────────────────────────────────────────


@router.post("/analyze/full", tags=["Analysis"])
async def full_meeting_analysis(data: dict, user: dict = Depends(get_current_user)):
    """Run full AI analysis: summary, actions, decisions, risks, follow-ups, sentiment."""
    transcript = data.get("transcript", "")
    if not transcript.strip():
        return {"status": "empty", "message": "No transcript provided"}

    start = time.monotonic()

    summary_result = await agent_manager.execute(
        "meeting_summarizer", {"transcript": transcript}
    )
    actions_result = await agent_manager.execute(
        "action_item_extractor", {"transcript": transcript}
    )
    decisions_result = await agent_manager.execute(
        "decision_extractor", {"transcript": transcript}
    )
    risks_result = await agent_manager.execute(
        "risk_detector", {"transcript": transcript}
    )
    followups_result = await agent_manager.execute(
        "followup_generator", {"transcript": transcript}
    )
    sentiment_result = await agent_manager.execute(
        "sentiment_analyzer", {"transcript": transcript}
    )

    latency = (time.monotonic() - start) * 1000

    return {
        "status": "ok",
        "latency_ms": latency,
        "summary": summary_result.output.get("summary", ""),
        "action_items": actions_result.output.get("action_items", []),
        "decisions": decisions_result.output.get("decisions", []),
        "risks": risks_result.output.get("risks", []),
        "follow_ups": followups_result.output.get("follow_ups", []),
        "sentiment": sentiment_result.output.get("sentiment", "neutral"),
    }


# ── Service Status ───────────────────────────────────────────────────


@router.get("/services/status", tags=["Status"])
async def all_services_status(user: dict = Depends(get_current_user)):
    """Get status of all AI services."""
    return {
        "speaker": speaker_service.get_status(),
        "search": search_service.get_stats(),
        "email": email_service.get_status(),
    }


# ── Model Management ─────────────────────────────────────────────────


@router.get("/hardware", tags=["Status"])
async def hardware_status(user: dict = Depends(get_current_user)):
    """Get hardware detection and model configuration status."""
    from app.core.config import settings

    return {
        "device": settings.device,
        "has_gpu": settings.has_gpu,
        "gpu_name": settings.gpu_name,
        "gpu_vram_gb": settings.gpu_vram_gb,
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model
            if settings.llm_provider == "ml"
            else settings.ollama_model,
            "max_context": settings.llm_max_context,
        },
        "speech": {
            "model_size": settings.whisper_model_size,
        },
        "translation": {
            "model": settings.translation_model,
        },
        "embedding": {
            "model": settings.embedding_model,
            "dimension": settings.embedding_dimension,
        },
        "diarization": {
            "enabled": settings.diarization_enabled,
            "model": settings.diarization_model,
        },
        "model_cache_dir": settings.model_cache_dir,
    }


@router.get("/models/capabilities", tags=["Status"])
async def model_capabilities(user: dict = Depends(get_current_user)):
    """Get detailed capabilities of all registered models."""
    return {
        "models": [
            {
                "model_id": m.model_id,
                "provider": m.provider,
                "capability": m.capability,
                "display_name": m.display_name,
                "max_tokens": m.max_tokens,
                "capabilities": m.capabilities,
            }
            for m in model_manager.list_all()
        ]
    }


# ── Speaker Diarization ─────────────────────────────────────────────


@router.post("/speakers/diarize", tags=["Speaker"])
async def diarize_audio(
    file: UploadFile = File(...),
    num_speakers: int | None = None,
    room_id: str = "",
    user: dict = Depends(get_current_user),
):
    """Run ML speaker diarization on an audio file."""
    audio_bytes = await file.read()
    if not room_id:
        room_id = str(uuid.uuid4())

    segments = await speaker_service.diarize_audio(room_id, audio_bytes, num_speakers)
    return {
        "room_id": room_id,
        "segments": segments,
        "total_speakers": len(set(s.get("speaker", "") for s in segments)),
    }


# ── RAG Engine ────────────────────────────────────────────────────────


@router.post("/rag/query", tags=["RAG"])
async def rag_query(data: dict, user: dict = Depends(get_current_user)):
    """RAG query: retrieve context and generate answer with citations."""
    from app.services.rag_engine import rag_engine

    question = data.get("question", "")
    top_k = data.get("top_k", 5)
    source_types = data.get("source_types")

    if not question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    result = await rag_engine.query(
        question=question,
        top_k=top_k,
        source_types=source_types,
    )
    return result


@router.post("/rag/index", tags=["RAG"])
async def rag_index(data: dict, user: dict = Depends(get_current_user)):
    """Index a document into the RAG engine."""
    from app.services.rag_engine import rag_engine

    text = data.get("text", "")
    source_id = data.get("source_id", str(uuid.uuid4()))
    source_type = data.get("source_type", "document")
    title = data.get("title", "")

    if not text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    chunk_count = await rag_engine.index(
        text=text,
        source_id=source_id,
        source_type=source_type,
        title=title,
        metadata=data.get("metadata"),
    )
    return {
        "status": "indexed",
        "source_id": source_id,
        "chunks_created": chunk_count,
    }


@router.get("/rag/stats", tags=["RAG"])
async def rag_stats(user: dict = Depends(get_current_user)):
    """Get RAG engine statistics."""
    from app.services.rag_engine import rag_engine

    return rag_engine.get_stats()


# ── Structured Output ────────────────────────────────────────────────


@router.post("/structured", tags=["LLM"])
async def structured_output(data: dict, user: dict = Depends(get_current_user)):
    """Generate structured JSON output from the LLM.

    The LLM is instructed to respond with valid JSON only.
    """
    messages = data.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages required")

    llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]

    provider = provider_manager.llm
    response = await provider.chat(
        llm_messages,
        max_tokens=data.get("max_tokens", 2048),
        response_format="json",
    )

    # Try to parse as JSON
    try:
        parsed = json.loads(response.content)
        return {"data": parsed, "raw": response.content, "provider": response.provider}
    except json.JSONDecodeError:
        return {
            "data": None,
            "raw": response.content,
            "provider": response.provider,
            "parse_error": True,
        }


# ── Function Calling ─────────────────────────────────────────────────


@router.post("/function-call", tags=["LLM"])
async def function_call(data: dict, user: dict = Depends(get_current_user)):
    """Execute a function/tool call using the LLM.

    Provide tools (function definitions) and messages.
    The LLM will decide which function to call and with what arguments.
    """
    messages = data.get("messages", [])
    tools = data.get("tools", [])

    if not messages or not tools:
        raise HTTPException(status_code=400, detail="messages and tools required")

    llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]

    provider = provider_manager.llm
    response = await provider.chat(
        llm_messages,
        tools=tools,
        response_format="json",
        max_tokens=data.get("max_tokens", 1024),
    )

    # Try to parse the tool call
    try:
        parsed = json.loads(response.content)
        return {
            "tool_call": parsed,
            "raw": response.content,
            "provider": response.provider,
        }
    except json.JSONDecodeError:
        return {
            "tool_call": None,
            "raw": response.content,
            "provider": response.provider,
            "parse_error": True,
        }


# ── PDF OCR ───────────────────────────────────────────────────────────


@router.post("/ocr/pdf", tags=["OCR"])
async def ocr_pdf(
    file: UploadFile = File(...),
    language: str = "en",
    user: dict = Depends(get_current_user),
):
    """Extract text from a PDF document using OCR."""
    if not file.content_type or "pdf" not in file.content_type:
        raise HTTPException(status_code=400, detail="File must be a PDF")

    file_bytes = await file.read()
    provider = provider_manager.ocr
    response = await provider.extract_text(
        file_bytes, language=language, content_type="application/pdf"
    )

    return {
        "text": response.text,
        "blocks": response.blocks,
        "provider": response.provider,
        "model": response.model,
        "confidence": response.confidence,
        "language": response.language,
        "latency_ms": response.latency_ms,
    }
