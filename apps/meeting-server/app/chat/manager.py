"""Chat Manager – in-meeting real-time chat."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class ChatMessage:
    """A single chat message within a meeting."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    room_id: str = ""
    sender_id: str = ""
    sender_name: str = ""
    content: str = ""
    message_type: str = "text"  # text | system | file
    file_url: str | None = None
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    edited: bool = False
    deleted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "content": self.content,
            "message_type": self.message_type,
            "file_url": self.file_url,
            "created_at": self.created_at.isoformat(),
            "edited": self.edited,
            "deleted": self.deleted,
        }


class ChatManager:
    """Manages in-meeting chat messages."""

    def __init__(self) -> None:
        self._messages: dict[str, list[ChatMessage]] = {}  # room_id -> messages

    def add_message(
        self,
        *,
        room_id: str,
        sender_id: str,
        sender_name: str,
        content: str,
        message_type: str = "text",
        file_url: str | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            room_id=room_id,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            message_type=message_type,
            file_url=file_url,
        )
        if room_id not in self._messages:
            self._messages[room_id] = []
        self._messages[room_id].append(msg)
        logger.info(
            "chat_message", room_id=room_id, sender_id=sender_id, type=message_type
        )
        return msg

    def get_messages(self, room_id: str, limit: int = 100) -> list[ChatMessage]:
        messages = self._messages.get(room_id, [])
        return messages[-limit:]

    def delete_message(self, room_id: str, message_id: str) -> bool:
        for msg in self._messages.get(room_id, []):
            if msg.id == message_id:
                msg.deleted = True
                return True
        return False

    def clear_room(self, room_id: str) -> None:
        self._messages.pop(room_id, None)

    def get_status(self) -> dict[str, Any]:
        total = sum(len(msgs) for msgs in self._messages.values())
        return {
            "total_messages": total,
            "rooms_with_chat": len(self._messages),
        }


chat_manager = ChatManager()
