"""Participant Manager – manages participants within rooms."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.participants.models import (
    MediaState,
    Participant,
    ParticipantRole,
    ParticipantState,
)

logger = structlog.get_logger()


class ParticipantManager:
    """Manages participants across all rooms."""

    def __init__(self) -> None:
        self._participants: dict[str, Participant] = {}  # participant_id -> Participant
        self._room_participants: dict[
            str, set[str]
        ] = {}  # room_id -> set of participant_ids

    def add_participant(
        self,
        *,
        room_id: str,
        user_id: str,
        display_name: str,
        role: ParticipantRole = ParticipantRole.PARTICIPANT,
        state: ParticipantState = ParticipantState.IN_ROOM,
    ) -> Participant:
        """Add a participant to a room."""
        participant = Participant(
            id=str(uuid.uuid4()),
            user_id=user_id,
            display_name=display_name,
            room_id=room_id,
            role=role,
            state=state,
        )
        self._participants[participant.id] = participant

        if room_id not in self._room_participants:
            self._room_participants[room_id] = set()
        self._room_participants[room_id].add(participant.id)

        logger.info(
            "participant_joined",
            participant_id=participant.id,
            user_id=user_id,
            room_id=room_id,
            role=role.value,
        )
        return participant

    def remove_participant(self, participant_id: str) -> Participant | None:
        """Remove a participant from their room."""
        participant = self._participants.pop(participant_id, None)
        if participant:
            participant.leave()
            if participant.room_id in self._room_participants:
                self._room_participants[participant.room_id].discard(participant_id)
            logger.info(
                "participant_left",
                participant_id=participant_id,
                room_id=participant.room_id,
            )
        return participant

    def get_participant(self, participant_id: str) -> Participant | None:
        return self._participants.get(participant_id)

    def get_room_participants(self, room_id: str) -> list[Participant]:
        pids = self._room_participants.get(room_id, set())
        return [self._participants[pid] for pid in pids if pid in self._participants]

    def get_active_count(self, room_id: str) -> int:
        return len(
            [
                p
                for p in self.get_room_participants(room_id)
                if p.state == ParticipantState.IN_ROOM
            ]
        )

    def update_media(
        self,
        participant_id: str,
        *,
        audio_enabled: bool | None = None,
        video_enabled: bool | None = None,
        screen_sharing: bool | None = None,
    ) -> Participant | None:
        participant = self._participants.get(participant_id)
        if participant:
            if audio_enabled is not None:
                participant.media.audio_enabled = audio_enabled
            if video_enabled is not None:
                participant.media.video_enabled = video_enabled
            if screen_sharing is not None:
                participant.media.screen_sharing = screen_sharing
        return participant

    def promote_to_host(self, participant_id: str) -> Participant | None:
        participant = self._participants.get(participant_id)
        if participant:
            participant.role = ParticipantRole.HOST
        return participant

    def mute_all(self, room_id: str, exclude_host: bool = True) -> list[str]:
        """Mute all participants in a room. Returns list of muted participant IDs."""
        muted = []
        for p in self.get_room_participants(room_id):
            if exclude_host and p.role == ParticipantRole.HOST:
                continue
            p.media.audio_enabled = False
            muted.append(p.id)
        return muted

    def get_status(self) -> dict[str, Any]:
        total = len(self._participants)
        active = sum(
            1
            for p in self._participants.values()
            if p.state == ParticipantState.IN_ROOM
        )
        waiting = sum(
            1
            for p in self._participants.values()
            if p.state == ParticipantState.IN_WAITING_ROOM
        )
        hands_raised = sum(1 for p in self._participants.values() if p.hand_raised)
        return {
            "total_participants": total,
            "active": active,
            "waiting": waiting,
            "hands_raised": hands_raised,
            "rooms_with_participants": len(self._room_participants),
        }


participant_manager = ParticipantManager()
