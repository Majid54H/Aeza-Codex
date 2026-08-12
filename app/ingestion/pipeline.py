"""Ingestion pipeline — load, chunk, embed, and index documents."""

from pathlib import Path

from app.ingestion.loader import load_text
from app.ingestion.chunker import chunk_with_metadata
from app.rag import embeddings, faiss
from app.storage.storage import get_storage


async def run(document_id: str, content: bytes, filename: str = "") -> list[dict]:
    text = load_text(content, filename)
    chunks = list(chunk_with_metadata(text, document_id))

    if not chunks:
        storage = get_storage()
        await storage.save_metadata(
            document_id,
            {
                "filename": filename,
                "file_type": Path(filename).suffix.lower(),
                "chunks": 0,
                "status": "empty",
            },
        )
        return []

    vectors = await embeddings.embed([c["text"] for c in chunks])
    faiss.add(document_id, chunks, vectors, filename=filename)

    storage = get_storage()
    await storage.save_metadata(
        document_id,
        {
            "filename": filename,
            "file_type": Path(filename).suffix.lower(),
            "chunks": len(chunks),
            "status": "indexed",
        },
    )

    return chunks
