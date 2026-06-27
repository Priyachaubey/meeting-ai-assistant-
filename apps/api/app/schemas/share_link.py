from datetime import datetime

from pydantic import BaseModel


class CreateShareLinkRequest(BaseModel):
    expires_in_hours: int = 168


class ShareLinkOut(BaseModel):
    id: str
    expires_at: datetime
    revoked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ShareLinkCreated(ShareLinkOut):
    token: str  # only ever present in the create response — never retrievable again


class GuestMeetingView(BaseModel):
    """Deliberately narrower than the authenticated meeting detail response — no owner_id,
    no workspace_id, nothing beyond what a guest reading a shared meeting outcome needs."""

    title: str
    created_at: datetime
    transcript: list[dict]
    summary: str | None
    decisions: list[str]
    risks: list[str]
    action_items: list[str]
    follow_ups: list[str]
