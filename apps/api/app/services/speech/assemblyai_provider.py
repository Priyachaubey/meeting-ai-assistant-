import asyncio
import base64
import contextlib
import json
from collections.abc import AsyncIterator

import websockets

from app.core.config import settings
from app.services.speech.base import TranscriptionProvider, TranscriptionProviderError

ASSEMBLYAI_WS_URL = "wss://api.assemblyai.com/v2/realtime/ws"


class AssemblyAIProvider(TranscriptionProvider):
    """Written against AssemblyAI's documented v2 real-time WebSocket protocol from training
    knowledge — not exercised against a live connection (no network access in this sandbox),
    same caveat as DeepgramProvider. Two protocol differences from Deepgram worth being
    explicit about, since they're easy to get wrong porting code between the two: (1)
    AssemblyAI's real-time API takes base64-encoded JSON audio messages, not raw binary
    frames — encoded here so the abstract `stream(audio: AsyncIterator[bytes])` interface
    stays identical regardless of which provider is behind it. (2) Auth is the permanent API
    key directly in the `Authorization` header, which is correct for a server-to-server
    connection like this one (our backend connecting out) — AssemblyAI's docs recommend a
    short-lived token instead specifically for browser-direct connections, which isn't what
    this is."""

    name = "assemblyai"

    def __init__(self) -> None:
        if not settings.assemblyai_api_key:
            raise TranscriptionProviderError("ASSEMBLYAI_API_KEY is not set — configure it in .env.")
        self._api_key = settings.assemblyai_api_key

    def _connection_url(self) -> str:
        return f"{ASSEMBLYAI_WS_URL}?sample_rate={settings.audio_sample_rate_hz}"

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        headers = {"Authorization": self._api_key}
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
            raise TranscriptionProviderError(f"AssemblyAI connection failed: {exc}") from exc
        except websockets.exceptions.WebSocketException as exc:
            raise TranscriptionProviderError(f"AssemblyAI websocket error: {exc}") from exc

    @staticmethod
    async def _send_audio(ws, audio: AsyncIterator[bytes]) -> None:
        try:
            async for frame in audio:
                await ws.send(json.dumps({"audio_data": base64.b64encode(frame).decode("ascii")}))
        finally:
            with contextlib.suppress(Exception):
                await ws.send(json.dumps({"terminate_session": True}))

    @staticmethod
    def _extract_transcript(raw_message: bytes | str) -> str | None:
        try:
            payload = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            return None
        if payload.get("message_type") != "FinalTranscript":
            return None  # ignore PartialTranscript — same "only finalized segments" contract as Deepgram
        text = payload.get("text", "")
        return text if text else None
