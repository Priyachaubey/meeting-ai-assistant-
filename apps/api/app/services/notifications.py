from sqlalchemy.orm import Session

from app.models.entities import Notification


def notify(
    db: Session,
    user_id: str,
    type: str,
    message: str,
    *,
    meeting_id: str | None = None,
    workspace_id: str | None = None,
) -> None:
    db.add(Notification(user_id=user_id, type=type, message=message, meeting_id=meeting_id, workspace_id=workspace_id))
    db.commit()


def notify_summary_ready(db: Session, user_id: str, meeting_id: str, meeting_title: str) -> None:
    notify(db, user_id, "summary_ready", f'Summary ready for "{meeting_title}"', meeting_id=meeting_id)


def notify_workspace_added(db: Session, user_id: str, workspace_id: str, workspace_name: str) -> None:
    notify(db, user_id, "workspace_added", f'You were added to "{workspace_name}"', workspace_id=workspace_id)


def notify_role_changed(db: Session, user_id: str, workspace_id: str, workspace_name: str, new_role: str) -> None:
    notify(db, user_id, "role_changed", f'Your role in "{workspace_name}" changed to {new_role}', workspace_id=workspace_id)
