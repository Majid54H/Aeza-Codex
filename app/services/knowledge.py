"""Knowledge service — document ingestion and management."""

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings
from app.ingestion import pipeline
from app.rag import faiss
from app.storage.storage import get_storage

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _validate_file(filename: str | None, size: int) -> str:
    if not filename:
        raise ValueError("Filename is required")

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    if size > settings.max_upload_bytes:
        raise ValueError(f"File exceeds maximum size of {settings.max_upload_size_mb} MB")

    return suffix


async def ingest_document(file: UploadFile) -> dict:
    content = await file.read()
    filename = file.filename or "document"
    _validate_file(filename, len(content))

    document_id = str(uuid.uuid4())
    storage = get_storage()
    await storage.save_document(document_id, filename, content)

    chunks = await pipeline.run(document_id, content, filename=filename)

    return {
        "document_id": document_id,
        "filename": filename,
        "chunks": len(chunks),
        "status": "indexed" if chunks else "empty",
    }


async def list_documents() -> list[dict]:
    storage = get_storage()
    return await storage.list_documents()


async def reindex_all() -> dict:
    """Rebuild embeddings + FAISS index for every stored document."""
    storage = get_storage()
    docs = await storage.list_documents()

    faiss.rebuild()

    for doc in docs:
        document_id = doc["id"]
        filename = doc.get("filename") or ""
        content = await storage.load_document(document_id)
        await pipeline.run(document_id, content, filename=filename)

    return {"status": "reindex_complete", "documents": len(docs)}
