"""Ingestion pipeline — load, chunk, embed, and index documents."""

from pathlib import Path

from app.ingestion.loader import load_text
from app.ingestion.chunker import chunk_with_metadata
from app.rag import embeddings, faiss
from app.storage.storage import get_storage


async def run_text(
    document_id: str,
    text: str,
    filename: str = "",
    extra_metadata: dict | None = None,
) -> list[dict]:
    """Chunk, embed, and index already-extracted text."""
    chunks = list(chunk_with_metadata(text, document_id))
    storage = get_storage()
    metadata = {
        "filename": filename,
        "file_type": Path(filename).suffix.lower() if filename else "",
        "chunks": len(chunks),
        "status": "indexed" if chunks else "empty",
    }
    if extra_metadata:
        metadata.update(extra_metadata)
        metadata["chunks"] = len(chunks)
        metadata["status"] = "indexed" if chunks else "empty"

    if not chunks:
        await storage.save_metadata(document_id, metadata)
        return []

    vectors = await embeddings.embed([c["text"] for c in chunks])
    faiss.add(document_id, chunks, vectors, filename=filename)
    await storage.save_metadata(document_id, metadata)
    return chunks


async def run(document_id: str, content: bytes, filename: str = "") -> list[dict]:
    text = load_text(content, filename)
    return await run_text(document_id, text, filename=filename)
