"""Realtime translation pipeline for meetings.

Manages per-user language preferences and translates transcript
entries in realtime. Every participant sees the meeting in their
selected language, updating continuously via WebSocket.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

import structlog

logger = structlog.get_logger()


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "ar": "Arabic",
    "ja": "Japanese",
    "zh": "Chinese",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "gu": "Gujarati",
    "mr": "Marathi",
    "pa": "Punjabi",
    "pt": "Portuguese",
    "it": "Italian",
    "ko": "Korean",
    "ru": "Russian",
    "tr": "Turkish",
    "nl": "Dutch",
    "sv": "Swedish",
    "pl": "Polish",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
    "uk": "Ukrainian",
    "ro": "Romanian",
    "el": "Greek",
    "he": "Hebrew",
    "cs": "Czech",
    "hu": "Hungarian",
}


@dataclass
class UserLanguagePref:
    """Per-user language preference for a meeting."""

    user_id: str
    room_id: str
    target_language: str = "en"
    auto_translate: bool = True
    updated_at: float = field(default_factory=time.time)


@dataclass
class TranslationCacheEntry:
    """Cached translation result."""

    source_text: str
    target_language: str
    translated_text: str
    provider: str = "local"
    created_at: float = field(default_factory=time.time)


class TranslationPipeline:
    """Realtime translation pipeline for meetings.

    Manages per-user language preferences, translates transcript entries
    in multiple languages simultaneously, and broadcasts translations
    to participants in their selected language.
    """

    def __init__(self) -> None:
        self._user_prefs: dict[str, UserLanguagePref] = {}
        self._room_users: dict[str, set[str]] = {}
        self._translation_cache: dict[str, TranslationCacheEntry] = {}
        self._room_pending: dict[str, list[dict]] = {}
        self._translate_fn: Callable[[str, str, str], Awaitable[str]] | None = None

    def set_translate_fn(self, fn: Callable[[str, str, str], Awaitable[str]]) -> None:
        """Set the translation function (from AI Server provider)."""
        self._translate_fn = fn

    def set_user_language(
        self, room_id: str, user_id: str, language: str
    ) -> UserLanguagePref:
        """Set a user's preferred language for a meeting."""
        key = f"{room_id}:{user_id}"
        pref = UserLanguagePref(
            user_id=user_id,
            room_id=room_id,
            target_language=language.lower(),
        )
        self._user_prefs[key] = pref

        if room_id not in self._room_users:
            self._room_users[room_id] = set()
        self._room_users[room_id].add(user_id)

        logger.info(
            "user_language_set",
            room_id=room_id,
            user_id=user_id,
            language=language,
        )
        return pref

    def get_user_language(self, room_id: str, user_id: str) -> str:
        """Get a user's preferred language."""
        key = f"{room_id}:{user_id}"
        pref = self._user_prefs.get(key)
        return pref.target_language if pref else "en"

    def get_room_languages(self, room_id: str) -> list[str]:
        """Get all unique target languages needed for a room."""
        users = self._room_users.get(room_id, set())
        languages = set()
        for uid in users:
            key = f"{room_id}:{uid}"
            pref = self._user_prefs.get(key)
            if pref and pref.auto_translate:
                languages.add(pref.target_language)
        languages.add("en")
        return sorted(languages)

    def _cache_key(self, text: str, language: str) -> str:
        """Generate a cache key for a translation."""
        import hashlib

        return hashlib.md5(f"{text}:{language}".encode()).hexdigest()

    async def translate_text(
        self, text: str, source_lang: str = "auto", target_lang: str = "en"
    ) -> str:
        """Translate text using the AI Server translation provider.

        Returns the original text if target language is English.
        Raises RuntimeError if translation fails and no cache hit.
        """
        if target_lang == "en":
            return text

        cache_key = self._cache_key(text, target_lang)
        cached = self._translation_cache.get(cache_key)
        if cached:
            return cached.translated_text

        if self._translate_fn:
            result = await self._translate_fn(text, source_lang, target_lang)
            self._translation_cache[cache_key] = TranslationCacheEntry(
                source_text=text,
                target_language=target_lang,
                translated_text=result,
                provider="ai_server",
            )
            # Evict cache if too large
            if len(self._translation_cache) > 10000:
                keys = list(self._translation_cache.keys())
                for k in keys[:5000]:
                    del self._translation_cache[k]
            return result

        raise RuntimeError(
            "Translation function not configured. AI Server translation provider not connected."
        )

    async def translate_transcript(
        self,
        transcript_id: str,
        text: str,
        room_id: str,
        source_lang: str = "en",
    ) -> dict[str, str]:
        """Translate a transcript entry into all needed languages for a room.

        Returns a dict of {language: translated_text}.
        """
        languages = self.get_room_languages(room_id)
        translations: dict[str, str] = {}

        for lang in languages:
            if lang == source_lang:
                translations[lang] = text
                continue
            translated = await self.translate_text(text, source_lang, lang)
            translations[lang] = translated

        return translations

    def remove_user(self, room_id: str, user_id: str) -> None:
        """Remove a user's language preference for a room."""
        key = f"{room_id}:{user_id}"
        self._user_prefs.pop(key, None)
        users = self._room_users.get(room_id, set())
        users.discard(user_id)
        if not users:
            self._room_users.pop(room_id, None)

    def cleanup_room(self, room_id: str) -> None:
        """Clean up all data for a room."""
        users = self._room_users.pop(room_id, set())
        for uid in users:
            key = f"{room_id}:{uid}"
            self._user_prefs.pop(key, None)
        self._room_pending.pop(room_id, None)

    def get_status(self) -> dict:
        """Get translation pipeline status."""
        total_prefs = len(self._user_prefs)
        total_cached = len(self._translation_cache)
        active_rooms = len(self._room_users)
        return {
            "active_rooms": active_rooms,
            "user_preferences": total_prefs,
            "cached_translations": total_cached,
            "supported_languages": len(LANGUAGE_NAMES),
        }


translation_pipeline = TranslationPipeline()
