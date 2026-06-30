"""Transcript Manager – real-time transcript state for meetings.

Manages per-meeting transcript state, speaker tracking, and
broadcasts transcript updates to all connected participants.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class TranscriptEntry:
    """A single transcript entry."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    room_id: str = ""
    speaker_id: str = ""
    speaker_name: str = ""
    text: str = ""
    timestamp_ms: int = 0
    kind: str = "statement"  # statement | question
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "text": self.text,
            "timestamp_ms": self.timestamp_ms,
            "kind": self.kind,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class TranslationEntry:
    """A translated transcript entry for a specific language."""

    transcript_id: str = ""
    language: str = ""
    translated_text: str = ""
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "transcript_id": self.transcript_id,
            "language": self.language,
            "translated_text": self.translated_text,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MeetingAIState:
    """Live AI state for a meeting."""

    room_id: str = ""
    summary: str = ""
    action_items: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    suggestions: list[str] = field(default_factory=list)
    questions: list[dict[str, str]] = field(default_factory=list)
    last_updated: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "summary": self.summary,
            "action_items": self.action_items,
            "decisions": self.decisions,
            "risks": self.risks,
            "follow_ups": self.follow_ups,
            "sentiment": self.sentiment,
            "suggestions": self.suggestions[-5:],
            "questions": self.questions[-20:],
            "last_updated": self.last_updated.isoformat(),
        }


class TranscriptManager:
    """Manages transcripts, translations, and AI state for all meetings."""

    def __init__(self) -> None:
        self._transcripts: dict[str, list[TranscriptEntry]] = {}
        self._translations: dict[str, list[TranslationEntry]] = {}
        self._ai_states: dict[str, MeetingAIState] = {}
        self._speaker_map: dict[
            str, dict[str, str]
        ] = {}  # room_id -> {user_id: display_name}
        self._meeting_start_times: dict[str, datetime.datetime] = {}

    # ── Transcript ────────────────────────────────────────────────────

    def add_transcript(
        self,
        *,
        room_id: str,
        speaker_id: str,
        speaker_name: str,
        text: str,
        kind: str = "statement",
    ) -> TranscriptEntry:
        if room_id not in self._transcripts:
            self._transcripts[room_id] = []
            self._meeting_start_times[room_id] = datetime.datetime.now(
                datetime.timezone.utc
            )

        start = self._meeting_start_times.get(
            room_id, datetime.datetime.now(datetime.timezone.utc)
        )
        timestamp_ms = int(
            (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
            * 1000
        )

        entry = TranscriptEntry(
            room_id=room_id,
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            text=text,
            timestamp_ms=timestamp_ms,
            kind=kind,
        )
        self._transcripts[room_id].append(entry)

        if room_id not in self._speaker_map:
            self._speaker_map[room_id] = {}
        self._speaker_map[room_id][speaker_id] = speaker_name

        logger.info(
            "transcript_added", room_id=room_id, speaker=speaker_name, kind=kind
        )
        return entry

    def get_transcript(self, room_id: str, limit: int = 200) -> list[TranscriptEntry]:
        return self._transcripts.get(room_id, [])[-limit:]

    def get_transcript_text(self, room_id: str) -> str:
        entries = self._transcripts.get(room_id, [])
        return "\n".join(f"{e.speaker_name}: {e.text}" for e in entries)

    def get_speakers(self, room_id: str) -> list[dict[str, str]]:
        speaker_map = self._speaker_map.get(room_id, {})
        return [{"id": uid, "name": name} for uid, name in speaker_map.items()]

    # ── Translation ───────────────────────────────────────────────────

    def add_translation(
        self,
        *,
        transcript_id: str,
        language: str,
        translated_text: str,
    ) -> TranslationEntry:
        entry = TranslationEntry(
            transcript_id=transcript_id,
            language=language,
            translated_text=translated_text,
        )
        key = transcript_id
        if key not in self._translations:
            self._translations[key] = []
        self._translations[key].append(entry)
        return entry

    def get_translations(
        self, transcript_id: str, language: str | None = None
    ) -> list[TranslationEntry]:
        entries = self._translations.get(transcript_id, [])
        if language:
            entries = [e for e in entries if e.language == language]
        return entries

    # ── AI State ──────────────────────────────────────────────────────

    def get_or_create_ai_state(self, room_id: str) -> MeetingAIState:
        if room_id not in self._ai_states:
            self._ai_states[room_id] = MeetingAIState(room_id=room_id)
        return self._ai_states[room_id]

    def update_ai_state(self, room_id: str, **kwargs: Any) -> MeetingAIState:
        state = self.get_or_create_ai_state(room_id)
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        state.last_updated = datetime.datetime.now(datetime.timezone.utc)
        return state

    def get_ai_state(self, room_id: str) -> MeetingAIState | None:
        return self._ai_states.get(room_id)

    # ── Cleanup ───────────────────────────────────────────────────────

    def cleanup_room(self, room_id: str) -> None:
        self._transcripts.pop(room_id, None)
        self._ai_states.pop(room_id, None)
        self._speaker_map.pop(room_id, None)
        self._meeting_start_times.pop(room_id, None)

    # ── Status ────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        total_entries = sum(len(t) for t in self._transcripts.values())
        total_translations = sum(len(t) for t in self._translations.values())
        return {
            "rooms_with_transcripts": len(self._transcripts),
            "total_transcript_entries": total_entries,
            "total_translations": total_translations,
            "rooms_with_ai_state": len(self._ai_states),
        }


transcript_manager = TranscriptManager()
