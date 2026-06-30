"""Memory Manager – conversation and context memory for AI agents.

Provides short-term (session) and long-term (persistent) memory
for AI interactions across all products.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class MemoryEntry:
    """A single memory entry."""

    key: str
    content: str
    role: str = "user"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    ttl_seconds: int | None = None


@dataclass
class ConversationMemory:
    """In-memory conversation history for a session."""

    session_id: str
    entries: list[MemoryEntry] = field(default_factory=list)
    max_entries: int = 100
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

    def get_messages(self, limit: int | None = None) -> list[dict[str, str]]:
        """Return entries as LLM-compatible message dicts."""
        entries = self.entries[-limit:] if limit else self.entries
        return [{"role": e.role, "content": e.content} for e in entries]

    def clear(self) -> None:
        self.entries.clear()


class MemoryManager:
    """Manages conversation memory across sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationMemory] = {}

    def get_or_create(
        self, session_id: str, max_entries: int = 100
    ) -> ConversationMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationMemory(
                session_id=session_id, max_entries=max_entries
            )
            logger.info("memory_session_created", session_id=session_id)
        return self._sessions[session_id]

    def get(self, session_id: str) -> ConversationMemory | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        logger.info("memory_session_deleted", session_id=session_id)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    def get_status(self) -> dict[str, Any]:
        return {
            "active_sessions": len(self._sessions),
            "total_entries": sum(len(s.entries) for s in self._sessions.values()),
        }


memory_manager = MemoryManager()
