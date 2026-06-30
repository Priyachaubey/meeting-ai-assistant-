from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    type: str
    message: str
    meeting_id: str | None
    workspace_id: str | None
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True
