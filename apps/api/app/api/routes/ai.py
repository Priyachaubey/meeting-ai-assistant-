import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.database.session import get_db
from app.models.entities import Document, Meeting
from app.services.llm import LLMProviderError, get_llm_provider
from app.services.permissions import get_membership, primary_workspace_id, workspace_ids_for_user
from app.services.prompts import get as get_prompt
from app.services.rag import RagError, RagPipeline
from app.services.usage import UsageEvent, get_usage_summary_last_n_days, record_usage

logger = logging.getLogger("convopilot.routes.ai")

router = APIRouter(prefix="/ai", tags=["ai"])
rag = RagPipeline()

GENERIC_SYSTEM_PROMPT = "Follow the instructions in the user message precisely. Output exactly what is asked for, nothing else."


def _meeting_or_404(db: Session, meeting_id: str, user_id: str) -> Meeting:
    """Same access level as meetings.py's _get_viewable_meeting: any member of the meeting's
    workspace can generate a follow-up/email from it — this reads and derives from a meeting,
    it doesn't run or modify the live session, so it belongs at "view" access, not "owner
    only". Meetings with no workspace_id (shouldn't happen post-migration-0005, see that
    file's docstring) fall back to a strict owner check."""
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if meeting.workspace_id:
        if not get_membership(db, meeting.workspace_id, user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    elif meeting.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


def _record_completion_usage(db: Session, response, *, owner_id: str, meeting_id: str | None = None) -> None:
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
        owner_id=owner_id,
        meeting_id=meeting_id,
    )


# --- AI analytics (Token Usage / Cost Tracking / AI Performance backend) ----------------


@router.get("/usage")
async def usage_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Real aggregation over ai_usage_events for the calling user — see services/usage.py.
    Scoped to the caller's own usage; there's no workspace/org concept yet to make a
    workspace-wide admin view meaningful (see AUDIT.md on Enterprise RBAC being deferred)."""
    summary = get_usage_summary_last_n_days(db, owner_id=user_id, days=days)
    return {
        "period_days": days,
        "total_events": summary.total_events,
        "successful_events": summary.successful_events,
        "failed_events": summary.failed_events,
        "success_rate": (summary.successful_events / summary.total_events) if summary.total_events else None,
        "total_prompt_tokens": summary.total_prompt_tokens,
        "total_completion_tokens": summary.total_completion_tokens,
        "total_cost_usd": round(summary.total_cost_usd, 6),
        "avg_latency_ms": round(summary.avg_latency_ms, 1),
        "by_provider": summary.by_provider,
    }


# --- Translation (Deliverable A: real text translation, not the live-audio pipeline) ----


class TranslateRequest(BaseModel):
    text: str
    target_language: str


@router.post("/translate")
async def translate_text(
    payload: TranslateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Generic text translation via the configured LLM provider. Deliberately generic rather
    than one endpoint per surface (transcript/summary/chat/action-items/docs/knowledge-base) —
    they're all just text, and the frontend already has each of those as a string by the time
    it would call this. This is Deliverable A only: real, works today, no infra needed beyond
    the LLM provider that's already wired. It is NOT Deliverable B (live audio translation) —
    see TRANSLATION_ARCHITECTURE.md for why those are different-sized problems."""
    prompt = get_prompt("text_translation").render(target_language=payload.target_language, text=payload.text)
    try:
        provider = get_llm_provider()
        response = await provider.complete(GENERIC_SYSTEM_PROMPT, prompt)
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    _record_completion_usage(db, response, owner_id=user_id)
    return {"translated_text": response.text, "target_language": payload.target_language}


# --- Enterprise AI generators -------------------------------------------------------------


@router.post("/meetings/{meeting_id}/email-draft")
async def generate_email_draft(
    meeting_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    meeting = _meeting_or_404(db, meeting_id, user_id)
    if not meeting.summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No summary yet for this meeting — call GET /meetings/{id}/summary first.",
        )
    intelligence = meeting.intelligence or {}
    prompt = get_prompt("ai_email_generator").render(
        summary=meeting.summary,
        decisions="\n".join(intelligence.get("decisions", [])) or "(none)",
        action_items="\n".join(intelligence.get("action_items", [])) or "(none)",
    )
    try:
        provider = get_llm_provider()
        response = await provider.complete(GENERIC_SYSTEM_PROMPT, prompt)
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    _record_completion_usage(db, response, owner_id=user_id, meeting_id=meeting_id)

    try:
        parsed = json.loads(response.text)
        return {"subject": parsed.get("subject", ""), "body": parsed.get("body", "")}
    except json.JSONDecodeError:
        logger.warning("ai_email_generator returned non-JSON output for meeting %s", meeting_id)
        return {"subject": "", "body": response.text}


