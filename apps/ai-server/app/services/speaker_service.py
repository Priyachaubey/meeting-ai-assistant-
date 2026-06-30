"""Speaker identification and diarization service.

Provides speaker identification, diarization, timeline tracking,
statistics, confidence scoring, and color coding for meeting participants.
Integrates with pyannote.audio for ML-based speaker diarization when available.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Any


# Module-level reference to ML diarization provider (set by main.py)
_diarizer: Any = None


@dataclass
class SpeakerProfile:
    """A known speaker profile for identification."""

    speaker_id: str
    display_name: str
    voice_features: dict[str, float] = field(default_factory=dict)
    color: str = "#5B0A8C"
    total_speak_time: float = 0.0
    total_segments: int = 0
    first_seen_ms: float = 0.0
    last_seen_ms: float = 0.0
    word_count: int = 0


@dataclass
class SpeakerSegment:
    """A single speaker segment in the timeline."""

    speaker_id: str
    speaker_name: str
    start_ms: float
    end_ms: float
    text: str
    confidence: float = 0.95
    word_count: int = 0

    def to_dict(self) -> dict:
        return {
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.end_ms - self.start_ms,
            "text": self.text,
            "confidence": self.confidence,
            "word_count": self.word_count,
        }


@dataclass
class SpeakerStats:
    """Aggregated statistics for a speaker in a meeting."""

    speaker_id: str
    speaker_name: str
    total_speak_time_ms: float = 0.0
    segment_count: int = 0
    word_count: int = 0
    avg_segment_duration_ms: float = 0.0
    speak_percentage: float = 0.0
    color: str = "#5B0A8C"

    def to_dict(self) -> dict:
        return {
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "total_speak_time_ms": round(self.total_speak_time_ms, 1),
            "segment_count": self.segment_count,
            "word_count": self.word_count,
            "avg_segment_duration_ms": round(self.avg_segment_duration_ms, 1),
            "speak_percentage": round(self.speak_percentage, 1),
            "color": self.color,
        }


SPEAKER_COLORS = [
    "#5B0A8C",
    "#2563EB",
    "#059669",
    "#D97706",
    "#DC2626",
    "#7C3AED",
    "#0891B2",
    "#4F46E5",
    "#BE185D",
    "#65A30D",
    "#0D9488",
    "#6366F1",
    "#E11D48",
    "#CA8A04",
    "#9333EA",
]


class SpeakerService:
    """Speaker identification, diarization, and timeline tracking."""

    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, Any]] = {}

    def _get_room(self, room_id: str) -> dict[str, Any]:
        if room_id not in self._rooms:
            self._rooms[room_id] = {
                "profiles": {},
                "segments": [],
                "color_index": 0,
                "start_time_ms": time.time() * 1000,
            }
        return self._rooms[room_id]

    def _assign_color(self, room: dict[str, Any]) -> str:
        color = SPEAKER_COLORS[room["color_index"] % len(SPEAKER_COLORS)]
        room["color_index"] += 1
        return color

    def register_speaker(
        self, room_id: str, speaker_id: str, display_name: str
    ) -> SpeakerProfile:
        """Register a known speaker in a meeting room."""
        room = self._get_room(room_id)
        if speaker_id in room["profiles"]:
            profile = room["profiles"][speaker_id]
            profile.display_name = display_name
            return profile

        color = self._assign_color(room)
        profile = SpeakerProfile(
            speaker_id=speaker_id,
            display_name=display_name,
            color=color,
            first_seen_ms=time.time() * 1000,
        )
        room["profiles"][speaker_id] = profile
        return profile

    def add_segment(
        self,
        room_id: str,
        speaker_id: str,
        speaker_name: str,
        text: str,
        start_ms: float | None = None,
        end_ms: float | None = None,
        confidence: float = 0.95,
    ) -> SpeakerSegment:
        """Add a speaker segment to the timeline."""
        room = self._get_room(room_id)

        if speaker_id not in room["profiles"]:
            self.register_speaker(room_id, speaker_id, speaker_name)

        now_ms = time.time() * 1000
        if start_ms is None:
            start_ms = now_ms
        if end_ms is None:
            end_ms = now_ms

        word_count = len(text.split())

        segment = SpeakerSegment(
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            start_ms=start_ms,
            end_ms=end_ms,
            text=text,
            confidence=confidence,
            word_count=word_count,
        )
        room["segments"].append(segment)

        profile = room["profiles"][speaker_id]
        profile.total_speak_time += end_ms - start_ms
        profile.total_segments += 1
        profile.last_seen_ms = end_ms
        profile.word_count += word_count
        profile.display_name = speaker_name

        return segment

    def get_timeline(self, room_id: str) -> list[dict]:
        """Get the full speaker timeline for a meeting."""
        room = self._get_room(room_id)
        return [s.to_dict() for s in room["segments"]]

    def get_speakers(self, room_id: str) -> list[dict]:
        """Get all registered speakers with their profiles."""
        room = self._get_room(room_id)
        result = []
        for pid, profile in room["profiles"].items():
            result.append(
                {
                    "speaker_id": profile.speaker_id,
                    "display_name": profile.display_name,
                    "color": profile.color,
                    "total_segments": profile.total_segments,
                    "word_count": profile.word_count,
                }
            )
        return result

    def get_statistics(self, room_id: str) -> list[dict]:
        """Get speaking statistics per speaker."""
        room = self._get_room(room_id)
        if not room["segments"]:
            return []

        total_time = sum(
            s.end_ms - s.start_ms for s in room["segments"] if s.end_ms > s.start_ms
        )
        if total_time == 0:
            total_time = 1.0

        stats_map: dict[str, SpeakerStats] = {}
        for seg in room["segments"]:
            if seg.speaker_id not in stats_map:
                profile = room["profiles"].get(seg.speaker_id)
                color = profile.color if profile else "#5B0A8C"
                stats_map[seg.speaker_id] = SpeakerStats(
                    speaker_id=seg.speaker_id,
                    speaker_name=seg.speaker_name,
                    color=color,
                )
            st = stats_map[seg.speaker_id]
            st.segment_count += 1
            st.word_count += seg.word_count
            st.total_speak_time_ms += seg.end_ms - seg.start_ms

        for st in stats_map.values():
            st.speak_percentage = (st.total_speak_time_ms / total_time) * 100
            if st.segment_count > 0:
                st.avg_segment_duration_ms = st.total_speak_time_ms / st.segment_count

        return sorted(
            [s.to_dict() for s in stats_map.values()],
            key=lambda x: x["speak_percentage"],
            reverse=True,
        )

    def get_speaker_color(self, room_id: str, speaker_id: str) -> str:
        """Get the assigned color for a speaker."""
        room = self._get_room(room_id)
        profile = room["profiles"].get(speaker_id)
        return profile.color if profile else "#5B0A8C"

    def identify_speaker(
        self, room_id: str, audio_features: dict[str, float]
    ) -> tuple[str, float] | None:
        """Identify a speaker from audio features using voice embedding similarity."""
        room = self._get_room(room_id)
        if not room["profiles"]:
            return None

        best_match = None
        best_score = 0.0
        for pid, profile in room["profiles"].items():
            if not profile.voice_features:
                continue
            score = self._cosine_similarity(audio_features, profile.voice_features)
            if score > best_score:
                best_score = score
                best_match = pid

        if best_match and best_score > 0.5:
            return (best_match, best_score)
        return None

    def _cosine_similarity(self, a: dict[str, float], b: dict[str, float]) -> float:
        """Compute cosine similarity between two feature dictionaries."""
        common_keys = set(a.keys()) & set(b.keys())
        if not common_keys:
            return 0.0
        dot = sum(a[k] * b[k] for k in common_keys)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def diarize_audio(
        self, room_id: str, audio_bytes: bytes, num_speakers: int | None = None
    ) -> list[dict]:
        """Run ML-based speaker diarization on audio bytes.

        Uses pyannote.audio if available, otherwise returns a single-speaker segment.
        The diarization result is automatically added to the room timeline.
        """
        if _diarizer is not None:
            try:
                segments = await _diarizer.diarize(
                    audio_bytes, num_speakers=num_speakers
                )
                # Register discovered speakers and add segments
                for seg in segments:
                    speaker_label = seg.get("speaker", "SPEAKER_00")
                    speaker_id = f"{room_id}_{speaker_label}"
                    if speaker_id not in self._get_room(room_id)["profiles"]:
                        self.register_speaker(room_id, speaker_id, speaker_label)
                    self.add_segment(
                        room_id=room_id,
                        speaker_id=speaker_id,
                        speaker_name=speaker_label,
                        text="",
                        start_ms=seg.get("start", 0.0) * 1000,
                        end_ms=seg.get("end", 0.0) * 1000,
                        confidence=seg.get("confidence", 0.9),
                    )
                return segments
            except Exception as exc:
                import logging

                logging.getLogger("convopilot").warning(
                    "diarization_failed", error=str(exc)
                )

        # Fallback: single speaker segment
        duration = len(audio_bytes) / 32000.0 if audio_bytes else 0.0
        speaker_id = f"{room_id}_SPEAKER_00"
        self.add_segment(
            room_id=room_id,
            speaker_id=speaker_id,
            speaker_name="Speaker 1",
            text="",
            start_ms=0.0,
            end_ms=duration * 1000,
        )
        return [
            {
                "speaker": "SPEAKER_00",
                "start": 0.0,
                "end": duration,
                "confidence": 0.5,
            }
        ]

    def cleanup_room(self, room_id: str) -> None:
        """Clean up room data."""
        self._rooms.pop(room_id, None)

    def get_status(self) -> dict:
        """Get service status."""
        total_segments = sum(len(r["segments"]) for r in self._rooms.values())
        total_speakers = sum(len(r["profiles"]) for r in self._rooms.values())
        return {
            "active_rooms": len(self._rooms),
            "total_segments": total_segments,
            "total_speakers": total_speakers,
        }


speaker_service = SpeakerService()
