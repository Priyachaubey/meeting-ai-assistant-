"""Room Manager – lifecycle management for meeting rooms."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.core.config import settings
from app.rooms.models import MeetingRoom, MeetingType, RoomSettings, RoomStatus

logger = structlog.get_logger()


class RoomManager:
    """Manages the lifecycle of all meeting rooms."""

    def __init__(self) -> None:
        self._rooms: dict[str, MeetingRoom] = {}

    def create_room(
        self,
        *,
        host_id: str,
        title: str = "",
        room_type: MeetingType = MeetingType.INSTANT,
        workspace_id: str | None = None,
        room_settings: RoomSettings | None = None,
        scheduled_start: Any = None,
        scheduled_end: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> MeetingRoom:
        """Create a new meeting room."""
        room = MeetingRoom(
            id=str(uuid.uuid4()),
            title=title or f"Meeting {len(self._rooms) + 1}",
            type=room_type,
            host_id=host_id,
            workspace_id=workspace_id,
            settings=room_settings or RoomSettings(),
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            metadata=metadata or {},
        )
        self._rooms[room.id] = room
        logger.info("room_created", room_id=room.id, host_id=host_id, title=room.title)
        return room

    def get_room(self, room_id: str) -> MeetingRoom | None:
        return self._rooms.get(room_id)

    def start_room(self, room_id: str) -> MeetingRoom | None:
        room = self._rooms.get(room_id)
        if room:
            room.start()
            logger.info("room_started", room_id=room_id)
        return room

    def end_room(self, room_id: str) -> MeetingRoom | None:
        room = self._rooms.get(room_id)
        if room:
            room.end()
            logger.info("room_ended", room_id=room_id, duration=room.duration_seconds)
        return room

    def lock_room(self, room_id: str) -> MeetingRoom | None:
        room = self._rooms.get(room_id)
        if room:
            room.lock()
        return room

    def unlock_room(self, room_id: str) -> MeetingRoom | None:
        room = self._rooms.get(room_id)
        if room:
            room.unlock()
        return room

    def start_recording(self, room_id: str) -> MeetingRoom | None:
        room = self._rooms.get(room_id)
        if room and room.settings.recording_enabled:
            room.start_recording()
            logger.info("recording_started", room_id=room_id)
        return room

    def stop_recording(self, room_id: str) -> MeetingRoom | None:
        room = self._rooms.get(room_id)
        if room:
            room.stop_recording()
            logger.info("recording_stopped", room_id=room_id)
        return room

    def list_rooms(
        self,
        *,
        host_id: str | None = None,
        workspace_id: str | None = None,
        status: RoomStatus | None = None,
    ) -> list[MeetingRoom]:
        rooms = list(self._rooms.values())
        if host_id:
            rooms = [r for r in rooms if r.host_id == host_id]
        if workspace_id:
            rooms = [r for r in rooms if r.workspace_id == workspace_id]
        if status:
            rooms = [r for r in rooms if r.status == status]
        return rooms

    def delete_room(self, room_id: str) -> bool:
        return self._rooms.pop(room_id, None) is not None

    def get_status(self) -> dict[str, Any]:
        rooms = list(self._rooms.values())
        return {
            "total_rooms": len(rooms),
            "active_rooms": sum(1 for r in rooms if r.status == RoomStatus.ACTIVE),
            "lobby_rooms": sum(1 for r in rooms if r.status == RoomStatus.LOBBY),
            "recording_rooms": sum(1 for r in rooms if r.is_recording),
            "ended_rooms": sum(1 for r in rooms if r.status == RoomStatus.ENDED),
            "total_participants": sum(r.participants_count for r in rooms),
        }


room_manager = RoomManager()