@router.post("/meetings/{meeting_id}/follow-up")
async def generate_follow_up(
    meeting_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    meeting = _meeting_or_404(db, meeting_id, user_id)
    if not meeting.summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No summary yet for this meeting — call GET /meetings/{id}/summary first.",
        )
    intelligence = meeting.intelligence or {}
    prompt = get_prompt("ai_followup_message").render(
        summary=meeting.summary,
        action_items="\n".join(intelligence.get("action_items", [])) or "(none)",
    )
    try:
        provider = get_llm_provider()
        response = await provider.complete(GENERIC_SYSTEM_PROMPT, prompt)
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    _record_completion_usage(db, response, owner_id=user_id, meeting_id=meeting_id)
    return {"message": response.text}


# --- AI Research / Knowledge Assistant ("chat with your knowledge base") ----------------


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
async def ask_knowledge_assistant(
    payload: AskRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Composes two already-real pieces — RAG search + an LLM call — rather than being new
    infrastructure of its own. If nothing's been uploaded yet, retrieved is empty and the
    prompt explicitly tells the model to say it doesn't have enough information, rather than
    silently falling back to the model's general knowledge dressed up as a grounded answer."""
    workspace_id = primary_workspace_id(db, user_id)
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace found for this account.")
    try:
        results, rag_usage = await rag.search(workspace_id, payload.question)
    except RagError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    for event in rag_usage:
        record_usage(db, event, owner_id=user_id)

    retrieved_block = "\n".join(f"- {r.text}" for r in results) if results else "(no documents found)"
    prompt = get_prompt("ai_research_assistant").render(retrieved_context=retrieved_block, question=payload.question)
    try:
        provider = get_llm_provider()
        response = await provider.complete(GENERIC_SYSTEM_PROMPT, prompt)
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    _record_completion_usage(db, response, owner_id=user_id)

    return {"answer": response.text, "sources": [r.document_id for r in results]}


# --- Enterprise Search ---------------------------------------------------------------------
# Added in the Phase 4/5 merge. Adapted from the upstream version, which was written against
# an earlier schema (it referenced a `WorkspaceMember` model and `Document.title`/`.content`
# columns that don't exist on this codebase's actual models — see app/models/entities.py).
# Rewritten here against the real `WorkspaceMembership` + `Document` models: documents don't
# store extracted text in Postgres (that lives in Qdrant via the RAG pipeline), so document
# matches are by filename only for now. Meeting matches use title + summary, same as before.


class SearchRequest(BaseModel):
    query: str
    doc_types: list[str] | None = None
    limit: int = 20


@router.post("/search")
async def enterprise_search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Lightweight keyword search across the caller's meetings and uploaded documents. This is
    a fast, dependency-free first pass (substring + word-overlap scoring, no embeddings) — for
    semantic search over document *contents*, ai.py's /ask endpoint already does real RAG via
    Qdrant. This endpoint is for "find the right meeting/file by name" style lookups."""
    import re

    if not payload.query.strip():
        return {"results": [], "total": 0}

    ws_ids = workspace_ids_for_user(db, user_id)
    query_lower = payload.query.lower().strip()
    query_words = set(re.findall(r"\w+", query_lower))
    results: list[dict] = []

    # Search meetings (by title + summary)
    meetings_query = db.query(Meeting).filter(Meeting.owner_id == user_id)
    if ws_ids:
        meetings_query = db.query(Meeting).filter(Meeting.workspace_id.in_(ws_ids))
    meetings = meetings_query.order_by(Meeting.created_at.desc()).limit(100).all()

    for meeting in meetings:
        text = f"{meeting.title or ''} {(meeting.summary or '')}".lower()
        score = 0.0
        if query_lower in text:
            score += 0.5
        for word in query_words:
            if word in text:
                score += 0.15
        if score > 0.05:
            results.append(
                {
                    "id": str(meeting.id),
                    "type": "meeting",
                    "title": meeting.title or "Untitled Meeting",
                    "text": (meeting.summary or "")[:300],
                    "score": round(min(score, 1.0), 4),
                    "metadata": {
                        "created_at": meeting.created_at.isoformat() if meeting.created_at else "",
                    },
                }
            )

    # Search uploaded documents (by filename only — content isn't stored relationally)
    if not payload.doc_types or "document" in payload.doc_types:
        docs_query = db.query(Document)
        if ws_ids:
            docs_query = docs_query.filter(Document.workspace_id.in_(ws_ids))
        documents = docs_query.order_by(Document.created_at.desc()).limit(50).all()

        for doc in documents:
            text = (doc.filename or "").lower()
            score = 0.0
            if query_lower in text:
                score += 0.5
            for word in query_words:
                if word in text:
                    score += 0.15
            if score > 0.05:
                results.append(
                    {
                        "id": str(doc.id),
                        "type": "document",
                        "title": doc.filename or "Untitled Document",
                        "text": "",
                        "score": round(min(score, 1.0), 4),
                        "metadata": {
                            "content_type": doc.content_type or "",
                            "created_at": doc.created_at.isoformat() if doc.created_at else "",
                        },
                    }
                )

    results.sort(key=lambda r: r["score"], reverse=True)
    return {"results": results[: payload.limit], "total": len(results)}


# --- Meeting Export -------------------------------------------------------------------------
# Also added in the Phase 4/5 merge, with the same kind of schema fix: the upstream version
# read `meeting.participants` and `meeting.duration_seconds`, neither of which exists on this
# Meeting model (this product doesn't have a participants table — see app/models/entities.py
# docstrings). Participants and duration are derived from the real transcript instead.


@router.get("/meetings/{meeting_id}/export/{format}")
async def export_meeting(
    meeting_id: str,
    format: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Export a meeting in JSON, TXT, Markdown, or HTML format."""
    import time as _time

    meeting = _meeting_or_404(db, meeting_id, user_id)
    if format not in ("json", "txt", "markdown", "html"):
        raise HTTPException(status_code=400, detail="Format must be json, txt, markdown, or html")

    intelligence = meeting.intelligence or {}
    transcript_events = sorted(meeting.transcript, key=lambda e: e.timestamp_ms)
    transcript_data = [
        {"speaker": e.speaker, "text": e.text, "kind": e.kind, "timestamp_ms": e.timestamp_ms}
        for e in transcript_events
    ]
    participants = sorted({e.speaker for e in transcript_events if e.speaker})
    duration_seconds = (transcript_events[-1].timestamp_ms // 1000) if transcript_events else 0

    if format == "json":
        data = {
            "meeting_id": str(meeting.id),
            "title": meeting.title or "Untitled",
            "exported_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            "summary": meeting.summary or "",
            "action_items": intelligence.get("action_items", []),
            "decisions": intelligence.get("decisions", []),
            "risks": intelligence.get("risks", []),
            "follow_ups": intelligence.get("follow_ups", []),
            "sentiment": intelligence.get("sentiment", ""),
            "participants": participants,
            "transcript": transcript_data,
            "duration_seconds": duration_seconds,
        }
        return {"format": "json", "data": data}

    elif format == "txt":
        lines = [f"MEETING: {meeting.title or 'Untitled'}", ""]
        if meeting.summary:
            lines.extend(["SUMMARY", meeting.summary, ""])
        if intelligence.get("action_items"):
            lines.append("ACTION ITEMS")
            for i, a in enumerate(intelligence["action_items"], 1):
                lines.append(f"  {i}. {a}")
            lines.append("")
        if intelligence.get("decisions"):
            lines.append("DECISIONS")
            for i, d in enumerate(intelligence["decisions"], 1):
                lines.append(f"  {i}. {d}")
            lines.append("")
        lines.append("---")
        lines.append("Exported by Microtechnique AI Meeting")
        return {"format": "txt", "content": "\n".join(lines)}

    elif format == "markdown":
        lines = [f"# {meeting.title or 'Untitled'}", ""]
        if meeting.summary:
            lines.extend(["## Summary", "", meeting.summary, ""])
        if intelligence.get("action_items"):
            lines.append("## Action Items")
            for a in intelligence["action_items"]:
                lines.append(f"- [ ] {a}")
            lines.append("")
        if intelligence.get("decisions"):
            lines.append("## Decisions")
            for d in intelligence["decisions"]:
                lines.append(f"- {d}")
            lines.append("")
        lines.extend(["---", "*Generated by Microtechnique AI Meeting*"])
        return {"format": "markdown", "content": "\n".join(lines)}

    else:  # html
        sections = []
        if meeting.summary:
            sections.append(f"<h2>Summary</h2><p>{meeting.summary}</p>")
        if intelligence.get("action_items"):
            items = "".join(f"<li>{a}</li>" for a in intelligence["action_items"])
            sections.append(f"<h2>Action Items</h2><ol>{items}</ol>")
        if intelligence.get("decisions"):
            items = "".join(f"<li>{d}</li>" for d in intelligence["decisions"])
            sections.append(f"<h2>Decisions</h2><ol>{items}</ol>")
        body = "\n".join(sections)
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:680px;margin:0 auto;padding:20px">
<div style="background:#5B0A8C;color:white;padding:20px;border-radius:8px 8px 0 0">
<h1 style="margin:0">{meeting.title or "Untitled"}</h1></div>
<div style="padding:20px;border:1px solid #e5e7eb">{body}</div>
</body></html>"""
        return {"format": "html", "content": html}
