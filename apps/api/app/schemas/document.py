from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime

    class Config:
        from_attributes = True
