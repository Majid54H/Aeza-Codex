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


def chunk_records(records: list[str], chunk_size: int = 512) -> list[str]:
    """Group whole row-records into chunks; never split a row."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for raw in records:
        record = (raw or "").strip()
        if not record:
            continue
        extra = len(record) + (1 if current else 0)
        if current and current_len + extra > chunk_size:
            chunks.append("\n".join(current))
            current = [record]
            current_len = len(record)
        else:
            current.append(record)
            current_len += extra

    if current:
        chunks.append("\n".join(current))
    return chunks


def chunk_records_with_metadata(records: list[str], document_id: str) -> Iterator[dict]:
    for i, chunk in enumerate(chunk_records(records)):
        yield {
            "document_id": document_id,
            "chunk_index": i,
            "text": chunk,
        }
