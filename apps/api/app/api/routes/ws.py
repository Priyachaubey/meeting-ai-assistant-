import asyncio
import contextlib
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agents.orchestrator import MeetingAgentOrchestrator
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.entities import Meeting, TranscriptEvent, User
from app.schemas.meeting import TranscriptChunk
from app.services.memory import append_action_items, append_follow_ups, get_recent_context
from app.services.speech import TranscriptionProviderError, get_speech_provider
from app.services.translation import LiveTranslationCoordinator, TranslationProviderError
from app.services.translation.llm_provider import LLMTranslationProvider
from app.services.usage import record_usage

logger = logging.getLogger("convopilot.ws")

router = APIRouter(tags=["websocket"])
orchestrator = MeetingAgentOrchestrator()

# Sentinel pushed onto the audio queue to mean "no more audio coming" (mic stopped, or the
# connection is closing) — lets the Deepgram-feeding async generator end its `async for` loop
# cleanly instead of hanging forever on an empty queue. A plain object(), not None: None could
# theoretically be a legitimate (if useless) queue item in other contexts, this can't.
_AUDIO_STREAM_END = object()


async def _queue_to_async_iterator(queue: "asyncio.Queue[bytes | object]"):
    while True:
        item = await queue.get()
        if item is _AUDIO_STREAM_END:
            return
        yield item


