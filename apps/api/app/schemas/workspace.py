from datetime import datetime

from pydantic import BaseModel, EmailStr


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceUpdate(BaseModel):
    name: str


class WorkspaceOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    my_role: str

    class Config:
        from_attributes = True


class MembershipOut(BaseModel):
    user_id: str
    email: EmailStr
    full_name: str | None
    role: str
    joined_at: datetime


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class UpdateMemberRoleRequest(BaseModel):
    role: str


class ActionItemEntry(BaseModel):
    meeting_id: str
    meeting_title: str
    text: str
