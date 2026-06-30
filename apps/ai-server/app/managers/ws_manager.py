"""WebSocket Manager – connection lifecycle for AI Server WebSocket endpoints."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class WSConnection:
    """Wrapper around a FastAPI WebSocket with metadata."""

    def __init__(
        self,
        ws: WebSocket,
        connection_id: str,
        user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.ws = ws
        self.connection_id = connection_id
        self.user_id = user_id
        self.metadata = metadata or {}
        self.connected_at = time.monotonic()
        self.last_activity = time.monotonic()
        self._closed = False

    async def send_json(self, data: dict[str, Any]) -> None:
        if self._closed:
            return
        self.last_activity = time.monotonic()
        await self.ws.send_json(data)

    async def send_text(self, data: str) -> None:
        if self._closed:
            return
        self.last_activity = time.monotonic()
        await self.ws.send_text(data)

    async def receive_json(self) -> dict[str, Any]:
        data = await self.ws.receive_json()
        self.last_activity = time.monotonic()
        return data

    async def receive_text(self) -> str:
        data = await self.ws.receive_text()
        self.last_activity = time.monotonic()
        return data

    async def close(self, code: int = 1000) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self.ws.close(code=code)
        except Exception:
            pass

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self.connected_at


class WebSocketManager:
    """Manages all active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: dict[str, WSConnection] = {}
        self._rooms: dict[str, set[str]] = {}  # room_id -> set of connection_ids

    async def connect(
        self,
        ws: WebSocket,
        connection_id: str,
        user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> WSConnection:
        await ws.accept()
        conn = WSConnection(ws, connection_id, user_id, metadata)
        self._connections[connection_id] = conn
        logger.info("ws_connected", connection_id=connection_id, user_id=user_id)
        return conn

    def disconnect(self, connection_id: str) -> None:
        self._connections.pop(connection_id, None)
        for room_connections in self._rooms.values():
            room_connections.discard(connection_id)
        logger.info("ws_disconnected", connection_id=connection_id)

    def join_room(self, room_id: str, connection_id: str) -> None:
        if room_id not in self._rooms:
            self._rooms[room_id] = set()
        self._rooms[room_id].add(connection_id)

    def leave_room(self, room_id: str, connection_id: str) -> None:
        if room_id in self._rooms:
            self._rooms[room_id].discard(connection_id)

    async def broadcast_to_room(
        self, room_id: str, data: dict[str, Any], exclude: str | None = None
    ) -> int:
        """Send a message to all connections in a room. Returns count of successful sends."""
        sent = 0
        for cid in self._rooms.get(room_id, set()):
            if cid == exclude:
                continue
            conn = self._connections.get(cid)
            if conn and not conn.is_closed:
                try:
                    await conn.send_json(data)
                    sent += 1
                except Exception:
                    pass
        return sent

    async def send_to(self, connection_id: str, data: dict[str, Any]) -> bool:
        conn = self._connections.get(connection_id)
        if conn and not conn.is_closed:
            try:
                await conn.send_json(data)
                return True
            except Exception:
                return False
        return False

    def get_connection(self, connection_id: str) -> WSConnection | None:
        return self._connections.get(connection_id)

    def get_room_connections(self, room_id: str) -> list[WSConnection]:
        return [
            self._connections[cid]
            for cid in self._rooms.get(room_id, set())
            if cid in self._connections
        ]

    def get_status(self) -> dict[str, Any]:
        return {
            "active_connections": len(self._connections),
            "active_rooms": len(self._rooms),
            "connections": [
                {
                    "id": c.connection_id,
                    "user_id": c.user_id,
                    "uptime_seconds": round(c.uptime_seconds, 2),
                }
                for c in self._connections.values()
            ],
        }


ws_manager = WebSocketManager()
