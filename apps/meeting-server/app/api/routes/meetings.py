"""Meeting Server API routes – with real-time transcript, translation, and AI."""

from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Any

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.core.security import get_current_user
from app.core.config import settings
from app.rooms.manager import room_manager
from app.rooms.models import MeetingType, RoomSettings
from app.participants.manager import participant_manager
from app.participants.models import ParticipantRole, ParticipantState
from app.chat.manager import chat_manager
from app.recording.manager import recording_manager
from app.signalling.manager import signalling_manager, SignallingMessage
from app.services.transcript_manager import transcript_manager
from app.services.translation_pipeline import translation_pipeline
from app.services.whiteboard_manager import whiteboard_manager
from app.services.audio_transcription import AudioTranscriptionSession, transcribe_via_ai_server
from app.schemas.models import (
    CreateRoomRequest,
    CreateRoomResponse,
    JoinRoomRequest,
    ParticipantActionRequest,
    HostActionRequest,
    ChatSendRequest,
    SignallingMessage as SignallingMessageSchema,
    MeetingStatusResponse,
)

router = APIRouter()


# ── AI Server Client ──────────────────────────────────────────────────


async def _ai_chat(messages: list[dict], max_tokens: int = 2048) -> str:
    """Send a chat request to the AI Server and return the response content.

    All LLM inference is handled by the AI Server.
    """
    ai_url = getattr(settings, "ai_server_url", "http://localhost:8001")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{ai_url}/api/ai/chat",
                json={
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("content", "")
    except Exception as exc:
        return f"[AI Server error: {exc}]"


# ── Room Management ───────────────────────────────────────────────────


@router.post("/rooms", response_model=CreateRoomResponse, tags=["Rooms"])
async def create_room(
    request: CreateRoomRequest, user: dict = Depends(get_current_user)
):
    """Create a new meeting room."""
    room_settings = RoomSettings(
        waiting_room=request.waiting_room,
        meeting_password=request.meeting_password,
        mute_on_entry=request.mute_on_entry,
        max_participants=request.max_participants,
        recording_enabled=request.recording_enabled,
        chat_enabled=request.chat_enabled,
        screen_share_enabled=request.screen_share_enabled,
    )

    room_type = (
        MeetingType(request.type)
        if request.type in MeetingType.__members__.values()
        else MeetingType.INSTANT
    )

    room = room_manager.create_room(
        host_id=user["sub"],
        title=request.title,
        room_type=room_type,
        workspace_id=request.workspace_id,
        room_settings=room_settings,
    )

    participant_manager.add_participant(
        room_id=room.id,
        user_id=user["sub"],
        display_name=user.get("full_name", "Host"),
        role=ParticipantRole.HOST,
    )
    room.participants_count = 1

    join_url = f"/meetings/{room.id}"

    return CreateRoomResponse(
        id=room.id,
        title=room.title,
        type=room.type.value,
        status=room.status.value,
        host_id=room.host_id,
        join_url=join_url,
        settings=room.to_dict()["settings"],
        created_at=room.created_at.isoformat(),
    )


@router.get("/rooms", tags=["Rooms"])
async def list_rooms(user: dict = Depends(get_current_user)):
    """List meeting rooms for the current user."""
    rooms = room_manager.list_rooms(host_id=user["sub"])
    return {"rooms": [r.to_dict() for r in rooms]}


@router.get("/rooms/{room_id}", tags=["Rooms"])
async def get_room(room_id: str, user: dict = Depends(get_current_user)):
    """Get room details, participants, transcript, and AI state."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    participants = participant_manager.get_room_participants(room_id)
    transcript = transcript_manager.get_transcript(room_id)
    ai_state = transcript_manager.get_ai_state(room_id)
    return {
        "room": room.to_dict(),
        "participants": [p.to_dict() for p in participants],
        "transcript": [e.to_dict() for e in transcript],
        "ai_state": ai_state.to_dict() if ai_state else None,
    }


@router.post("/rooms/{room_id}/start", tags=["Rooms"])
async def start_room(room_id: str, user: dict = Depends(get_current_user)):
    """Start a meeting room."""
    room = room_manager.start_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"status": "started", "room": room.to_dict()}


@router.post("/rooms/{room_id}/end", tags=["Rooms"])
async def end_room(room_id: str, user: dict = Depends(get_current_user)):
    """End a meeting room."""
    room = room_manager.end_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"status": "ended", "room": room.to_dict()}


@router.post("/rooms/{room_id}/lock", tags=["Rooms"])
async def lock_room(room_id: str, user: dict = Depends(get_current_user)):
    room = room_manager.lock_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"is_locked": True}


@router.post("/rooms/{room_id}/unlock", tags=["Rooms"])
async def unlock_room(room_id: str, user: dict = Depends(get_current_user)):
    room = room_manager.unlock_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"is_locked": False}


# ── Participant Management ────────────────────────────────────────────


@router.post("/rooms/{room_id}/join", tags=["Participants"])
async def join_room(
    room_id: str, request: JoinRoomRequest, http_request: Request, user: dict = Depends(get_current_user)
):
    """Join a meeting room."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.is_locked:
        raise HTTPException(status_code=403, detail="Room is locked")
    if (
        room.settings.meeting_password
        and request.password != room.settings.meeting_password
    ):
        raise HTTPException(status_code=403, detail="Invalid meeting password")

    active_count = participant_manager.get_active_count(room_id)
    if active_count >= room.settings.max_participants:
        raise HTTPException(status_code=429, detail="Room is at capacity")

    initial_state = (
        ParticipantState.IN_WAITING_ROOM
        if room.settings.waiting_room
        else ParticipantState.IN_ROOM
    )
    role = (
        ParticipantRole.HOST
        if user["sub"] == room.host_id
        else ParticipantRole.PARTICIPANT
    )

    participant = participant_manager.add_participant(
        room_id=room_id,
        user_id=user["sub"],
        display_name=request.display_name,
        role=role,
        state=initial_state,
    )
    room.participants_count = participant_manager.get_active_count(room_id)

    if initial_state == ParticipantState.IN_WAITING_ROOM:
        # Host notification fix: previously silent — a host's waiting-room panel would only
        # ever learn someone new arrived on its next poll cycle, not the moment it happens.
        # The new arrival hasn't opened the room WS yet (they're in the waiting room — see
        # the WS access-control fix above), so this broadcast only reaches whoever's already
        # connected, which for a waiting-room flow is exactly who needs to know: the host.
        await _broadcast_to_room(
            http_request.app.state,
            room_id,
            {
                "type": "waiting_list_changed",
                "participant_id": participant.id,
                "action": "joined",
                "participant": participant.to_dict(),
            },
        )

    return {
        "participant": participant.to_dict(),
        "room": room.to_dict(),
        "state": initial_state.value,
    }


@router.post("/rooms/{room_id}/leave", tags=["Participants"])
async def leave_room(room_id: str, user: dict = Depends(get_current_user)):
    """Leave a meeting room."""
    participants = participant_manager.get_room_participants(room_id)
    for p in participants:
        if p.user_id == user["sub"]:
            participant_manager.remove_participant(p.id)
            room = room_manager.get_room(room_id)
            if room:
                room.participants_count = participant_manager.get_active_count(room_id)
            return {"status": "left"}
    raise HTTPException(status_code=404, detail="Participant not found in room")


@router.post(
    "/rooms/{room_id}/participants/{participant_id}/action", tags=["Participants"]
)
async def participant_action(
    room_id: str,
    participant_id: str,
    request: ParticipantActionRequest,
    user: dict = Depends(get_current_user),
):
    """Perform a participant action (mute, video, raise hand, etc.)."""
    participant = participant_manager.get_participant(participant_id)
    if not participant or participant.room_id != room_id:
        raise HTTPException(status_code=404, detail="Participant not found")

    action = request.action
    if action == "mute":
        participant.media.audio_enabled = False
    elif action == "unmute":
        participant.media.audio_enabled = True
    elif action == "video_on":
        participant.media.video_enabled = True
    elif action == "video_off":
        participant.media.video_enabled = False
    elif action == "raise_hand":
        participant.raise_hand()
    elif action == "lower_hand":
        participant.lower_hand()
    elif action == "screen_share_start":
        participant.media.screen_sharing = True
    elif action == "screen_share_stop":
        participant.media.screen_sharing = False
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    return {"participant": participant.to_dict()}


# ── Host Controls ─────────────────────────────────────────────────────


@router.post("/rooms/{room_id}/host/action", tags=["Host Controls"])
async def host_action(
    room_id: str,
    request: HostActionRequest,
    user: dict = Depends(get_current_user),
):
    """Host-only actions: lock, mute all, remove participant, etc."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.host_id != user["sub"]:
        raise HTTPException(
            status_code=403, detail="Only the host can perform this action"
        )

    action = request.action
    if action == "lock":
        room.lock()
        return {"is_locked": True}
    elif action == "unlock":
        room.unlock()
        return {"is_locked": False}
    elif action == "mute_all":
        muted = participant_manager.mute_all(room_id)
        return {"muted_count": len(muted)}
    elif action == "remove_participant":
        if request.target_participant_id:
            participant_manager.remove_participant(request.target_participant_id)
            room.participants_count = participant_manager.get_active_count(room_id)
            return {"status": "removed"}
        raise HTTPException(status_code=400, detail="target_participant_id required")
    elif action == "end_meeting":
        room_manager.end_room(room_id)
        return {"status": "ended"}
    elif action == "start_recording":
        rec = recording_manager.start_recording(room_id, user["sub"])
        room.start_recording()
        return {"recording": rec.to_dict()}
    elif action == "stop_recording":
        rec = recording_manager.stop_recording(room_id)
        room.stop_recording()
        return {"recording": rec.to_dict() if rec else None}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


# ── Waiting Room ──────────────────────────────────────────────────────


@router.post("/rooms/{room_id}/waiting/admit/{participant_id}", tags=["Waiting Room"])
async def admit_from_waiting(
    room_id: str, participant_id: str, request: Request, user: dict = Depends(get_current_user)
):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    # Security fix, found during an authorization audit: this endpoint correctly required a
    # valid JWT (authentication) but never checked *whose* JWT — any logged-in user, with no
    # relationship to this meeting at all, could call this and admit or reject people from
    # any room's waiting list. Same host-only check host_action already applies correctly for
    # lock/mute_all/remove_participant/end_meeting — was simply missing here.
    if room.host_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Only the host can admit participants")
    participant = participant_manager.get_participant(participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    participant.state = ParticipantState.IN_ROOM
    room.participants_count = participant_manager.get_active_count(room_id)
    # Real-time sync fix: previously nothing told anyone this happened. The admitted
    # participant's frontend picks this up via polling (see the WS access-control fix above
    # for why polling, not a kept-alive socket) — but any co-host watching the waiting list
    # live needs a push, not a poll, or their panel goes stale the moment someone else admits
    # a participant. Reuses the connection registry already built for signaling (§22) rather
    # than adding a separate notification channel.
    await _broadcast_to_room(
        request.app.state,
        room_id,
        {"type": "waiting_list_changed", "participant_id": participant_id, "action": "admitted"},
    )
    return {"status": "admitted", "participant": participant.to_dict()}


@router.post("/rooms/{room_id}/waiting/reject/{participant_id}", tags=["Waiting Room"])
async def reject_from_waiting(
    room_id: str, participant_id: str, request: Request, user: dict = Depends(get_current_user)
):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.host_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Only the host can reject participants")
    participant_manager.remove_participant(participant_id)
    await _broadcast_to_room(
        request.app.state,
        room_id,
        {"type": "waiting_list_changed", "participant_id": participant_id, "action": "rejected"},
    )
    return {"status": "rejected"}


@router.get("/rooms/{room_id}/waiting", tags=["Waiting Room"])
async def list_waiting(room_id: str, user: dict = Depends(get_current_user)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.host_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Only the host can view the waiting list")
    participants = participant_manager.get_room_participants(room_id)
    waiting = [
        p.to_dict() for p in participants if p.state == ParticipantState.IN_WAITING_ROOM
    ]
    return {"waiting": waiting}


# ── Chat ──────────────────────────────────────────────────────────────


@router.post("/rooms/{room_id}/chat", tags=["Chat"])
async def send_chat(
    room_id: str, request: ChatSendRequest, user: dict = Depends(get_current_user)
):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not room.settings.chat_enabled:
        raise HTTPException(status_code=403, detail="Chat is disabled")

    msg = chat_manager.add_message(
        room_id=room_id,
        sender_id=user["sub"],
        sender_name=user.get("full_name", "User"),
        content=request.content,
        message_type=request.message_type,
    )
    return {"message": msg.to_dict()}


@router.get("/rooms/{room_id}/chat", tags=["Chat"])
async def get_chat(
    room_id: str, limit: int = 100, user: dict = Depends(get_current_user)
):
    messages = chat_manager.get_messages(room_id, limit=limit)
    return {"messages": [m.to_dict() for m in messages]}


# ── Transcript ────────────────────────────────────────────────────────


@router.post("/rooms/{room_id}/transcript", tags=["Transcript"])
async def add_transcript(
    room_id: str,
    data: dict,
    user: dict = Depends(get_current_user),
):
    """Add a transcript entry (from speech-to-text or manual entry)."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    speaker_id = data.get("speaker_id", user["sub"])
    speaker_name = data.get("speaker_name", user.get("full_name", "Speaker"))
    text = data.get("text", "")
    kind = data.get("kind", "statement")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    entry = transcript_manager.add_transcript(
        room_id=room_id,
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        text=text,
        kind=kind,
    )

    return {"transcript": entry.to_dict()}


@router.get("/rooms/{room_id}/transcript", tags=["Transcript"])
async def get_transcript(
    room_id: str, limit: int = 200, user: dict = Depends(get_current_user)
):
    """Get transcript entries for a room."""
    entries = transcript_manager.get_transcript(room_id, limit=limit)
    speakers = transcript_manager.get_speakers(room_id)
    return {
        "transcript": [e.to_dict() for e in entries],
        "speakers": speakers,
    }


# ── Translation ───────────────────────────────────────────────────────


@router.get("/rooms/{room_id}/translations/{transcript_id}", tags=["Translation"])
async def get_translations(
    room_id: str,
    transcript_id: str,
    language: str | None = None,
    user: dict = Depends(get_current_user),
):
    """Get translations for a specific transcript entry."""
    entries = transcript_manager.get_translations(transcript_id, language)
    return {"translations": [e.to_dict() for e in entries]}


# ── AI State ──────────────────────────────────────────────────────────


@router.get("/rooms/{room_id}/ai", tags=["AI"])
async def get_ai_state(room_id: str, user: dict = Depends(get_current_user)):
    """Get live AI state for a meeting (summary, actions, decisions, risks)."""
    ai_state = transcript_manager.get_ai_state(room_id)
    if not ai_state:
        return {"ai_state": None, "status": "no_data"}
    return {"ai_state": ai_state.to_dict(), "status": "ok"}


@router.post("/rooms/{room_id}/ai/analyze", tags=["AI"])
async def trigger_ai_analysis(room_id: str, user: dict = Depends(get_current_user)):
    """Trigger AI analysis on current transcript (summary, actions, decisions, risks)."""
    transcript_text = transcript_manager.get_transcript_text(room_id)
    if not transcript_text.strip():
        return {"status": "empty", "message": "No transcript to analyze"}

    participants = participant_manager.get_room_participants(room_id)
    participant_names = [p.display_name for p in participants]
    room = room_manager.get_room(room_id)
    meeting_title = room.title if room else "Meeting"

    # Run all AI agents
    from app.services.transcript_manager import transcript_manager as tm

    context = {
        "transcript": transcript_text,
        "participants": participant_names,
        "meeting_title": meeting_title,
    }

    # Send to AI Server for real inference
    summary_resp = await _ai_chat(
        [
            {"role": "system", "content": "Generate a concise meeting summary."},
            {"role": "user", "content": f"Summarize:\n\n{transcript_text[-3000:]}"},
        ],
        max_tokens=500,
    )

    # Action items
    actions_resp = await _ai_chat(
        [
            {
                "role": "system",
                "content": "Extract action items. Return a numbered list.",
            },
            {
                "role": "user",
                "content": f"Extract action items:\n\n{transcript_text[-3000:]}",
            },
        ],
        max_tokens=300,
    )
    action_items = [
        l.strip().lstrip("0123456789.-) ")
        for l in actions_resp.split("\n")
        if l.strip() and not l.strip().startswith(("Action", "No specific"))
    ]
    action_items = [i for i in action_items if len(i) > 5][:10]

    # Decisions
    decisions_resp = await _ai_chat(
        [
            {"role": "system", "content": "Extract decisions. Return a numbered list."},
            {
                "role": "user",
                "content": f"Extract decisions:\n\n{transcript_text[-3000:]}",
            },
        ],
        max_tokens=300,
    )
    decisions = [
        l.strip().lstrip("0123456789.-) ")
        for l in decisions_resp.split("\n")
        if l.strip() and not l.strip().startswith(("Decision", "No explicit"))
    ]
    decisions = [i for i in decisions if len(i) > 5][:10]

    # Risks
    risks_resp = await _ai_chat(
        [
            {"role": "system", "content": "Identify risks. Return a numbered list."},
            {
                "role": "user",
                "content": f"Identify risks:\n\n{transcript_text[-3000:]}",
            },
        ],
        max_tokens=300,
    )
    risks = [
        l.strip().lstrip("0123456789.-) ")
        for l in risks_resp.split("\n")
        if l.strip() and not l.strip().startswith(("Risk", "No specific"))
    ]
    risks = [i for i in risks if len(i) > 5][:10]

    # Sentiment
    sentiment_resp = await _ai_chat(
        [
            {
                "role": "system",
                "content": "Analyze sentiment. Reply: positive, negative, or neutral.",
            },
            {"role": "user", "content": f"Analyze:\n\n{transcript_text[-1500:]}"},
        ],
        max_tokens=10,
    )
    sentiment = sentiment_resp.strip().lower()
    if sentiment not in ("positive", "negative", "neutral"):
        sentiment = "neutral"

    # Follow-ups
    followups_resp = await _ai_chat(
        [
            {
                "role": "system",
                "content": "Generate follow-up items. Return a numbered list.",
            },
            {
                "role": "user",
                "content": f"Generate follow-ups:\n\n{transcript_text[-3000:]}",
            },
        ],
        max_tokens=300,
    )
    follow_ups = [
        l.strip().lstrip("0123456789.-) ")
        for l in followups_resp.split("\n")
        if l.strip() and not l.strip().startswith(("Follow", "No follow"))
    ]
    follow_ups = [i for i in follow_ups if len(i) > 5][:10]

    # Update AI state
    ai_state = tm.update_ai_state(
        room_id,
        summary=summary_resp,
        action_items=action_items,
        decisions=decisions,
        risks=risks,
        follow_ups=follow_ups,
        sentiment=sentiment,
    )

    return {
        "status": "ok",
        "ai_state": ai_state.to_dict(),
    }


@router.post("/rooms/{room_id}/ai/chat", tags=["AI"])
async def ai_chat(
    room_id: str,
    data: dict,
    user: dict = Depends(get_current_user),
):
    """Ask the AI assistant a question about the meeting."""
    question = data.get("question", "")
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    transcript_text = transcript_manager.get_transcript_text(room_id)

    response = await _ai_chat(
        [
            {
                "role": "system",
                "content": "You are a meeting AI assistant. Answer questions based on the meeting transcript. If the answer is not in the transcript, say so.",
            },
            {
                "role": "user",
                "content": f"Meeting transcript:\n{transcript_text[-3000:]}\n\nQuestion: {question}",
            },
        ],
        max_tokens=400,
    )

    return {"answer": response.strip(), "status": "ok"}


@router.post("/rooms/{room_id}/ai/email", tags=["AI"])
async def generate_email(
    room_id: str,
    user: dict = Depends(get_current_user),
):
    """Generate a follow-up email for the meeting."""
    transcript_text = transcript_manager.get_transcript_text(room_id)
    if not transcript_text.strip():
        return {"email": "", "status": "empty"}

    participants = participant_manager.get_room_participants(room_id)
    participant_names = [p.display_name for p in participants]
    room = room_manager.get_room(room_id)
    meeting_title = room.title if room else "Meeting"

    response = await _ai_chat(
        [
            {
                "role": "system",
                "content": "Generate a professional meeting follow-up email with summary, decisions, and action items.",
            },
            {
                "role": "user",
                "content": f"Meeting: {meeting_title}\nParticipants: {', '.join(participant_names)}\n\nTranscript:\n{transcript_text[-3000:]}\n\nGenerate email draft.",
            },
        ],
        max_tokens=600,
    )

    return {"email": response.strip(), "status": "ok"}


@router.get("/rooms/{room_id}/search", tags=["Search"])
async def search_meeting(
    room_id: str,
    q: str,
    user: dict = Depends(get_current_user),
):
    """Search meeting transcript, chat, and AI state."""
    query = q.lower().strip()
    if not query:
        return {"results": [], "total": 0}

    results = []

    # Search transcript
    transcript_entries = transcript_manager.get_transcript(room_id, limit=500)
    for entry in transcript_entries:
        if query in entry.text.lower() or query in entry.speaker_name.lower():
            results.append(
                {
                    "type": "transcript",
                    "text": entry.text,
                    "speaker": entry.speaker_name,
                    "timestamp_ms": entry.timestamp_ms,
                    "score": 1.0,
                }
            )

    # Search chat
    chat_messages = chat_manager.get_messages(room_id, limit=200)
    for msg in chat_messages:
        if query in msg.content.lower() or query in msg.sender_name.lower():
            results.append(
                {
                    "type": "chat",
                    "text": msg.content,
                    "sender": msg.sender_name,
                    "time": msg.created_at.isoformat(),
                    "score": 1.0,
                }
            )

    # Search AI state
    ai_state = transcript_manager.get_ai_state(room_id)
    if ai_state:
        for item in ai_state.action_items:
            if query in item.lower():
                results.append({"type": "action_item", "text": item, "score": 0.9})
        for item in ai_state.decisions:
            if query in item.lower():
                results.append({"type": "decision", "text": item, "score": 0.9})
        for item in ai_state.risks:
            if query in item.lower():
                results.append({"type": "risk", "text": item, "score": 0.9})

    return {"results": results[:50], "total": len(results)}


# ── WebSocket ─────────────────────────────────────────────────────────


@router.websocket("/ws/rooms/{room_id}")
async def meeting_websocket(websocket: WebSocket, room_id: str, token: str = ""):
    """WebSocket endpoint for real-time meeting communication."""
    from app.core.security import decode_access_token

    try:
        user = decode_access_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    room = room_manager.get_room(room_id)
    if not room:
        await websocket.close(code=4004, reason="Room not found")
        return

    # The actual access-control fix: this handler previously accepted any valid JWT and sent
    # the full room_state regardless of waiting-room status — meaning a participant the host
    # hadn't admitted yet could already see the transcript, chat, and every other participant
    # over the WS, even with `waiting_room=True` set on the room. Real-time signaling/media
    # only ever happens over this connection, so the REST-level waiting-room state meant
    # nothing without this check. A still-waiting participant gets a `waiting_room` status
    # message and the connection is closed immediately rather than held open in a half-state
    # — the frontend polls GET /rooms/{room_id} (see meeting-room.tsx's WaitingRoomScreen)
    # to detect admission and opens a fresh connection once admitted, the standard, simple
    # pattern for an approval-gated connection rather than keeping one socket alive across
    # a state transition.
    my_participant = next(
        (p for p in participant_manager.get_room_participants(room_id) if p.user_id == user["sub"]),
        None,
    )
    # A more serious version of the same gap, found in the same audit pass: the check above
    # only handles the case where the user IS a recognized participant in waiting-room state.
    # If they're not a participant at all — never called POST /rooms/{id}/join for this
    # specific room — `my_participant` is None, the `if my_participant and ...` condition is
    # therefore False, and the code fell straight through to full WS access. Any user with a
    # valid platform JWT (not necessarily anything to do with this meeting) could connect
    # directly to any room's live WebSocket by room_id alone, completely bypassing the
    # password check, room-lock check, and waiting-room logic that all live in the /join
    # REST route — none of which this WS endpoint ever re-checks itself. Requiring a real
    # participant record closes this: you must have actually joined (and been through
    # whatever gate that route enforces) before this socket will do anything for you.
    if not my_participant:
        await websocket.close(code=4003, reason="Not a participant of this meeting — join via POST /join first")
        return
    if my_participant.state == ParticipantState.IN_WAITING_ROOM:
        await websocket.accept()
        await websocket.send_json({"type": "waiting_room", "status": "waiting"})
        await websocket.close(code=4003, reason="Waiting for host approval")
        return

    connection_id = str(uuid.uuid4())
    audio_session = AudioTranscriptionSession()
    # Found during a security audit: there was no rate limiting anywhere on this WS message
    # loop — a malicious or buggy client could send messages as fast as the network allowed,
    # with every message type (chat, whiteboard strokes, reactions, signaling) all incurring
    # real server-side work (broadcast fan-out to every other connection in the room). 60
    # messages/second per connection is generous: real continuous mic audio is ~4
    # messages/second (one ~256ms frame at a time — see audio_chunk's own size-cap comment),
    # and every other message type fires on discrete user actions (one chat send, one stroke
    # completion, one reaction click), not continuously.
    recent_message_times: deque[float] = deque(maxlen=200)
    RATE_LIMIT_PER_SECOND = 60
    await websocket.accept()

    # Track connection with room association
    if not hasattr(websocket.app.state, "meeting_connections"):
        websocket.app.state.meeting_connections = {}
    if not hasattr(websocket.app.state, "room_connections"):
        websocket.app.state.room_connections = {}

    websocket.app.state.meeting_connections[connection_id] = {
        "ws": websocket,
        "room_id": room_id,
        "user_id": user["sub"],
    }

    if room_id not in websocket.app.state.room_connections:
        websocket.app.state.room_connections[room_id] = set()
    websocket.app.state.room_connections[room_id].add(connection_id)

    # Send initial state
    participants = participant_manager.get_room_participants(room_id)
    transcript = transcript_manager.get_transcript(room_id)
    ai_state = transcript_manager.get_ai_state(room_id)

    # Attach each participant's WS connection_id (a transport-layer concept the Participant
    # model itself doesn't track) so a newly-joining client can immediately open WebRTC
    # connections to everyone already in the room, not just to people who join after them.
    # Real gap fixed here: this mapping previously didn't exist anywhere, and neither did the
    # participant_joined/participant_left broadcasts below — the frontend already had a
    # handler for both message types (see meeting-room.tsx's handleWSMessage), but nothing on
    # this side ever sent them, so it was dead code that looked wired but never fired.
    user_id_to_connection_id = {
        info["user_id"]: cid
        for cid, info in getattr(websocket.app.state, "meeting_connections", {}).items()
        if info.get("room_id") == room_id
    }

    def participant_payload(p: Any) -> dict:
        payload = p.to_dict()
        cid = user_id_to_connection_id.get(p.user_id)
        if cid:
            payload["connection_id"] = cid
        return payload

    await websocket.send_json(
        {
            "type": "room_state",
            "room": room.to_dict(),
            "participants": [participant_payload(p) for p in participants],
            "transcript": [e.to_dict() for e in transcript[-50:]],
            "ai_state": ai_state.to_dict() if ai_state else None,
            "connection_id": connection_id,
            "whiteboard_strokes": [s.to_dict() for s in whiteboard_manager.get_strokes(room_id)],
        }
    )

    # Tell everyone already in the room that this connection just joined — see comment above
    # on why this previously never happened. Includes connection_id so existing peers can
    # immediately initiate (or wait to receive) a WebRTC offer addressed to this connection.
    my_participant = next((p for p in participants if p.user_id == user["sub"]), None)
    if my_participant:
        await _broadcast_to_room(
            websocket.app.state,
            room_id,
            {
                "type": "participant_joined",
                "participant": {**my_participant.to_dict(), "connection_id": connection_id},
            },
            exclude=connection_id,
        )


    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # Rate limit check — see this connection's setup above for why 60/sec and why
            # this exists at all. Single clear sliding-window count: how many of the last
            # `maxlen` message timestamps fall within the last second. Recomputed fresh each
            # time rather than maintained incrementally — deque length is capped at 200, so
            # this sum is cheap, and a single obviously-correct check beats two overlapping
            # ones that are harder to verify don't disagree with each other at the edges.
            now = time.monotonic()
            recent_message_times.append(now)
            window_start = now - 1.0
            recent_count = sum(1 for t in recent_message_times if t >= window_start)
            if recent_count > RATE_LIMIT_PER_SECOND:
                # Drop this one silently rather than closing the connection outright — a
                # single network hiccup causing a small queued burst shouldn't disconnect
                # someone; only sustained abuse keeps tripping this on every iteration.
                continue

            if msg_type == "signalling":
                await signalling_manager.route_message(
                    room_id=room_id,
                    sender_id=connection_id,
                    message=data.get("data", {}),
                    broadcast_fn=lambda rid, msg, exclude=None: _broadcast_to_room(
                        websocket.app.state, rid, msg, exclude
                    ),
                    send_fn=lambda tid, msg: _send_to_connection(
                        websocket.app.state, tid, msg
                    ),
                )
            elif msg_type == "chat":
                content = str(data.get("content", ""))[:5000]
                if not content.strip():
                    continue
                msg = chat_manager.add_message(
                    room_id=room_id,
                    sender_id=user["sub"],
                    sender_name=user.get("full_name", "User"),
                    content=content,
                )
                await _broadcast_to_room(
                    websocket.app.state,
                    room_id,
                    SignallingMessage.chat_message(msg.to_dict()),
                )
            elif msg_type == "transcript":
                # Real-time transcript from speech-to-text
                speaker_name = data.get(
                    "speaker_name", user.get("full_name", "Speaker")
                )
                text = data.get("text", "")
                kind = data.get("kind", "statement")

                if text.strip():
                    entry = transcript_manager.add_transcript(
                        room_id=room_id,
                        speaker_id=user["sub"],
                        speaker_name=speaker_name,
                        text=text,
                        kind=kind,
                    )
                    await _broadcast_to_room(
                        websocket.app.state,
                        room_id,
                        {"type": "transcript", "entry": entry.to_dict()},
                    )
                    await _auto_translate_entry(websocket.app.state, room_id, entry)
            elif msg_type == "audio_chunk":
                # The actual mic-audio-to-transcript link: see audio_transcription.py's
                # module docstring for why this didn't exist before. `pcm` is base64-encoded
                # PCM16 mono audio at 16kHz (see apps/web's mic capture, which sends frames
                # in exactly this shape). VAD-segmented per-utterance — most frames just
                # buffer silently and return nothing; only a completed utterance produces a
                # transcript entry.
                #
                # Size cap added during a security audit: real frames from the actual capture
                # code are ~11KB base64 (4096 samples x 2 bytes, PCM16, then base64's ~33%
                # inflation) — 256KB is generous headroom for any legitimate variance while
                # rejecting an arbitrarily large payload before paying the cost of
                # base64-decoding it at all.
                pcm_b64 = data.get("pcm", "")
                if pcm_b64 and isinstance(pcm_b64, str) and len(pcm_b64) <= 256_000:
                    utterance = await audio_session.feed_frame(pcm_b64)
                    if utterance:
                        text = await transcribe_via_ai_server(utterance)
                        if text:
                            speaker_name = user.get("full_name", "Speaker")
                            entry = transcript_manager.add_transcript(
                                room_id=room_id,
                                speaker_id=user["sub"],
                                speaker_name=speaker_name,
                                text=text,
                                kind="statement",
                            )
                            await _broadcast_to_room(
                                websocket.app.state,
                                room_id,
                                {"type": "transcript", "entry": entry.to_dict()},
                            )
                            await _auto_translate_entry(websocket.app.state, room_id, entry)
            elif msg_type == "translation":
                # Translation for a transcript entry
                transcript_id = data.get("transcript_id", "")
                language = data.get("language", "en")
                translated_text = data.get("translated_text", "")

                if transcript_id and translated_text:
                    trans_entry = transcript_manager.add_translation(
                        transcript_id=transcript_id,
                        language=language,
                        translated_text=translated_text,
                    )
                    await _broadcast_to_room(
                        websocket.app.state,
                        room_id,
                        {"type": "translation", "translation": trans_entry.to_dict()},
                    )
            elif msg_type == "translate_transcript":
                # Realtime translation of a transcript entry into multiple languages
                transcript_id = data.get("transcript_id", "")
                text = data.get("text", "")

                if transcript_id and text:
                    from app.services.translation_pipeline import translation_pipeline

                    translations = await translation_pipeline.translate_transcript(
                        transcript_id=transcript_id,
                        text=text,
                        room_id=room_id,
                    )
                    for lang, translated in translations.items():
                        trans_entry = transcript_manager.add_translation(
                            transcript_id=transcript_id,
                            language=lang,
                            translated_text=translated,
                        )
                        await _broadcast_to_room(
                            websocket.app.state,
                            room_id,
                            {
                                "type": "translation",
                                "translation": trans_entry.to_dict(),
                                "target_user": None,  # broadcast to all
                            },
                        )
            elif msg_type == "set_language":
                # Set user's preferred language for the meeting
                from app.services.translation_pipeline import translation_pipeline

                lang = data.get("language", "en")
                translation_pipeline.set_user_language(room_id, user["sub"], lang)
                await websocket.send_json(
                    {
                        "type": "language_set",
                        "language": lang,
                        "room_languages": translation_pipeline.get_room_languages(
                            room_id
                        ),
                    }
                )
            elif msg_type == "ai_update":
                # AI state update broadcast
                ai_data = data.get("ai_state", {})
                if ai_data:
                    transcript_manager.update_ai_state(room_id, **ai_data)
                    await _broadcast_to_room(
                        websocket.app.state,
                        room_id,
                        {"type": "ai_update", "ai_state": ai_data},
                    )
            elif msg_type == "media_state":
                for p in participant_manager.get_room_participants(room_id):
                    if p.user_id == user["sub"]:
                        participant_manager.update_media(
                            p.id,
                            audio_enabled=data.get("audio_enabled"),
                            video_enabled=data.get("video_enabled"),
                            screen_sharing=data.get("screen_sharing"),
                        )
                        await _broadcast_to_room(
                            websocket.app.state,
                            room_id,
                            SignallingMessage.media_state_changed(p.id, data),
                        )
                        break
            elif msg_type == "hand":
                raised = data.get("raised", False)
                for p in participant_manager.get_room_participants(room_id):
                    if p.user_id == user["sub"]:
                        if raised:
                            p.raise_hand()
                        else:
                            p.lower_hand()
                        await _broadcast_to_room(
                            websocket.app.state,
                            room_id,
                            SignallingMessage.hand_raised(p.id, raised),
                        )
                        break
            elif msg_type == "emoji":
                emoji = str(data.get("emoji", ""))[:16]
                if not emoji:
                    continue
                await _broadcast_to_room(
                    websocket.app.state,
                    room_id,
                    SignallingMessage.emoji_reaction(
                        connection_id, emoji
                    ),
                )
            elif msg_type == "whiteboard_draw":
                # New feature surface, not a missing wire on existing code (see §26 of the
                # merge report for why this was sequenced after the bug-fix-shaped items) —
                # broadcasts over this same existing WebSocket, no separate whiteboard server.
                #
                # Input validation added during a security audit (§28+): none of this was
                # bounded before — a malicious or buggy client could send a single message
                # with a multi-megabyte `points` array or `text` string, or a `tool` value
                # outside the known set, and it would be accepted, stored, and broadcast to
                # everyone in the room as-is. These limits are generous for any real drawing
                # action (a single mouse-drag stroke is realistically tens to low hundreds of
                # points, not tens of thousands) while closing the unbounded-payload vector.
                raw_points = data.get("points", [])
                raw_tool = data.get("tool", "pencil")
                raw_text = data.get("text")
                if raw_tool not in ("pencil", "rectangle", "ellipse", "line", "text", "eraser"):
                    continue
                if not isinstance(raw_points, list) or len(raw_points) > 20000:
                    continue
                if raw_text is not None and (not isinstance(raw_text, str) or len(raw_text) > 2000):
                    continue
                try:
                    safe_width = min(max(float(data.get("width", 3.0)), 0.5), 50.0)
                except (TypeError, ValueError):
                    safe_width = 3.0
                stroke = whiteboard_manager.add_stroke(
                    room_id=room_id,
                    user_id=user["sub"],
                    tool=raw_tool,
                    points=raw_points,
                    color=str(data.get("color", "#000000"))[:32],
                    width=safe_width,
                    text=raw_text,
                )
                await _broadcast_to_room(
                    websocket.app.state,
                    room_id,
                    {"type": "whiteboard_stroke", "stroke": stroke.to_dict()},
                )
            elif msg_type == "whiteboard_undo":
                stroke = whiteboard_manager.undo(room_id)
                if stroke:
                    await _broadcast_to_room(
                        websocket.app.state,
                        room_id,
                        {"type": "whiteboard_undo", "stroke_id": stroke.id},
                    )
            elif msg_type == "whiteboard_redo":
                stroke = whiteboard_manager.redo(room_id)
                if stroke:
                    await _broadcast_to_room(
                        websocket.app.state,
                        room_id,
                        {"type": "whiteboard_stroke", "stroke": stroke.to_dict()},
                    )
            elif msg_type == "whiteboard_clear":
                whiteboard_manager.clear(room_id)
                await _broadcast_to_room(
                    websocket.app.state,
                    room_id,
                    {"type": "whiteboard_clear"},
                )
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup connection
        if hasattr(websocket.app.state, "meeting_connections"):
            websocket.app.state.meeting_connections.pop(connection_id, None)
        if hasattr(websocket.app.state, "room_connections"):
            room_conns = websocket.app.state.room_connections.get(room_id, set())
            room_conns.discard(connection_id)
            if not room_conns:
                websocket.app.state.room_connections.pop(room_id, None)

        # Remove participant
        left_participant_id = None
        for p in participant_manager.get_room_participants(room_id):
            if p.user_id == user["sub"]:
                left_participant_id = p.id
                participant_manager.remove_participant(p.id)
                break
        room = room_manager.get_room(room_id)
        if room:
            room.participants_count = participant_manager.get_active_count(room_id)

        # Mirror of the participant_joined broadcast above — tells remaining peers to close
        # their RTCPeerConnection to this one rather than leaving it open and silently dead.
        await _broadcast_to_room(
            websocket.app.state,
            room_id,
            {
                "type": "participant_left",
                "participant_id": left_participant_id,
                "connection_id": connection_id,
            },
        )

        # Broadcast participant left
        await _broadcast_to_room(
            websocket.app.state,
            room_id,
            SignallingMessage.participant_left(connection_id, user["sub"]),
        )


async def _broadcast_to_room(
    state: Any, room_id: str, message: dict, exclude: str | None = None
):
    """Broadcast a message to all connections in a specific room."""
    room_conns = getattr(state, "room_connections", {}).get(room_id, set())
    all_conns = getattr(state, "meeting_connections", {})

    for cid in room_conns:
        if cid == exclude:
            continue
        conn_info = all_conns.get(cid)
        if conn_info:
            ws = conn_info["ws"]
            try:
                await ws.send_json(message)
            except Exception:
                pass


async def _auto_translate_entry(state: Any, room_id: str, entry: Any) -> None:
    """Auto-translates a freshly added transcript entry into every language currently
    selected by someone in the room, and broadcasts each result. This is what actually
    closes the loop described in this product's own architecture docs (Mic -> ... ->
    Translation -> Frontend): previously a client had to explicitly send a
    `translate_transcript` WS message per entry for this to happen at all, and nothing ever
    did — translation only worked if you built a client that manually triggered it. Calling
    it automatically here means every transcript entry — whether from the audio_chunk
    pipeline above or the manual `transcript` message type — gets translated the moment it's
    created, with no extra step required of any client.

    Best-effort: a translation failure (ai-server down, language not supported, etc.) is
    logged and skipped rather than raised — losing one entry's translation shouldn't break
    the live transcript itself, which already broadcast successfully before this is called.
    """
    languages = translation_pipeline.get_room_languages(room_id)
    if not languages:
        return
    try:
        translations = await translation_pipeline.translate_transcript(
            transcript_id=entry.id, text=entry.text, room_id=room_id
        )
    except Exception:
        import structlog

        structlog.get_logger().warning("auto_translate_failed", room_id=room_id, transcript_id=entry.id)
        return

    for lang, translated_text in translations.items():
        trans_entry = transcript_manager.add_translation(
            transcript_id=entry.id, language=lang, translated_text=translated_text
        )
        await _broadcast_to_room(
            state, room_id, {"type": "translation", "translation": trans_entry.to_dict()}
        )


async def _send_to_connection(state: Any, target_id: str, message: dict):
    """Send a message to a specific connection."""
    all_conns = getattr(state, "meeting_connections", {})
    conn_info = all_conns.get(target_id)
    if conn_info:
        ws = conn_info["ws"]
        try:
            await ws.send_json(message)
        except Exception:
            pass


# ── Status ────────────────────────────────────────────────────────────


@router.get("/status", response_model=MeetingStatusResponse, tags=["Status"])
async def meeting_status(user: dict = Depends(get_current_user)):
    """Get meeting server status."""
    return MeetingStatusResponse(
        rooms=room_manager.get_status(),
        participants=participant_manager.get_status(),
        chat=chat_manager.get_status(),
        recording=recording_manager.get_status(),
    )


# ── Email Generation ─────────────────────────────────────────────────


@router.post("/rooms/{room_id}/email/generate", tags=["Email"])
async def generate_meeting_email(room_id: str, user: dict = Depends(get_current_user)):
    """Generate a follow-up email for the meeting."""
    from app.services.email_generation import generate_meeting_email as gen_email

    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    transcript_text = transcript_manager.get_transcript_text(room_id)
    if not transcript_text.strip():
        return {"email": "", "status": "empty"}

    participants = participant_manager.get_room_participants(room_id)
    ai_state = transcript_manager.get_ai_state(room_id)

    participant_data = [
        {
            "name": p.display_name,
            "display_name": p.display_name,
            "email": "",
        }
        for p in participants
    ]

    email_data = gen_email(
        meeting_id=room_id,
        meeting_title=room.title,
        participants=participant_data,
        transcript=transcript_text,
        summary=ai_state.summary if ai_state else "",
        action_items=ai_state.action_items if ai_state else [],
        decisions=ai_state.decisions if ai_state else [],
        follow_ups=ai_state.follow_ups if ai_state else [],
        risks=ai_state.risks if ai_state else [],
    )

    return {"email": email_data, "status": "ok"}


# ── Meeting Export ───────────────────────────────────────────────────


@router.get("/rooms/{room_id}/export/{format}", tags=["Export"])
async def export_meeting(
    room_id: str,
    format: str,
    user: dict = Depends(get_current_user),
):
    """Export meeting in specified format (json, txt, markdown, html)."""
    from app.services.meeting_export import export_meeting as do_export
    from fastapi.responses import PlainTextResponse, HTMLResponse

    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if format not in ("json", "txt", "markdown", "html"):
        raise HTTPException(
            status_code=400, detail="Format must be json, txt, markdown, or html"
        )

    transcript_entries = transcript_manager.get_transcript(room_id, limit=5000)
    participants = participant_manager.get_room_participants(room_id)
    ai_state = transcript_manager.get_ai_state(room_id)

    data = {
        "participants": [
            {"display_name": p.display_name, "name": p.display_name}
            for p in participants
        ],
        "transcript": [e.to_dict() for e in transcript_entries],
        "summary": ai_state.summary if ai_state else "",
        "action_items": ai_state.action_items if ai_state else [],
        "decisions": ai_state.decisions if ai_state else [],
        "risks": ai_state.risks if ai_state else [],
        "follow_ups": ai_state.follow_ups if ai_state else [],
        "sentiment": ai_state.sentiment if ai_state else "neutral",
        "chat_messages": [
            m.to_dict() for m in chat_manager.get_messages(room_id, limit=500)
        ],
        "duration_minutes": room.duration_minutes
        if hasattr(room, "duration_minutes")
        else 0,
        "metadata": {
            "room_type": room.type.value,
            "created_at": room.created_at.isoformat(),
        },
    }

    result = do_export(room_id, room.title, format, data)

    if format == "html":
        return HTMLResponse(content=result["content"])
    elif format in ("txt", "markdown"):
        return PlainTextResponse(
            content=result["content"],
            headers={
                "Content-Disposition": f'attachment; filename="{result["filename"]}"'
            },
        )
    else:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            content=result["data"],
            headers={
                "Content-Disposition": f'attachment; filename="{result["filename"]}"'
            },
        )


# ── Translation Preferences ──────────────────────────────────────────


@router.post("/rooms/{room_id}/language", tags=["Translation"])
async def set_user_language(
    room_id: str, data: dict, user: dict = Depends(get_current_user)
):
    """Set user's preferred language for live translation."""
    from app.services.translation_pipeline import translation_pipeline

    language = data.get("language", "en")
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    pref = translation_pipeline.set_user_language(room_id, user["sub"], language)
    return {
        "status": "ok",
        "language": pref.target_language,
        "room_languages": translation_pipeline.get_room_languages(room_id),
    }


@router.get("/rooms/{room_id}/languages", tags=["Translation"])
async def get_room_languages(room_id: str, user: dict = Depends(get_current_user)):
    """Get all languages needed for a room based on participant preferences."""
    from app.services.translation_pipeline import translation_pipeline

    return {
        "languages": translation_pipeline.get_room_languages(room_id),
        "status": translation_pipeline.get_status(),
    }


@router.get("/health", tags=["Health"])
async def health():
    """Meeting server health check."""
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
        "transcript": transcript_manager.get_status(),
    }
