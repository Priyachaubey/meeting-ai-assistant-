import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.entities import MeetingShareLink, ShareLinkAccess


class ShareLinkError(Exception):
    """Invalid, expired, or revoked link — the guest endpoint turns this into a 404, not a
    403, so a guessed/expired token doesn't confirm to an attacker that a link once existed."""


def _hash_token(raw_token: str) -> str:
    # SHA-256 of a 256-bit random token is plenty here — this isn't a password (no human
    # picks it, no brute-forceable keyspace smaller than the token itself), so a slow KDF
    # like bcrypt would just add latency for no real security benefit.
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_share_link(db: Session, meeting_id: str, created_by: str, *, expires_in_hours: int = 168) -> tuple[MeetingShareLink, str]:
    """Returns (the DB row, the raw token) — the raw token is only ever available here, at
    creation time. Default expiry 168h (7 days): long enough to be useful for "share this
    meeting outcome," short enough that a forgotten link doesn't stay live forever."""
    raw_token = secrets.token_urlsafe(32)
    link = MeetingShareLink(
        meeting_id=meeting_id,
        created_by=created_by,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
    )
    db.add(link)
    db.commit()
    return link, raw_token


def resolve_share_link(db: Session, raw_token: str, *, ip_address: str | None = None) -> MeetingShareLink:
    """Validates and logs access in one step — every successful resolution is a real guest
    view, so it's logged here rather than relying on every caller to remember to."""
    link = db.query(MeetingShareLink).filter(MeetingShareLink.token_hash == _hash_token(raw_token)).first()
    if not link:
        raise ShareLinkError("Invalid link.")
    if link.revoked:
        raise ShareLinkError("This link has been revoked.")
    if link.expires_at < datetime.utcnow():
        raise ShareLinkError("This link has expired.")
    db.add(ShareLinkAccess(link_id=link.id, ip_address=ip_address))
    db.commit()
    return link
