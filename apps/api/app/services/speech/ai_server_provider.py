import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.security import create_access_token
from app.services.speech.base import TranscriptionProvider, TranscriptionProviderError
from app.services.vad import VoiceActivityDetector

logger = logging.getLogger("convopilot.speech.ai_server")

# PCM16 mono — matches settings.audio_sample_rate_hz (16000) and what the VAD/whisper side
# already assumes. 2 bytes/sample.
_BYTES_PER_SECOND = settings.audio_sample_rate_hz * 2

# How much trailing silence ends an utterance and triggers transcription of what's buffered
# so far. Deepgram/AssemblyAI do this kind of endpointing internally over a live socket;
# ai-server's /transcribe is a batch endpoint (whole file in, whole transcript out — see its
# docstring in apps/ai-server/app/providers/providers.py), so this provider does the
# endpointing itself and calls that batch endpoint once per detected utterance instead of
# once per whole meeting. From the frontend's perspective this still behaves like live
# transcription — finalized text arrives a beat after each thing someone says, not only at
# the end of the meeting — just with higher per-utterance latency than a real streaming ASR
# API, especially on CPU. That trade-off is inherent to self-hosting today's ai-server as-is,
# not a shortcut taken here; see MERGE_REPORT.md.
_SILENCE_SECONDS_TO_FINALIZE = 0.6
_MAX_UTTERANCE_SECONDS = 25.0  # safety cap so one long ramble doesn't become a 60s request
_MIN_UTTERANCE_SECONDS = 0.3  # drop sub-300ms blips (a cough, a VAD false-trigger) — not worth a request


class AIServerSpeechProvider(TranscriptionProvider):
    """Self-hosted equivalent of DeepgramProvider/AssemblyAIProvider — buffers audio using
    the existing energy-based VoiceActivityDetector (app/services/vad.py — previously
    unused anywhere in this codebase) to find utterance boundaries, then sends each
    complete utterance to ai-server's /api/ai/transcribe (faster-whisper) and yields the
    text back, same `AsyncIterator[bytes] -> AsyncIterator[str]` contract every other
    provider here implements.
    """

    name = "ai-server"

    def __init__(self) -> None:
        self._base_url = settings.ai_server_url.rstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        token = create_access_token(subject="api-service", minutes=5)
        return {"Authorization": f"Bearer {token}"}

    async def _transcribe_utterance(self, pcm_bytes: bytes) -> str | None:
        if len(pcm_bytes) < _MIN_UTTERANCE_SECONDS * _BYTES_PER_SECOND:
            return None
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.post(
                    f"{self._base_url}/api/ai/transcribe",
                    params={"language": "auto"},
                    files={"file": ("utterance.pcm", pcm_bytes, "application/octet-stream")},
                    headers=self._auth_headers(),
                )
        except httpx.RequestError as exc:
            raise TranscriptionProviderError(f"ai-server unreachable at {self._base_url}: {exc}") from exc

        if resp.status_code != 200:
            raise TranscriptionProviderError(f"ai-server returned {resp.status_code}: {resp.text[:300]}")

        try:
            text = resp.json().get("text", "")
        except ValueError as exc:
            raise TranscriptionProviderError(f"ai-server returned a non-JSON response: {resp.text[:300]}") from exc
        return text.strip() or None

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        vad = VoiceActivityDetector()
        buffer = bytearray()
        speaking = False
        silence_bytes = 0

        async for frame in audio:
            is_speech = vad.is_user_speaking(frame)

            if is_speech:
                speaking = True
                silence_bytes = 0
                buffer.extend(frame)
            elif speaking:
                # Keep buffering through short pauses (natural speech has them) rather than
                # cutting the instant energy drops below threshold.
                buffer.extend(frame)
                silence_bytes += len(frame)

            if speaking and silence_bytes >= _SILENCE_SECONDS_TO_FINALIZE * _BYTES_PER_SECOND:
                text = await self._transcribe_utterance(bytes(buffer))
                if text:
                    yield text
                buffer.clear()
                vad.reset()
                speaking = False
                silence_bytes = 0
            elif speaking and len(buffer) >= _MAX_UTTERANCE_SECONDS * _BYTES_PER_SECOND:
                logger.info("ai_server_speech: max utterance length hit, finalizing early")
                text = await self._transcribe_utterance(bytes(buffer))
                if text:
                    yield text
                buffer.clear()
                vad.reset()
                # Deliberately leave `speaking=True`/silence_bytes=0: audio is still actively
                # coming in above the energy threshold, this was a length cap, not a pause.

        # Audio stream ended (mic stopped, connection closing) — flush whatever's left.
        if buffer:
            text = await self._transcribe_utterance(bytes(buffer))
            if text:
                yield text
