"""Turns raw mic audio frames (sent over the room WebSocket) into real transcript entries.

This is the missing link in the pipeline this product's own docs describe:

    Mic Audio -> Meeting Server -> AI Server -> Speech Recognition -> Transcript

The receiving/display side of this (the `transcript`/`translation`/`ai_update` WebSocket
broadcasts) already existed and worked — see meeting-room.tsx's handleWSMessage. What never
existed was anything that produced a transcript entry from real audio; the only thing that
ever called `transcript_manager.add_transcript()` was the `transcript` WS message type, which
expects already-transcribed text — there was no audio-in path at all.

Approach: same utterance-segmentation pattern as apps/api/app/services/speech/
ai_server_provider.py (built earlier in this project for the OTHER live-meeting feature) —
buffer audio while an energy-based VAD detects speech, finalize and transcribe on trailing
silence — ported here because meeting-server's room WebSocket is a different connection
entirely from apps/api's, with its own audio stream per participant.
"""

from __future__ import annotations

import base64
import time

import httpx
import structlog

from app.core.config import settings
from app.services.service_auth import mint_ai_server_token

logger = structlog.get_logger()

# PCM16 mono, 16kHz — matches the sample rate the browser-side capture is expected to send
# (see apps/web's audio-capture utility). 2 bytes/sample.
_BYTES_PER_SECOND = 16000 * 2
_SILENCE_SECONDS_TO_FINALIZE = 0.6
_MAX_UTTERANCE_SECONDS = 25.0
_MIN_UTTERANCE_SECONDS = 0.3
_SILENCE_ENERGY_THRESHOLD = 500  # same threshold as apps/api's VoiceActivityDetector


def _frame_is_speech(frame: bytes) -> bool:
    """Simple energy-based VAD — same approach as apps/api/app/services/vad.py, kept as a
    self-contained copy here rather than a cross-service import (these are two genuinely
    separate Python processes/deployments; importing across apps/api and apps/meeting-server
    would mean coupling their packaging, not appropriate for what's a ~10-line function)."""
    if len(frame) < 2:
        return False
    samples = len(frame) // 2
    total = 0
    for i in range(0, samples * 2, 2):
        sample = int.from_bytes(frame[i : i + 2], byteorder="little", signed=True)
        total += abs(sample)
    return (total / samples) > _SILENCE_ENERGY_THRESHOLD


class _ConnectionAudioState:
    __slots__ = ("buffer", "speaking", "silence_bytes")

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.speaking = False
        self.silence_bytes = 0


class AudioTranscriptionSession:
    """One instance per active room WebSocket connection — tracks that connection's
    in-progress utterance buffer. Created and torn down alongside the WS connection itself
    (see meetings.py's audio_chunk handling and its `finally` cleanup)."""

    def __init__(self) -> None:
        self._state = _ConnectionAudioState()

    async def feed_frame(self, pcm_b64: str) -> bytes | None:
        """Feed one base64-encoded PCM16 frame. Returns the finalized utterance's raw bytes
        when a pause (or the max-length safety cap) completes one, otherwise None."""
        try:
            frame = base64.b64decode(pcm_b64)
        except Exception:
            logger.warning("audio_frame_decode_failed")
            return None

        s = self._state
        is_speech = _frame_is_speech(frame)

        if is_speech:
            s.speaking = True
            s.silence_bytes = 0
            s.buffer.extend(frame)
        elif s.speaking:
            s.buffer.extend(frame)
            s.silence_bytes += len(frame)

        if s.speaking and s.silence_bytes >= _SILENCE_SECONDS_TO_FINALIZE * _BYTES_PER_SECOND:
            return self._finalize()
        if s.speaking and len(s.buffer) >= _MAX_UTTERANCE_SECONDS * _BYTES_PER_SECOND:
            return self._finalize(keep_speaking=True)
        return None

    def _finalize(self, keep_speaking: bool = False) -> bytes | None:
        s = self._state
        result = bytes(s.buffer) if len(s.buffer) >= _MIN_UTTERANCE_SECONDS * _BYTES_PER_SECOND else None
        s.buffer = bytearray()
        s.silence_bytes = 0
        s.speaking = keep_speaking
        return result

    def flush(self) -> bytes | None:
        """Call on disconnect — return whatever's buffered rather than discarding the last
        few seconds someone said right before leaving."""
        return self._finalize()


async def transcribe_via_ai_server(pcm_bytes: bytes, language: str = "auto") -> str | None:
    """Sends one utterance's raw audio to apps/ai-server's /api/ai/transcribe. Returns None
    (rather than raising) on failure — a single dropped utterance shouldn't kill the whole
    room's WebSocket connection; the next utterance gets another chance."""
    token = mint_ai_server_token()
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.ai_server_url.rstrip('/')}/api/ai/transcribe",
                params={"language": language},
                files={"file": ("utterance.pcm", pcm_bytes, "application/octet-stream")},
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as exc:
        logger.error("transcription_request_failed", error=str(exc))
        return None

    if resp.status_code != 200:
        logger.error("transcription_bad_status", status=resp.status_code, body=resp.text[:300])
        return None

    try:
        text = resp.json().get("text", "")
    except ValueError:
        logger.error("transcription_bad_response_shape")
        return None

    logger.info(
        "transcription_completed",
        chars=len(text),
        latency_ms=round((time.monotonic() - start) * 1000, 1),
    )
    return text.strip() or None
