from datetime import datetime

from pydantic import BaseModel


class MeetingCreate(BaseModel):
    title: str
    mode: str = "meeting"
    workspace_id: str | None = None  # defaults to the caller's primary (oldest-owned) workspace if omitted


class MeetingOut(BaseModel):
    id: str
    title: str
    mode: str
    created_at: datetime
    has_summary: bool
    workspace_id: str | None
    owner_id: str

    class Config:
        from_attributes = True


class TranscriptChunk(BaseModel):
    speaker: str = "Unknown"
    text: str
    timestamp_ms: int


class AgentResult(BaseModel):
    question_detected: bool
    suggested_response: str | None = None
    follow_ups: list[str] = []
    action_items: list[str] = []
    sentiment: str = "neutral"
    decisions: list[str] = []
    risks: list[str] = []
