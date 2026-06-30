"""Shared helper for minting short-lived service-to-service auth tokens.

Found duplicated verbatim in ai_translate_client.py and audio_transcription.py during a
duplicate-code audit — both call apps/ai-server on this service's own behalf (not on behalf
of any specific end user), and both need exactly the same token. Consolidated here rather
than each module calling create_access_token(sub="meeting-service", role="service") directly.
"""

from __future__ import annotations

from app.core.security import create_access_token


def mint_ai_server_token() -> str:
    """A token identifying this service (not any particular end user) for calls to
    apps/ai-server. Minted fresh per call — these are short, frequent, server-to-server
    requests, not something worth a caching/refresh-token layer for."""
    return create_access_token(sub="meeting-service", role="service")
