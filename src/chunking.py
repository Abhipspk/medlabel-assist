import re


def _split_sentences(text, max_chars):
    pieces = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if not sent:
            continue
        # A very long run with no punctuation (tables, lists) is cut by length.
        for i in range(0, len(sent), max_chars):
            pieces.append(sent[i : i + max_chars])
    return pieces


def chunk_text(text, max_chars=1000, overlap_sentences=1):
    if not text.strip():
        return []

    sentences = _split_sentences(text, max_chars)
    chunks, current, size = [], [], 0

    for sent in sentences:
        if current and size + len(sent) + 1 > max_chars:
            chunks.append(" ".join(current))
            current = (
                current[-overlap_sentences:] if overlap_sentences else []
            )
            size = sum(len(s) + 1 for s in current)
            # If the retained overlap + new sentence still exceeds max_chars, drop overlap
            if size + len(sent) + 1 > max_chars:
                current, size = [], 0

        current.append(sent)
        size += len(sent) + 1

    if current:
        chunks.append(" ".join(current))

    return chunks