import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from urllib.parse import urlencode

import websockets

from app.core.config import settings
from app.services.speech.base import TranscriptionProvider, TranscriptionProviderError

logger = logging.getLogger("convopilot.speech.deepgram")

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class DeepgramProvider(TranscriptionProvider):
    """Streams raw audio to Deepgram's real-time API and yields finalized transcript segments.

    NOTE: written against Deepgram's documented v1/listen streaming contract from training
    knowledge, not verified against a live connection (this sandbox has no network access).
    Before relying on this in production, confirm against https://developers.deepgram.com
    that the auth header, query params, and `websockets` library API below still match —
    in particular the `extra_headers` kwarg name on `websockets.connect`, which is why
    `websockets` is pinned in requirements.txt rather than left floating.
    """

    name = "deepgram"

    def __init__(self) -> None:
        if not settings.deepgram_api_key:
            raise TranscriptionProviderError("DEEPGRAM_API_KEY is not set — configure it in .env.")
        self._api_key = settings.deepgram_api_key

    def _connection_url(self) -> str:
        params = {
            "encoding": "linear16",
            "sample_rate": str(settings.audio_sample_rate_hz),
            "channels": "1",
            "model": settings.deepgram_model,
            "punctuate": "true",
            "smart_format": "true",
            "interim_results": "false",
        }
        return f"{DEEPGRAM_WS_URL}?{urlencode(params)}"

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        headers = {"Authorization": f"Token {self._api_key}"}
        try:
            async with websockets.connect(self._connection_url(), extra_headers=headers, ping_interval=5) as ws:
                sender = asyncio.create_task(self._send_audio(ws, audio))
                try:
                    async for raw_message in ws:
                        transcript = self._extract_transcript(raw_message)
                        if transcript:
                            yield transcript
                finally:
                    sender.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await sender
        except OSError as exc:
            raise TranscriptionProviderError(f"Deepgram connection failed: {exc}") from exc
        except websockets.exceptions.WebSocketException as exc:
            raise TranscriptionProviderError(f"Deepgram websocket error: {exc}") from exc

    @staticmethod
    async def _send_audio(ws, audio: AsyncIterator[bytes]) -> None:
        try:
            async for frame in audio:
                await ws.send(frame)
        finally:
            with contextlib.suppress(Exception):
                await ws.send(json.dumps({"type": "CloseStream"}))

    @staticmethod
    def _extract_transcript(raw_message: bytes | str) -> str | None:
        try:
            payload = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            return None
        if payload.get("type") != "Results":
            return None
        alternatives = payload.get("channel", {}).get("alternatives", [])
        if not alternatives:
            return None
        transcript = alternatives[0].get("transcript", "")
        if transcript and payload.get("is_final", True):
            return transcript
        return None
