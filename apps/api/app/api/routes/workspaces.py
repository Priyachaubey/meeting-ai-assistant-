from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.database.session import get_db
from app.models.entities import Meeting, User, Workspace, WorkspaceMembership
from app.schemas.workspace import (
    ActionItemEntry,
    AddMemberRequest,
    MembershipOut,
    UpdateMemberRoleRequest,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.services.notifications import notify_role_changed, notify_workspace_added
from app.services.permissions import PermissionError, count_owners, get_membership, require_role

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _membership_or_404(db: Session, workspace_id: str, user_id: str) -> WorkspaceMembership:
    membership = get_membership(db, workspace_id, user_id)
    if not membership:
        # 404, not 403 — don't confirm a workspace exists to someone who isn't in it.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return membership


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)) -> list[dict]:
    memberships = db.query(WorkspaceMembership).filter(WorkspaceMembership.user_id == user_id).all()
    workspaces = {w.id: w for w in db.query(Workspace).filter(Workspace.id.in_([m.workspace_id for m in memberships]))}
    return [
        {
            "id": m.workspace_id,
            "name": workspaces[m.workspace_id].name,
            "created_at": workspaces[m.workspace_id].created_at,
            "my_role": m.role,
        }
        for m in memberships
        if m.workspace_id in workspaces
    ]


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """A user can have more than one workspace — e.g. their personal one plus a shared team
    one. Creating a workspace makes you its owner; nothing else changes for your existing
    workspaces."""
    workspace = Workspace(name=payload.name, created_by=user_id)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=user_id, role="owner"))
    db.commit()
    return {"id": workspace.id, "name": workspace.name, "created_at": workspace.created_at, "my_role": "owner"}


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def rename_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        membership = require_role(db, workspace_id, user_id, minimum="owner")
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    workspace.name = payload.name
    db.commit()
    return {"id": workspace.id, "name": workspace.name, "created_at": workspace.created_at, "my_role": membership.role}


@router.get("/{workspace_id}/members", response_model=list[MembershipOut])
async def list_members(
    workspace_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    _membership_or_404(db, workspace_id, user_id)
    rows = (
        db.query(WorkspaceMembership, User)
        .join(User, User.id == WorkspaceMembership.user_id)
        .filter(WorkspaceMembership.workspace_id == workspace_id)
        .all()
    )
    return [
        {"user_id": u.id, "email": u.email, "full_name": u.full_name, "role": m.role, "joined_at": m.joined_at}
        for m, u in rows
    ]


@router.post("/{workspace_id}/members", response_model=MembershipOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    workspace_id: str,
    payload: AddMemberRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Adds an EXISTING user (by email) to the workspace. There's no email-invite system in
    this codebase (no email-sending infra wired anywhere) — claiming "invite sent" without one
    would be a fake confirmation, so this is honest about what it actually does: if the email
    doesn't belong to a registered user yet, it 404s and says so, rather than pretending an
    invite went out."""
    try:
        require_role(db, workspace_id, user_id, minimum="admin")
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if payload.role not in ("admin", "member"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role must be 'admin' or 'member'")

    target = db.query(User).filter(User.email == payload.email.lower()).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registered user with email {payload.email} — they need to create an account first "
            "(no email-invite system exists to send one automatically).",
        )
    if get_membership(db, workspace_id, target.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a member of this workspace.")

    membership = WorkspaceMembership(workspace_id=workspace_id, user_id=target.id, role=payload.role)
    db.add(membership)
    db.commit()
    workspace = db.get(Workspace, workspace_id)
    if workspace:
        notify_workspace_added(db, target.id, workspace_id, workspace.name)
    return {
        "user_id": target.id,
        "email": target.email,
        "full_name": target.full_name,
        "role": membership.role,
        "joined_at": membership.joined_at,
    }


@router.patch("/{workspace_id}/members/{member_user_id}", response_model=MembershipOut)
async def update_member_role(
    workspace_id: str,
    member_user_id: str,
    payload: UpdateMemberRoleRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    try:
        require_role(db, workspace_id, user_id, minimum="owner")
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if payload.role not in ("owner", "admin", "member"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role must be owner, admin, or member")

    membership = _membership_or_404(db, workspace_id, member_user_id)
    if membership.role == "owner" and payload.role != "owner" and count_owners(db, workspace_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote the last owner — promote someone else first.",
        )
    membership.role = payload.role
    db.commit()
    target = db.get(User, member_user_id)
    workspace = db.get(Workspace, workspace_id)
    if workspace:
        notify_role_changed(db, member_user_id, workspace_id, workspace.name, payload.role)
    return {
        "user_id": member_user_id,
        "email": target.email,
        "full_name": target.full_name,
        "role": membership.role,
        "joined_at": membership.joined_at,
    }


@router.delete("/{workspace_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: str,
    member_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    try:
        require_role(db, workspace_id, user_id, minimum="admin")
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    membership = _membership_or_404(db, workspace_id, member_user_id)
    if membership.role == "owner" and count_owners(db, workspace_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last owner — promote someone else first.",
        )
    db.delete(membership)
    db.commit()


@router.get("/{workspace_id}/action-items", response_model=list[ActionItemEntry])
async def team_action_board(
    workspace_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    """Team Action Board: real aggregation of action_items across every meeting in this
    workspace (meeting.intelligence['action_items'], populated live — see services/memory.py),
    not a separate tracked-task system. There's no assignee/priority/due-date field on action
    items anywhere in this codebase (they're free-text strings detected by a keyword
    heuristic, see agents/orchestrator.py) — filtering by those, as the original feature
    request asked for, would need that data to exist first. What's real: every action item
    from every meeting in the workspace, with which meeting it came from."""
    _membership_or_404(db, workspace_id, user_id)
    meetings = db.query(Meeting).filter(Meeting.workspace_id == workspace_id).all()
    entries = []
    for meeting in meetings:
        for item in (meeting.intelligence or {}).get("action_items", []):
            entries.append({"meeting_id": meeting.id, "meeting_title": meeting.title, "text": item})
    return entries
