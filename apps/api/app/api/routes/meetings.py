import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import MeetingAgentOrchestrator
from app.core.security import get_current_user_id
from app.database.session import get_db
from app.models.entities import Meeting, MeetingShareLink, TranscriptEvent
from app.schemas.meeting import AgentResult, MeetingCreate, MeetingOut, TranscriptChunk
from app.schemas.share_link import CreateShareLinkRequest, ShareLinkCreated, ShareLinkOut
from app.services.llm import LLMProviderError, get_llm_provider
from app.services.memory import append_action_items, append_follow_ups, format_context_block, get_recent_context
from app.services.notifications import notify_summary_ready
from app.services.permissions import get_membership, primary_workspace_id, workspace_ids_for_user
from app.services.prompts import get as get_prompt
from app.services.rag import RagError, RagPipeline
from app.services.scoring import compute_meeting_score
from app.services.share_links import create_share_link
from app.services.usage import UsageEvent, record_usage

logger = logging.getLogger("convopilot.routes.meetings")

router = APIRouter(prefix="/meetings", tags=["meetings"])
orchestrator = MeetingAgentOrchestrator()
rag = RagPipeline()



def _get_viewable_meeting(meeting_id: str, user_id: str, db: Session) -> Meeting:
    """Any member of the meeting's workspace can view it — this is the "shared meeting
    library" behavior: a teammate can read a meeting they didn't run. Falls back to a strict
    owner check for meetings with no workspace_id (shouldn't happen after migration 0005's
    backfill, but the fallback costs nothing and avoids a meeting becoming unviewable by
    anyone if that invariant is ever violated)."""
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if meeting.workspace_id:
        if not get_membership(db, meeting.workspace_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this meeting's workspace")
    elif meeting.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your meeting")
    return meeting


def _get_writable_meeting(meeting_id: str, user_id: str, db: Session) -> Meeting:
    """Only the person who actually started this specific live session can post transcript
    chunks to it — distinct from viewing, which any workspace member can do. A shared meeting
    library doesn't mean teammates can inject lines into a call they're not running."""
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if meeting.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the meeting's owner can do this")
    return meeting


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_meeting(
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    workspace_id = payload.workspace_id or primary_workspace_id(db, user_id)
    if payload.workspace_id and not get_membership(db, payload.workspace_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of that workspace")

    meeting = Meeting(title=payload.title, mode=payload.mode, owner_id=user_id, workspace_id=workspace_id)
    db.add(meeting)
    db.commit()
    return {"id": meeting.id, "title": meeting.title, "mode": meeting.mode, "workspace_id": workspace_id}


@router.get("", response_model=list[MeetingOut])
async def list_meetings(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[MeetingOut]:
    """Returns meetings across every workspace the caller belongs to — for most users that's
    just their own personal workspace (so this looks identical to "my meetings" as before
    workspaces existed), but a teammate added to a shared workspace now sees meetings their
    workspace-mates ran too, not just their own. See _get_viewable_meeting for the same
    membership check enforced on individual meeting reads."""
    workspace_ids = workspace_ids_for_user(db, user_id)
    meetings = (
        db.query(Meeting)
        .filter(Meeting.workspace_id.in_(workspace_ids))
        .order_by(Meeting.created_at.desc())
        .all()
    )
    return [
        MeetingOut(
            id=m.id,
            title=m.title,
            mode=m.mode,
            created_at=m.created_at,
            has_summary=m.summary is not None,
            workspace_id=m.workspace_id,
            owner_id=m.owner_id,
        )
        for m in meetings
    ]


@router.post("/{meeting_id}/transcript", response_model=AgentResult)
async def transcript_event(
    meeting_id: str,
    chunk: TranscriptChunk,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> AgentResult:
    meeting = _get_writable_meeting(meeting_id, user_id, db)
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
    return result


@router.get("/{meeting_id}/summary")
async def meeting_summary(
    meeting_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    meeting = _get_viewable_meeting(meeting_id, user_id, db)

    if meeting.summary and meeting.intelligence:
        return {
            "meeting_id": meeting_id,
            "summary": meeting.summary,
            "decisions": meeting.intelligence.get("decisions", []),
            "risks": meeting.intelligence.get("risks", []),
            "action_items": meeting.intelligence.get("action_items", []),
        }

    events = (
        db.query(TranscriptEvent)
        .filter(TranscriptEvent.meeting_id == meeting_id)
        .order_by(TranscriptEvent.timestamp_ms)
        .all()
    )
    if not events:
        return {
            "meeting_id": meeting_id,
            "summary": "No transcript recorded yet.",
            "decisions": [],
            "risks": [],
            "action_items": (meeting.intelligence or {}).get("action_items", []),
        }

    transcript_text = format_context_block([f"{e.speaker}: {e.text}" for e in events])
    prompt = get_prompt("meeting_summary").render(transcript=transcript_text)
    try:
        provider = get_llm_provider()
        response = await provider.complete("Follow the instructions precisely.", prompt, max_tokens=600)
    except LLMProviderError as exc:
        logger.warning("Summary generation unavailable: %s", exc)
        return {
            "meeting_id": meeting_id,
            "summary": f"[Summary unavailable: {exc}]",
            "decisions": [],
            "risks": [],
            "action_items": (meeting.intelligence or {}).get("action_items", []),
        }

    record_usage(
        db,
        UsageEvent(
            operation="chat_completion",
            provider=response.provider,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=response.latency_ms,
        ),
        owner_id=user_id,
        meeting_id=meeting_id,
    )

    try:
        parsed = json.loads(response.text)
        summary, decisions, risks = parsed.get("summary", ""), parsed.get("decisions", []), parsed.get("risks", [])
    except json.JSONDecodeError:
        # Model didn't return valid JSON — surface the raw text rather than silently losing it.
        logger.warning("Summary model returned non-JSON output for meeting %s", meeting_id)
        return {
            "meeting_id": meeting_id,
            "summary": response.text,
            "decisions": [],
            "risks": [],
            "action_items": (meeting.intelligence or {}).get("action_items", []),
        }

    meeting.summary = summary
    meeting.intelligence = {**(meeting.intelligence or {}), "decisions": decisions, "risks": risks}
    db.commit()
    # Notify the meeting's actual owner — not necessarily the caller, since any workspace
    # member can trigger summary generation on a shared meeting via _get_viewable_meeting.
    notify_summary_ready(db, meeting.owner_id, meeting_id, meeting.title)

    # Index for Universal Meeting Search — same collection/search surface as uploaded
    # documents (see RagPipeline docstring). Best-effort: a failure here shouldn't break the
    # summary response the user is actually waiting on, just means this meeting won't show up
    # in search until the summary is regenerated.
    try:
        index_workspace = meeting.workspace_id or primary_workspace_id(db, user_id)
        if index_workspace:
            _, index_usage = await rag.ingest_text(index_workspace, f"meeting-{meeting_id}", summary, meeting_id=meeting_id)
            for event in index_usage:
                record_usage(db, event, owner_id=user_id, meeting_id=meeting_id)
    except RagError as exc:
        logger.warning("Could not index meeting %s for search: %s", meeting_id, exc)

    return {
        "meeting_id": meeting_id,
        "summary": summary,
        "decisions": decisions,
        "risks": risks,
        "action_items": meeting.intelligence.get("action_items", []),
    }


@router.get("/{meeting_id}/detail")
async def meeting_detail(
    meeting_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Single aggregate call for the Meeting Deep Dive page — transcript, AI cards
    (summary/decisions/risks/action items/follow-ups/questions), and a heuristic score, all in
    one response instead of the frontend making 4-5 separate calls. Doesn't generate a summary
    if one doesn't exist yet (that's a real LLM call with real cost — this endpoint is read-
    only against what's already there; call GET /summary first if summary is null below).

    "Speaking Time" and "Participation" from the original Meeting Scorecard request are not
    in this response — see services/scoring.py for why (no real speaker-diarization data
    exists to compute them from)."""
    meeting = _get_viewable_meeting(meeting_id, user_id, db)
    events = (
        db.query(TranscriptEvent)
        .filter(TranscriptEvent.meeting_id == meeting_id)
        .order_by(TranscriptEvent.timestamp_ms)
        .all()
    )
    intelligence = meeting.intelligence or {}
    decisions = intelligence.get("decisions", [])
    risks = intelligence.get("risks", [])
    action_items = intelligence.get("action_items", [])
    follow_ups = intelligence.get("follow_ups", [])
    questions = [{"speaker": e.speaker, "text": e.text, "timestamp_ms": e.timestamp_ms} for e in events if e.kind == "question"]
    score = compute_meeting_score(decisions=decisions, action_items=action_items, risks=risks)

    return {
        "meeting_id": meeting_id,
        "title": meeting.title,
        "mode": meeting.mode,
        "created_at": meeting.created_at.isoformat(),
        "transcript": [
            {"speaker": e.speaker, "text": e.text, "kind": e.kind, "timestamp_ms": e.timestamp_ms} for e in events
        ],
        "summary": meeting.summary,
        "decisions": decisions,
        "risks": risks,
        "action_items": action_items,
        "follow_ups": follow_ups,
        "questions": questions,
        "score": {
            "overall": score.overall,
            "decisiveness": score.decisiveness,
            "productivity": score.productivity,
            "risk_penalty": score.risk_penalty,
            "note": score.breakdown_note,
        },
    }


@router.post("/{meeting_id}/share-links", response_model=ShareLinkCreated, status_code=status.HTTP_201_CREATED)
async def create_share_link_endpoint(
    meeting_id: str,
    payload: CreateShareLinkRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Owner-only, not just any workspace member with view access — sharing a meeting outside
    the workspace entirely is a higher-stakes action than viewing it inside the team."""
    meeting = _get_writable_meeting(meeting_id, user_id, db)
    if payload.expires_in_hours < 1 or payload.expires_in_hours > 24 * 90:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="expires_in_hours must be between 1 and 2160 (90 days).")
    link, raw_token = create_share_link(db, meeting.id, user_id, expires_in_hours=payload.expires_in_hours)
    return {
        "id": link.id,
        "expires_at": link.expires_at,
        "revoked": link.revoked,
        "created_at": link.created_at,
        "token": raw_token,
    }


@router.get("/{meeting_id}/share-links", response_model=list[ShareLinkOut])
async def list_share_links(
    meeting_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[MeetingShareLink]:
    _get_writable_meeting(meeting_id, user_id, db)
    return db.query(MeetingShareLink).filter(MeetingShareLink.meeting_id == meeting_id).order_by(MeetingShareLink.created_at.desc()).all()


@router.delete("/{meeting_id}/share-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share_link(
    meeting_id: str,
    link_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    _get_writable_meeting(meeting_id, user_id, db)
    link = db.get(MeetingShareLink, link_id)
    if not link or link.meeting_id != meeting_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    link.revoked = True
    db.commit()
