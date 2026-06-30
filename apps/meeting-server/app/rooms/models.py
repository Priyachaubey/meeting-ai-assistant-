"""Meeting Room – core room model and state management."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RoomStatus(str, Enum):
    LOBBY = "lobby"
    ACTIVE = "active"
    PAUSED = "paused"
    RECORDING = "recording"
    ENDED = "ended"


class MeetingType(str, Enum):
    INSTANT = "instant"
    SCHEDULED = "scheduled"
    RECURRING = "recurring"


@dataclass
class RoomSettings:
    """Configurable room settings."""

    waiting_room: bool = False
    meeting_password: str | None = None
    lock_after_join: bool = False
    mute_on_entry: bool = True
    max_participants: int = 100
    recording_enabled: bool = True
    chat_enabled: bool = True
    screen_share_enabled: bool = True
    raise_hand_enabled: bool = True
    emoji_reactions_enabled: bool = True
    breakout_rooms_enabled: bool = False


@dataclass
class MeetingRoom:
    """Represents a meeting room with full state."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    type: MeetingType = MeetingType.INSTANT
    status: RoomStatus = RoomStatus.LOBBY
    host_id: str = ""
    workspace_id: str | None = None
    settings: RoomSettings = field(default_factory=RoomSettings)

    # Timing
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None
    scheduled_start: datetime.datetime | None = None
    scheduled_end: datetime.datetime | None = None

    # State
    is_locked: bool = False
    is_recording: bool = False
    participants_count: int = 0

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        self.status = RoomStatus.ACTIVE
        self.started_at = datetime.datetime.now(datetime.timezone.utc)

    def end(self) -> None:
        self.status = RoomStatus.ENDED
        self.ended_at = datetime.datetime.now(datetime.timezone.utc)
        self.is_recording = False

    def lock(self) -> None:
        self.is_locked = True

    def unlock(self) -> None:
        self.is_locked = False

    def start_recording(self) -> None:
        self.is_recording = True
        self.status = RoomStatus.RECORDING

    def stop_recording(self) -> None:
        self.is_recording = False
        self.status = RoomStatus.ACTIVE

    @property
    def duration_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.ended_at or datetime.datetime.now(datetime.timezone.utc)
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type.value,
            "status": self.status.value,
            "host_id": self.host_id,
            "workspace_id": self.workspace_id,
            "settings": {
                "waiting_room": self.settings.waiting_room,
                "mute_on_entry": self.settings.mute_on_entry,
                "max_participants": self.settings.max_participants,
                "recording_enabled": self.settings.recording_enabled,
                "chat_enabled": self.settings.chat_enabled,
                "screen_share_enabled": self.settings.screen_share_enabled,
                "raise_hand_enabled": self.settings.raise_hand_enabled,
                "emoji_reactions_enabled": self.settings.emoji_reactions_enabled,
                "breakout_rooms_enabled": self.settings.breakout_rooms_enabled,
            },
            "is_locked": self.is_locked,
            "is_recording": self.is_recording,
            "participants_count": self.participants_count,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "scheduled_start": self.scheduled_start.isoformat()
            if self.scheduled_start
            else None,
            "scheduled_end": self.scheduled_end.isoformat()
            if self.scheduled_end
            else None,
            "duration_seconds": self.duration_seconds,
        }
