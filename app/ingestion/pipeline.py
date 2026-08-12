"""Ingestion pipeline — load, chunk, embed, and index documents."""

from app.ingestion.loader import load_text
from app.ingestion.chunker import chunk_with_metadata
from app.rag import embeddings, faiss
from app.storage.storage import get_storage


async def run(document_id: str, content: bytes, filename: str = "") -> list[dict]:
    text = load_text(content, filename)
    chunks = list(chunk_with_metadata(text, document_id))

    vectors = await embeddings.embed([c["text"] for c in chunks])
    faiss.add(document_id, chunks, vectors)

    storage = get_storage()
    await storage.save_metadata(document_id, {"filename": filename, "chunks": len(chunks)})

    return chunks
