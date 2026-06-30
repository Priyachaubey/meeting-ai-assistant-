"""Meeting Server API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateRoomRequest(BaseModel):
    title: str = ""
    type: str = "instant"  # instant | scheduled | recurring
    workspace_id: str | None = None
    waiting_room: bool = False
    meeting_password: str | None = None
    mute_on_entry: bool = True
    max_participants: int = 100
    recording_enabled: bool = True
    chat_enabled: bool = True
    screen_share_enabled: bool = True
    scheduled_start: str | None = None
    scheduled_end: str | None = None


class CreateRoomResponse(BaseModel):
    id: str
    title: str
    type: str
    status: str
    host_id: str
    join_url: str
    settings: dict
    created_at: str


class JoinRoomRequest(BaseModel):
    display_name: str
    password: str | None = None


class RoomResponse(BaseModel):
    room: dict
    participants: list[dict]
    chat_enabled: bool = True


class ParticipantActionRequest(BaseModel):
    action: str  # mute | unmute | video_on | video_off | raise_hand | lower_hand | screen_share_start | screen_share_stop
    participant_id: str | None = None


class HostActionRequest(BaseModel):
    action: str  # lock | unlock | mute_all | remove_participant | end_meeting | start_recording | stop_recording
    target_participant_id: str | None = None


class ChatSendRequest(BaseModel):
    content: str
    message_type: str = "text"


class SignallingMessage(BaseModel):
    type: str
    target_id: str | None = None
    data: dict = Field(default_factory=dict)


class InviteRequest(BaseModel):
    emails: list[str] = Field(default_factory=list)
    message: str = ""


class MeetingStatusResponse(BaseModel):
    rooms: dict
    participants: dict
    chat: dict
    recording: dict
