from sqlalchemy.orm import Session

from app.models.entities import WorkspaceMembership

# Higher rank = more access. "owner" > "admin" > "member" — a simple total order, not a
# matrix of fine-grained permissions, because nothing in this product yet needs finer-grained
# distinctions (e.g. "can invite but not remove members"). Extend ROLE_RANK + the call sites
# that check it if/when a real need for that granularity shows up; inventing it now would be
# permissions for workflows that don't exist.
ROLE_RANK = {"member": 0, "admin": 1, "owner": 2}


class PermissionError(Exception):
    """Raised when a user lacks the role required for an action. Routes convert this to a
    403, never a generic 500 — this is always a real authorization decision, not a bug."""


def get_membership(db: Session, workspace_id: str, user_id: str) -> WorkspaceMembership | None:
    return (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.workspace_id == workspace_id, WorkspaceMembership.user_id == user_id)
        .first()
    )


def require_role(db: Session, workspace_id: str, user_id: str, *, minimum: str) -> WorkspaceMembership:
    """Raises PermissionError if the user isn't a member, or is a member below `minimum`
    role. Returns the membership row on success, in case the caller needs it (e.g. to check
    `membership.role` for finer display logic)."""
    membership = get_membership(db, workspace_id, user_id)
    if not membership:
        raise PermissionError("Not a member of this workspace.")
    if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
        raise PermissionError(f"This action requires '{minimum}' role or higher — you have '{membership.role}'.")
    return membership


def workspace_ids_for_user(db: Session, user_id: str) -> list[str]:
    rows = db.query(WorkspaceMembership).filter(WorkspaceMembership.user_id == user_id).all()
    return [r.workspace_id for r in rows]


def primary_workspace_id(db: Session, user_id: str) -> str | None:
    """A user's earliest membership — their personal workspace from registration, assuming
    no other membership predates it (true in practice: registration creates it as literally
    the first thing after the user row exists). Shared by routes/meetings.py (default
    workspace for a new meeting) and routes/knowledge.py + routes/ai.py (default scope for
    knowledge-base ingestion/search) — both need the same "which workspace if not specified"
    resolution, so it lives here once instead of being duplicated per route file."""
    membership = (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.user_id == user_id)
        .order_by(WorkspaceMembership.joined_at)
        .first()
    )
    return membership.workspace_id if membership else None


def count_owners(db: Session, workspace_id: str) -> int:
    """Used to block removing/demoting the last owner — a workspace with zero owners is
    permanently locked (nobody left with rights to manage membership), which is a real bug
    class worth explicitly preventing rather than discovering later."""
    return (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.workspace_id == workspace_id, WorkspaceMembership.role == "owner")
        .count()
    )
