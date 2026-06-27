def chunk_text(text: str, *, max_tokens: int = 350, overlap_tokens: int = 50) -> list[str]:
    """Splits on paragraph boundaries first (keeps semantic units intact where possible),
    then packs paragraphs into chunks up to max_tokens, splitting an individual paragraph
    only if it alone exceeds max_tokens. Overlap repeats the tail of one chunk at the start
    of the next so a sentence split across a chunk boundary still has context on both sides.

    Uses tiktoken's cl100k_base encoding as a length proxy — not exactly OpenAI embedding
    tokenization for every model, but close enough to size chunks sensibly, and a real token
    count (not a word- or character-count guess).
    """
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    def flush():
        if current:
            chunks.append("\n\n".join(current))

    for para in paragraphs:
        para_tokens = len(enc.encode(para))

        if para_tokens > max_tokens:
            # Single paragraph too big on its own — hard-split it by token windows.
            flush()
            current, current_tokens = [], 0
            tokens = enc.encode(para)
            for start in range(0, len(tokens), max_tokens - overlap_tokens):
                window = tokens[start : start + max_tokens]
                chunks.append(enc.decode(window))
            continue

        if current_tokens + para_tokens > max_tokens:
            flush()
            # Carry overlap: keep decoding the tail of the last chunk as the new seed.
            if chunks:
                tail_tokens = enc.encode(chunks[-1])[-overlap_tokens:]
                current = [enc.decode(tail_tokens)] if tail_tokens else []
                current_tokens = len(tail_tokens)
            else:
                current, current_tokens = [], 0

        current.append(para)
        current_tokens += para_tokens

    flush()
    return [c for c in chunks if c.strip()]
