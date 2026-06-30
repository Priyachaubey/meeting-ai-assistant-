"""Participant model and state management."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParticipantRole(str, Enum):
    HOST = "host"
    CO_HOST = "co_host"
    PARTICIPANT = "participant"
    GUEST = "guest"
    WAITING = "waiting"


class ParticipantState(str, Enum):
    IN_ROOM = "in_room"
    IN_WAITING_ROOM = "in_waiting_room"
    DISCONNECTED = "disconnected"
    REMOVED = "removed"


@dataclass
class MediaState:
    """Audio/video device state for a participant."""

    audio_enabled: bool = False
    video_enabled: bool = False
    screen_sharing: bool = False
    audio_device: str | None = None
    video_device: str | None = None


@dataclass
class Participant:
    """Represents a meeting participant."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    display_name: str = ""
    room_id: str = ""
    role: ParticipantRole = ParticipantRole.PARTICIPANT
    state: ParticipantState = ParticipantState.IN_ROOM
    media: MediaState = field(default_factory=MediaState)

    # Timing
    joined_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    left_at: datetime.datetime | None = None

    # UI state
    hand_raised: bool = False
    hand_raised_at: datetime.datetime | None = None
    is_pinned: bool = False
    is_speaking: bool = False
    connection_quality: str = "good"  # good | fair | poor

    # Metadata
    avatar_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def leave(self) -> None:
        self.state = ParticipantState.DISCONNECTED
        self.left_at = datetime.datetime.now(datetime.timezone.utc)
        self.media = MediaState()

    def raise_hand(self) -> None:
        self.hand_raised = True
        self.hand_raised_at = datetime.datetime.now(datetime.timezone.utc)

    def lower_hand(self) -> None:
        self.hand_raised = False
        self.hand_raised_at = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "display_name": self.display_name,
            "room_id": self.room_id,
            "role": self.role.value,
            "state": self.state.value,
            "media": {
                "audio_enabled": self.media.audio_enabled,
                "video_enabled": self.media.video_enabled,
                "screen_sharing": self.media.screen_sharing,
            },
            "hand_raised": self.hand_raised,
            "is_speaking": self.is_speaking,
            "connection_quality": self.connection_quality,
            "joined_at": self.joined_at.isoformat(),
            "left_at": self.left_at.isoformat() if self.left_at else None,
        }
