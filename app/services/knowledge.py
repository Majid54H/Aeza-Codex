"""Knowledge service — document ingestion and management."""

import uuid

from fastapi import UploadFile

from app.rag import faiss
from app.ingestion import pipeline
from app.storage.storage import get_storage


async def ingest_document(file: UploadFile) -> dict:
    content = await file.read()
    document_id = str(uuid.uuid4())

    storage = get_storage()
    await storage.save_document(document_id, file.filename or "document", content)

    chunks = await pipeline.run(document_id, content, filename=file.filename or "")

    return {
        "document_id": document_id,
        "chunks": len(chunks),
        "status": "indexed",
    }


async def list_documents() -> list[dict]:
    storage = get_storage()
    return await storage.list_documents()


async def reindex_all() -> dict:
    """Rebuild embeddings + FAISS index for every stored document."""
    storage = get_storage()
    docs = await storage.list_documents()

    # Reindex from scratch so the index doesn't accumulate duplicates.
    faiss.reset()

    for doc in docs:
        document_id = doc["id"]
        filename = doc.get("filename") or ""
        content = await storage.load_document(document_id)
        await pipeline.run(document_id, content, filename=filename)

    return {"status": "reindex_complete", "documents": len(docs)}
