import re


def chunk_text(text: str, target_words: int = 180, overlap_words: int = 30):
    """Splits text into overlapping word-window chunks, trying to break on
    paragraph/heading boundaries first so chunks stay semantically coherent
    (this matters a lot for retrieval quality in a RAG pipeline)."""
    text = text.replace("\r\n", "\n")
    paragraphs = [p.strip() for p in re.split(r"\n{1,2}", text) if p.strip()]

    chunks = []
    buffer = []
    buffer_words = 0
    for para in paragraphs:
        words = para.split()
        if buffer_words + len(words) > target_words and buffer:
            chunks.append(" ".join(buffer))
            # keep overlap for context continuity across chunk boundaries
            overlap = " ".join(buffer).split()[-overlap_words:]
            buffer = overlap[:]
            buffer_words = len(overlap)
        buffer.extend(words)
        buffer_words += len(words)
        if buffer_words >= target_words:
            chunks.append(" ".join(buffer))
            overlap = buffer[-overlap_words:]
            buffer = overlap[:]
            buffer_words = len(overlap)

    if buffer:
        chunks.append(" ".join(buffer))

    return [c for c in chunks if len(c.split()) > 5]
