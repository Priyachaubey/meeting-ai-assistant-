import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    full_name: Mapped[str | None] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="owner")
    audio_capture_mode: Mapped[str] = mapped_column(String, default="hybrid")
    preferred_language: Mapped[str] = mapped_column(String, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class Workspace(Base):
    """A team/organization. Every user gets one personal workspace automatically on
    registration (see routes/auth.py register()) so the single-user flow that existed before
    this kept working unchanged — a user with no teammates just has a workspace of one.
    Real multi-tenancy starts at WorkspaceMembership, not here: this table is just identity
    (name, who created it); membership and roles are the actual access-control surface."""
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkspaceMembership(Base):
    """The actual RBAC surface: who belongs to which workspace, with what role.
    role is one of "owner" | "admin" | "member" — see services/permissions.py for what each
    can do. unique(workspace_id, user_id): a user has exactly one role per workspace, not a
    stack of memberships to reconcile."""
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        Index("ix_workspace_memberships_workspace_id", "workspace_id"),
        Index("ix_workspace_memberships_user_id", "user_id"),
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String, default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (Index("ix_meetings_owner_id", "owner_id"), Index("ix_meetings_workspace_id", "workspace_id"))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String, default="meeting")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"))
    encrypted: Mapped[bool] = mapped_column(Boolean, default=True)
    summary: Mapped[str | None] = mapped_column(Text)
    intelligence: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    transcript: Mapped[list["TranscriptEvent"]] = relationship(back_populates="meeting")
class TranscriptEvent(Base):
    __tablename__ = "transcript_events"
    __table_args__ = (Index("ix_transcript_events_meeting_id", "meeting_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"))
    speaker: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String, default="statement")
    timestamp_ms: Mapped[int]
    meeting: Mapped[Meeting] = relationship(back_populates="transcript")
class Document(Base):
    """Was in the original scaffold but never actually instantiated anywhere — uploads were
    processed (chunked into Qdrant) and the original bytes discarded, with no row ever
    written here. Now real: services/storage persists the actual file, and a row here tracks
    where. workspace_id, not owner_id, matching RAG's workspace-level scoping (see
    services/rag/pipeline.py's docstring) — a document one teammate uploads is visible to the
    whole workspace, the same as a meeting or anything else in this product's shared-library
    model."""
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_workspace_id", "workspace_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(default=0)
    storage_key: Mapped[str] = mapped_column(String)
    qdrant_collection: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class Subscription(Base):
    """One row per workspace/owner's Stripe subscription. Updated from webhook events,
    never trust client-supplied plan/status — only the checkout/webhook flow writes here."""
    __tablename__ = "subscriptions"
    __table_args__ = (Index("ix_subscriptions_owner_id", "owner_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, index=True)
    plan: Mapped[str] = mapped_column(String, default="free")
    status: Mapped[str] = mapped_column(String, default="inactive")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
class AIUsageEvent(Base):
    """One row per AI provider call (chat completion or embedding) — real token counts and
    latency read from the provider's own response, real cost computed from the dated pricing
    table in services/llm/pricing.py. This is the data every AI analytics endpoint reads from;
    there is no separate "analytics" data source, just aggregation queries over this table."""
    __tablename__ = "ai_usage_events"
    __table_args__ = (
        Index("ix_ai_usage_events_owner_id", "owner_id"),
        Index("ix_ai_usage_events_meeting_id", "meeting_id"),
        Index("ix_ai_usage_events_created_at", "created_at"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    meeting_id: Mapped[str | None] = mapped_column(ForeignKey("meetings.id"))
    operation: Mapped[str] = mapped_column(String)  # "chat_completion" | "embedding"
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float | None] = mapped_column()  # NULL, not 0.0, when the model/price is unknown
    latency_ms: Mapped[float] = mapped_column(default=0.0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class Notification(Base):
    """In-app only — there's no email/push infrastructure wired anywhere in this codebase, so
    that's all this can honestly be right now. Triggered by real events (see services/
    notifications.py): a meeting summary finishing generation, being added to a workspace, a
    role change. Not a generic "log every event" table — only things a user would actually
    want to see, to avoid the feed becoming noise nobody reads."""
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_created_at", "created_at"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String)  # "summary_ready" | "workspace_added" | "role_changed"
    message: Mapped[str] = mapped_column(String)
    meeting_id: Mapped[str | None] = mapped_column(ForeignKey("meetings.id"))
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class MeetingShareLink(Base):
    """Read-only guest access to ONE meeting's transcript/AI artifacts, scoped narrowly on
    purpose — see AUDIT.md for why this exists instead of full multi-participant video rooms.
    token_hash, never the raw token: same handling as a password — a DB leak shouldn't hand
    out live access to every shared meeting. The raw token is generated once at creation time
    (routes/meetings.py), returned to the creator, and never stored or logged anywhere again."""
    __tablename__ = "meeting_share_links"
    __table_args__ = (
        Index("ix_meeting_share_links_meeting_id", "meeting_id"),
        Index("ix_meeting_share_links_token_hash", "token_hash"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class ShareLinkAccess(Base):
    """One row per guest view — real, minimal audit log for a real public endpoint, not a
    generic catch-all event table."""
    __tablename__ = "share_link_accesses"
    __table_args__ = (Index("ix_share_link_accesses_link_id", "link_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    link_id: Mapped[str] = mapped_column(ForeignKey("meeting_share_links.id"))
    ip_address: Mapped[str | None] = mapped_column(String)
    accessed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