@router.websocket("/ws/meetings/{meeting_id}")
async def meeting_socket(
    websocket: WebSocket,
    meeting_id: str,
    # Browsers can't set custom Authorization headers on a WebSocket handshake, so the JWT
    # travels as a query param here instead of through get_current_user_id's header-based scheme.
    token: str = Query(...),
    # Optional: translate this connection's own transcript line + AI suggestion into another
    # language. This is the single-connection case from TRANSLATION_ARCHITECTURE.md §5 — true
    # multi-participant fan-out (each connection getting a DIFFERENT language) needs a
    # connection registry that doesn't exist yet (§3 of that doc); this flag works today
    # because it's just "translate what this one socket already receives." If omitted, falls
    # back to the connecting user's persisted User.preferred_language (Settings page) —
    # "en" is treated as "no preference set" rather than literally translating English to
    # English on every chunk.
    target_language: str | None = Query(None),
    db: Session = Depends(get_db),
) -> None:
    try:
        user_id = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    meeting = db.get(Meeting, meeting_id)
    if not meeting or meeting.owner_id != user_id:
        await websocket.close(code=4403)
        return

    if not target_language:
        user = db.get(User, user_id)
        if user and user.preferred_language and user.preferred_language != "en":
            target_language = user.preferred_language

    translation_provider = LLMTranslationProvider() if target_language else None
    translator = LiveTranslationCoordinator(translation_provider) if translation_provider else None

    # Real audio frames (from the browser's microphone — see live-meeting.tsx) and manual-entry
    # JSON chunks arrive interleaved on the SAME socket. Both end up calling process_chunk(),
    # which touches `db` — a SQLAlchemy Session is not safe for concurrent use from two
    # coroutines at once, so this lock makes sure a mic-derived chunk (processed by the
    # background task below) and a manually-typed chunk (processed by the main receive loop)
    # never run process_chunk() at the same time, even though they can be IN FLIGHT concurrently
    # otherwise (receiving more audio bytes while a previous chunk's LLM call is still pending,
    # for example).
    db_lock = asyncio.Lock()
    audio_queue: "asyncio.Queue[bytes | object]" = asyncio.Queue()
    mic_task: asyncio.Task | None = None

    async def process_chunk(chunk: TranscriptChunk) -> None:
        async with db_lock:
            recent_lines = get_recent_context(db, meeting_id)
            result, usage_events = await orchestrator.process(chunk, meeting.workspace_id, recent_lines)
            db.add(
                TranscriptEvent(
                    meeting_id=meeting_id,
                    speaker=chunk.speaker,
                    text=chunk.text,
                    kind="question" if result.question_detected else "statement",
                    timestamp_ms=chunk.timestamp_ms,
                )
            )
            if result.action_items:
                append_action_items(db, meeting_id, result.action_items)
            if result.follow_ups:
                append_follow_ups(db, meeting_id, result.follow_ups)
            db.commit()
            for event in usage_events:
                record_usage(db, event, owner_id=user_id, meeting_id=meeting_id)

            response_payload = {
                "meeting_id": meeting_id,
                "speaker": chunk.speaker,
                "text": chunk.text,
                "timestamp_ms": chunk.timestamp_ms,
                **result.model_dump(),
            }

            if translator and target_language and translation_provider:
                translation_provider.last_usage = None
                try:
                    segments = await translator.add_utterance(
                        chunk.speaker, chunk.text, chunk.timestamp_ms, target_languages={target_language}
                    )
                except TranslationProviderError as exc:
                    logger.warning("Live translation unavailable: %s", exc)
                    segments = []
                if translation_provider.last_usage:
                    record_usage(db, translation_provider.last_usage, owner_id=user_id, meeting_id=meeting_id)
                if segments:
                    response_payload["translated_transcript"] = segments[0].translated_text
                    response_payload["translated_language"] = target_language
                if result.suggested_response and not result.suggested_response.startswith("[AI suggestion"):
                    translation_provider.last_usage = None
                    try:
                        translated_suggestion = await translation_provider.translate(
                            result.suggested_response, source_language=None, target_language=target_language
                        )
                        response_payload["translated_suggested_response"] = translated_suggestion
                        if translation_provider.last_usage:
                            record_usage(db, translation_provider.last_usage, owner_id=user_id, meeting_id=meeting_id)
                    except TranslationProviderError as exc:
                        logger.warning("Suggestion translation unavailable: %s", exc)

        await websocket.send_json(response_payload)

    async def run_mic_transcription() -> None:
        """Background task, started lazily on the first binary frame this connection ever
        receives — a manual-entry-only session never touches Deepgram at all, zero behavior
        change for that already-working path. Consumes audio_queue, streams it to the real
        Deepgram provider, and runs every finalized segment through the exact same
        process_chunk() pipeline as a manually-typed line, so the two input paths can't
        silently diverge in what they do with a transcript once they have one."""
        try:
            provider = get_speech_provider()
        except TranscriptionProviderError as exc:
            await websocket.send_json({"error": f"Speech provider unavailable: {exc}"})
            return
        try:
            async for transcript_text in provider.stream(_queue_to_async_iterator(audio_queue)):
                if not transcript_text.strip():
                    continue
                chunk = TranscriptChunk(
                    speaker="Microphone", text=transcript_text, timestamp_ms=int((time.time() - connection_start) * 1000)
                )
                await process_chunk(chunk)
        except TranscriptionProviderError as exc:
            logger.warning("Mic transcription stopped for meeting %s: %s", meeting_id, exc)
            await websocket.send_json({"error": f"Speech provider error: {exc}"})

    await websocket.accept()
    # timestamp_ms is meeting-relative elapsed time, not absolute epoch time — the Meeting
    # Deep Dive timeline (formatTimestamp in meetings/[id]/page.tsx) renders it as mm:ss,
    # which only makes sense for "seconds since this session started," not a 13-digit epoch
    # value. The frontend's manual-entry path computes this the same way (see live-meeting.tsx,
    # fixed in the same pass this comment was added) — both input paths need to agree on what
    # timestamp_ms actually means, or the timeline and transcript ordering silently corrupt.
    connection_start = time.time()
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            raw_bytes = message.get("bytes")
            if raw_bytes is not None:
                if mic_task is None:
                    mic_task = asyncio.create_task(run_mic_transcription())
                await audio_queue.put(raw_bytes)
                continue

            raw_text = message.get("text")
            if raw_text is None:
                continue
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "invalid message: not valid JSON"})
                continue

            if payload.get("type") == "end_audio":
                # Browser stopped the mic (or the user clicked Stop) — signal the streaming
                # generator to finish cleanly rather than leaving it awaiting a queue item
                # that will never arrive until the whole connection closes anyway.
                await audio_queue.put(_AUDIO_STREAM_END)
                continue

            try:
                chunk = TranscriptChunk(**payload)
            except ValidationError as exc:
                await websocket.send_json({"error": f"invalid transcript chunk: {exc}"})
                continue
            await process_chunk(chunk)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for meeting %s", meeting_id)
    finally:
        await audio_queue.put(_AUDIO_STREAM_END)
        if mic_task is not None:
            mic_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await mic_task
