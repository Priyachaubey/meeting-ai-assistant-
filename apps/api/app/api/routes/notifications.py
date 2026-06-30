from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.database.session import get_db
from app.models.entities import Notification
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[Notification]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.read.is_(False))
    return query.order_by(Notification.created_at.desc()).limit(50).all()


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Notification:
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.read = True
    db.commit()
    return notification


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)) -> None:
    db.query(Notification).filter(Notification.user_id == user_id, Notification.read.is_(False)).update({"read": True})
    db.commit()
