from app.services.translation.buffer import UtteranceBuffer


def test_consecutive_same_speaker_utterances_merge_within_gap_window():
    buf = UtteranceBuffer(max_gap_ms=1500, max_chars=280)
    assert buf.add("Alice", "I think we should", 1000) is None
    assert buf.add("Alice", "ship on Friday.", 1800) is None  # 800ms gap, within window
    flushed = buf.flush("Alice")
    assert flushed.text == "I think we should ship on Friday."


def test_long_pause_flushes_old_buffer_and_starts_fresh():
    buf = UtteranceBuffer(max_gap_ms=1500, max_chars=280)
    buf.add("Bob", "Let me check on that.", 1000)
    flushed = buf.add("Bob", "Okay, confirmed.", 5000)  # 4000ms gap, past the window
    assert flushed is not None
    assert flushed.text == "Let me check on that."
    remaining = buf.flush("Bob")
    assert remaining.text == "Okay, confirmed."


def test_length_cap_flushes_even_within_gap_window():
    buf = UtteranceBuffer(max_gap_ms=5000, max_chars=20)
    buf.add("Carol", "This is a short phrase", 1000)
    flushed = buf.add("Carol", "and here is more text that pushes well past the limit", 1100)
    assert flushed is not None
    assert flushed.text == "This is a short phrase"


def test_per_speaker_buffers_stay_independent_when_speakers_interleave():
    buf = UtteranceBuffer()
    buf.add("Alice", "Hello", 1000)
    buf.add("Bob", "Hi there", 1050)
    remaining = {u.speaker: u.text for u in buf.flush_all()}
    assert remaining == {"Alice": "Hello", "Bob": "Hi there"}


def test_flush_all_drains_and_clears():
    buf = UtteranceBuffer()
    buf.add("Alice", "test", 1000)
    assert len(buf.flush_all()) == 1
    assert buf.flush_all() == []
