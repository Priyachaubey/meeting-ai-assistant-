"""Conversation memory.

Scoped deliberately to what's well-defined: a rolling window of recent transcript lines for
the *current meeting* — "session memory" and "meeting memory" are the same thing in this
product (a meeting IS the session), and the storage already exists for free in
TranscriptEvent; this module is just a query helper plus formatting, not new state.

NOT implemented here: cross-meeting "user memory" / "workspace memory" / "long-term memory"
(remembering facts about a person or account across separate meetings). That's not a missing
query helper, it's a missing product decision — what facts get remembered, who can see them,
how long they're retained, whether a customer can ask to have them forgotten. Inventing a
schema for that without those answers would be guessing at a spec, not implementing one.
Once there's an actual answer to "what should persist about a contact across meetings,"
adding a table for it is small; deciding what that table should mean is the real work, and
it isn't done.
"""

from sqlalchemy.orm import Session

from app.models.entities import Meeting, TranscriptEvent


def get_recent_context(db: Session, meeting_id: str, *, limit: int = 8) -> list[str]:
    """Last `limit` transcript lines for this meeting, oldest first (so it reads as a
    conversation when joined into a prompt, not reverse-chronological)."""
    rows = (
        db.query(TranscriptEvent)
        .filter(TranscriptEvent.meeting_id == meeting_id)
        .order_by(TranscriptEvent.timestamp_ms.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [f"{r.speaker}: {r.text}" for r in rows]


def format_context_block(lines: list[str]) -> str:
    return "\n".join(lines) if lines else "(no prior context)"


def append_intelligence_items(db: Session, meeting_id: str, field: str, new_items: list[str]) -> None:
    """Generic accumulator for any list-of-strings field on meeting.intelligence (action_items,
    follow_ups, ...). Reuses the JSON column rather than a new table per field: it's already
    where AI-derived meeting data lives, and a JSON list of short strings doesn't need real
    normalization. Deduplicates by exact text match — good enough for the same heuristic/LLM
    call re-firing on similar lines, not meant to catch near-duplicate phrasing.
    Shared by both routes/meetings.py (REST) and routes/ws.py (WebSocket) — they see the same
    kind of per-chunk signals and should accumulate them the same way."""
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        return
    intelligence = dict(meeting.intelligence or {})
    existing = intelligence.get(field, [])
    merged = existing + [item for item in new_items if item not in existing]
    intelligence[field] = merged
    meeting.intelligence = intelligence


def append_action_items(db: Session, meeting_id: str, new_items: list[str]) -> None:
    """Action items are detected cheaply on every chunk (ActionItemAgent's keyword heuristic
    in the orchestrator, no LLM call) — accumulated as they're found rather than waiting for
    the end-of-meeting summary."""
    append_intelligence_items(db, meeting_id, "action_items", new_items)


def append_follow_ups(db: Session, meeting_id: str, new_items: list[str]) -> None:
    """Follow-ups come from the gated structured LLM call (question-triggered), same source as
    decisions/risks — accumulated live so the Meeting Deep Dive page has them without waiting
    for (or duplicating) the end-of-meeting summary call."""
    append_intelligence_items(db, meeting_id, "follow_ups", new_items)
