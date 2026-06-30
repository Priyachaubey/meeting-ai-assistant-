"""Whiteboard Manager – in-meeting collaborative drawing state.

Mirrors apps/meeting-server/app/chat/manager.py's pattern exactly (same in-memory,
per-room dict structure) rather than inventing a different shape for what's structurally
the same kind of thing: an append-only-ish list of room-scoped events that needs to be
replayed to anyone who joins after they happened, and broadcast live to everyone already
connected. No new persistence layer, no new server — same in-memory model every other
real-time feature in this service already uses.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog

logger = structlog.get_logger()

StrokeTool = Literal["pencil", "rectangle", "ellipse", "line", "text", "eraser"]


@dataclass
class WhiteboardStroke:
    """One drawing action — a pencil/eraser path, a shape, or a text element. `points` holds
    whatever the tool needs: a pencil/eraser path is a flat [x1,y1,x2,y2,...] list; a shape
    is its two corner points; text is a single [x,y] anchor point (with the actual string in
    `text`). Kept deliberately generic rather than one dataclass per tool — the frontend
    already knows how to interpret each tool's own point shape, and a single broadcast/replay
    path for all of them is simpler and has less duplication than five near-identical ones.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    room_id: str = ""
    user_id: str = ""
    tool: StrokeTool = "pencil"
    points: list[float] = field(default_factory=list)
    color: str = "#000000"
    width: float = 3.0
    text: str | None = None
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "user_id": self.user_id,
            "tool": self.tool,
            "points": self.points,
            "color": self.color,
            "width": self.width,
            "text": self.text,
            "created_at": self.created_at.isoformat(),
        }


class WhiteboardManager:
    """Manages in-meeting whiteboard strokes — append-only per room, with undo implemented
    as "remove the most recent stroke" rather than a full document-diff/CRDT history. This is
    a deliberate scoping choice: real per-user undo (undoing only *your own* last stroke,
    independent of what anyone else drew after it) needs an operation-transform or CRDT-style
    structure — meaningfully more complex than a shared whiteboard needs to ship a working
    undo button. "Undo removes the globally most recent stroke" is what most simple
    collaborative whiteboards actually do, and matches what redo (re-adding the most recently
    undone stroke) needs to mirror it.
    """

    def __init__(self) -> None:
        self._strokes: dict[str, list[WhiteboardStroke]] = {}
        self._undone: dict[str, list[WhiteboardStroke]] = {}  # for redo

    def add_stroke(
        self,
        *,
        room_id: str,
        user_id: str,
        tool: StrokeTool,
        points: list[float],
        color: str = "#000000",
        width: float = 3.0,
        text: str | None = None,
    ) -> WhiteboardStroke:
        stroke = WhiteboardStroke(
            room_id=room_id, user_id=user_id, tool=tool, points=points,
            color=color, width=width, text=text,
        )
        self._strokes.setdefault(room_id, []).append(stroke)
        # A fresh stroke invalidates whatever redo history existed — same behavior as any
        # standard undo/redo stack (drawing something new after undoing means there's no
        # longer a single linear "redo" path back to where you were).
        self._undone.pop(room_id, None)
        return stroke

    def get_strokes(self, room_id: str) -> list[WhiteboardStroke]:
        return self._strokes.get(room_id, [])

    def undo(self, room_id: str) -> WhiteboardStroke | None:
        strokes = self._strokes.get(room_id, [])
        if not strokes:
            return None
        stroke = strokes.pop()
        self._undone.setdefault(room_id, []).append(stroke)
        return stroke

    def redo(self, room_id: str) -> WhiteboardStroke | None:
        undone = self._undone.get(room_id, [])
        if not undone:
            return None
        stroke = undone.pop()
        self._strokes.setdefault(room_id, []).append(stroke)
        return stroke

    def clear(self, room_id: str) -> None:
        self._strokes.pop(room_id, None)
        self._undone.pop(room_id, None)

    def get_status(self) -> dict[str, Any]:
        total = sum(len(s) for s in self._strokes.values())
        return {"total_strokes": total, "rooms_with_whiteboard": len(self._strokes)}


whiteboard_manager = WhiteboardManager()
