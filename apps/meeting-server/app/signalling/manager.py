"""WebRTC Signalling Manager – handles WebRTC offer/answer/ICE exchange.

This manager coordinates WebRTC signalling between participants
for peer-to-peer media streams.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class SignallingMessage:
    """Standardized WebRTC signalling messages."""

    @staticmethod
    def offer(sender_id: str, target_id: str, sdp: dict) -> dict[str, Any]:
        return {
            "type": "offer",
            "sender_id": sender_id,
            "target_id": target_id,
            "sdp": sdp,
        }

    @staticmethod
    def answer(sender_id: str, target_id: str, sdp: dict) -> dict[str, Any]:
        return {
            "type": "answer",
            "sender_id": sender_id,
            "target_id": target_id,
            "sdp": sdp,
        }

    @staticmethod
    def ice_candidate(
        sender_id: str, target_id: str, candidate: dict
    ) -> dict[str, Any]:
        return {
            "type": "ice_candidate",
            "sender_id": sender_id,
            "target_id": target_id,
            "candidate": candidate,
        }

    @staticmethod
    def participant_joined(participant: dict) -> dict[str, Any]:
        return {"type": "participant_joined", "participant": participant}

    @staticmethod
    def participant_left(participant_id: str, user_id: str) -> dict[str, Any]:
        return {
            "type": "participant_left",
            "participant_id": participant_id,
            "user_id": user_id,
        }

    @staticmethod
    def media_state_changed(participant_id: str, media: dict) -> dict[str, Any]:
        return {
            "type": "media_state_changed",
            "participant_id": participant_id,
            "media": media,
        }

    @staticmethod
    def room_state_changed(state: dict) -> dict[str, Any]:
        return {"type": "room_state_changed", "state": state}

    @staticmethod
    def chat_message(message: dict) -> dict[str, Any]:
        return {"type": "chat_message", "message": message}

    @staticmethod
    def hand_raised(participant_id: str, raised: bool) -> dict[str, Any]:
        return {
            "type": "hand_raised",
            "participant_id": participant_id,
            "raised": raised,
        }

    @staticmethod
    def emoji_reaction(participant_id: str, emoji: str) -> dict[str, Any]:
        return {
            "type": "emoji_reaction",
            "participant_id": participant_id,
            "emoji": emoji,
        }

    @staticmethod
    def error(message: str) -> dict[str, Any]:
        return {"type": "error", "message": message}


class SignallingManager:
    """Coordinates WebRTC signalling between participants."""

    def __init__(self) -> None:
        self._pending_offers: dict[str, list[dict]] = {}

    async def route_message(
        self,
        room_id: str,
        sender_id: str,
        message: dict[str, Any],
        broadcast_fn: Any,
        send_fn: Any,
    ) -> None:
        """Route a signalling message to the appropriate target."""
        msg_type = message.get("type")
        target_id = message.get("target_id")

        if msg_type in ("offer", "answer", "ice_candidate") and target_id:
            # Point-to-point signalling
            await send_fn(target_id, message)
        elif msg_type in (
            "participant_joined",
            "participant_left",
            "media_state_changed",
            "hand_raised",
            "emoji_reaction",
        ):
            # Broadcast to room
            await broadcast_fn(room_id, message, exclude=sender_id)
        else:
            logger.warning("unknown_signalling_type", type=msg_type, room_id=room_id)


signalling_manager = SignallingManager()
