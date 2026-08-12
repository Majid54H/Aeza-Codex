"""Text chunking utilities."""

from typing import Iterator


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end].strip())
        if end == length:
            break
        start = end - overlap

    return [c for c in chunks if c]


def chunk_with_metadata(text: str, document_id: str) -> Iterator[dict]:
    """Yield chunks with document metadata attached."""
    for i, chunk in enumerate(chunk_text(text)):
        yield {
            "document_id": document_id,
            "chunk_index": i,
            "text": chunk,
        }
