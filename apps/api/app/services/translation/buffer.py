"""Decides WHEN a finalized transcript utterance is ready to send to a translation provider.

This is the part of "real-time translation" that's genuinely just an algorithm — no GPU, no
streaming MT model, no provider account needed to build or test it. Two competing failure modes
it's balancing:
  - Translate every single short utterance the instant it arrives: lowest possible latency per
    utterance, but pays a full translation call's overhead on every short fragment, and loses
    cross-sentence context ("yes." translated alone vs. "yes." following "should we ship Friday?").
  - Wait and batch a lot of speech together: better context and fewer calls, but participants
    watching subtitles wait noticeably longer for each batch — the opposite of "real-time."

Strategy: merge consecutive same-speaker utterances into one pending buffer as long as the gap
between them is short (still the same train of thought) and the merged text hasn't grown past a
length cap (don't let one speaker's monologue silently turn into one giant delayed translation).
A long gap (the speaker paused, or someone else started talking) or hitting the length cap flushes
the buffer — that's the unit that actually gets sent to a translation provider.
"""

from dataclasses import dataclass


@dataclass
class BufferedUtterance:
    speaker: str
    text: str
    start_timestamp_ms: int
    end_timestamp_ms: int


class UtteranceBuffer:
    def __init__(self, *, max_gap_ms: int = 1500, max_chars: int = 280) -> None:
        self._max_gap_ms = max_gap_ms
        self._max_chars = max_chars
        self._pending: dict[str, BufferedUtterance] = {}

    def add(self, speaker: str, text: str, timestamp_ms: int) -> BufferedUtterance | None:
        """Returns a flushed BufferedUtterance if this new piece didn't merge with what was
        pending for this speaker (caller should translate it now); returns None if it merged
        into the still-open buffer (caller should wait for the next flush)."""
        pending = self._pending.get(speaker)
        if pending is None:
            self._pending[speaker] = BufferedUtterance(speaker, text, timestamp_ms, timestamp_ms)
            return None

        gap = timestamp_ms - pending.end_timestamp_ms
        merged_text = f"{pending.text} {text}".strip()
        if gap <= self._max_gap_ms and len(merged_text) <= self._max_chars:
            pending.text = merged_text
            pending.end_timestamp_ms = timestamp_ms
            return None

        ready = pending
        self._pending[speaker] = BufferedUtterance(speaker, text, timestamp_ms, timestamp_ms)
        return ready

    def flush(self, speaker: str) -> BufferedUtterance | None:
        """Force-flush one speaker's pending buffer — call on speaker change detection or
        when a meeting/session ends, so the last few words don't get silently dropped."""
        return self._pending.pop(speaker, None)

    def flush_all(self) -> list[BufferedUtterance]:
        items = list(self._pending.values())
        self._pending.clear()
        return items
