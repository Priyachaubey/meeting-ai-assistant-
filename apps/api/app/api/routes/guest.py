from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.limiter import limiter
from app.models.entities import Meeting, TranscriptEvent
from app.schemas.share_link import GuestMeetingView
from app.services.share_links import ShareLinkError, resolve_share_link

router = APIRouter(prefix="/guest", tags=["guest"])


@router.get("/meetings/{token}", response_model=GuestMeetingView)
@limiter.limit("20/minute")
async def guest_view_meeting(token: str, request: Request, db: Session = Depends(get_db)) -> dict:
    """No auth dependency at all — the token IS the credential, same model as a password-
    reset link. Rate-limited per IP (not per-token: an attacker rotating tokens against one
    IP is the threat model this guards against, not a legitimate user retrying their own
    link). Returns a narrow GuestMeetingView, not the full authenticated meeting detail —
    no owner_id, no workspace_id, nothing beyond what a guest reading a shared outcome needs."""
    try:
        link = resolve_share_link(db, token, ip_address=request.client.host if request.client else None)
    except ShareLinkError as exc:
        # 404, not 400/403 — don't confirm to a guesser whether a token format was "close"
        # to valid; invalid, expired, and revoked all look identical from the outside.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    meeting = db.get(Meeting, link.meeting_id)
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    events = (
        db.query(TranscriptEvent)
        .filter(TranscriptEvent.meeting_id == meeting.id)
        .order_by(TranscriptEvent.timestamp_ms)
        .all()
    )
    intelligence = meeting.intelligence or {}
    return {
        "title": meeting.title,
        "created_at": meeting.created_at,
        "transcript": [
            {"speaker": e.speaker, "text": e.text, "kind": e.kind, "timestamp_ms": e.timestamp_ms} for e in events
        ],
        "summary": meeting.summary,
        "decisions": intelligence.get("decisions", []),
        "risks": intelligence.get("risks", []),
        "action_items": intelligence.get("action_items", []),
        "follow_ups": intelligence.get("follow_ups", []),
    }
