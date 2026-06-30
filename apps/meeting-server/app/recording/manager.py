"""Recording Manager – controls meeting recording state.

Actual recording implementation depends on the media server
(WebRTC SFU). This manager tracks recording state and metadata.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class RecordingStatus(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Recording:
    """Represents a meeting recording."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    room_id: str = ""
    started_by: str = ""
    status: RecordingStatus = RecordingStatus.IDLE
    started_at: datetime.datetime | None = None
    stopped_at: datetime.datetime | None = None
    duration_seconds: float = 0.0
    file_path: str | None = None
    file_size_bytes: int = 0
    format: str = "webm"
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self, started_by: str) -> None:
        self.status = RecordingStatus.RECORDING
        self.started_by = started_by
        self.started_at = datetime.datetime.now(datetime.timezone.utc)

    def stop(self) -> None:
        self.status = RecordingStatus.COMPLETED
        self.stopped_at = datetime.datetime.now(datetime.timezone.utc)
        if self.started_at:
            self.duration_seconds = (self.stopped_at - self.started_at).total_seconds()

    def pause(self) -> None:
        self.status = RecordingStatus.PAUSED

    def resume(self) -> None:
        self.status = RecordingStatus.RECORDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "started_by": self.started_by,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "duration_seconds": self.duration_seconds,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "format": self.format,
        }


class RecordingManager:
    """Manages recording sessions for meetings."""

    def __init__(self) -> None:
        self._recordings: dict[str, Recording] = {}  # recording_id -> Recording
        self._room_recordings: dict[str, str] = {}  # room_id -> recording_id

    def start_recording(self, room_id: str, started_by: str) -> Recording:
        """Start a new recording for a room."""
        if room_id in self._room_recordings:
            existing = self._recordings.get(self._room_recordings[room_id])
            if existing and existing.status == RecordingStatus.RECORDING:
                return existing

        recording = Recording(room_id=room_id)
        recording.start(started_by)
        self._recordings[recording.id] = recording
        self._room_recordings[room_id] = recording.id
        logger.info("recording_started", recording_id=recording.id, room_id=room_id)
        return recording

    def stop_recording(self, room_id: str) -> Recording | None:
        recording_id = self._room_recordings.get(room_id)
        if not recording_id:
            return None
        recording = self._recordings.get(recording_id)
        if recording:
            recording.stop()
            logger.info(
                "recording_stopped",
                recording_id=recording_id,
                duration=recording.duration_seconds,
            )
        return recording

    def get_recording(self, recording_id: str) -> Recording | None:
        return self._recordings.get(recording_id)

    def get_room_recording(self, room_id: str) -> Recording | None:
        recording_id = self._room_recordings.get(room_id)
        if recording_id:
            return self._recordings.get(recording_id)
        return None

    def list_room_recordings(self, room_id: str) -> list[Recording]:
        return [r for r in self._recordings.values() if r.room_id == room_id]

    def get_status(self) -> dict[str, Any]:
        total = len(self._recordings)
        active = sum(
            1
            for r in self._recordings.values()
            if r.status == RecordingStatus.RECORDING
        )
        return {
            "total_recordings": total,
            "active_recordings": active,
        }


recording_manager = RecordingManager()
