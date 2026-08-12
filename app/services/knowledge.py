"""Knowledge service — document ingestion and management."""

import uuid

from fastapi import UploadFile


async def ingest_document(file: UploadFile) -> dict:
    # Consume the upload body without persisting or indexing in Phase 1.
    await file.read()
    document_id = str(uuid.uuid4())

    return {
        "document_id": document_id,
        "chunks": 0,
        "status": "not_implemented_phase_1",
    }


async def list_documents() -> list[dict]:
    # Placeholder until document ingestion + storage indexing are implemented.
    return []


async def reindex_all() -> dict:
    # Placeholder until ingestion + FAISS persistence are implemented.
    return {"status": "not_implemented_phase_1"}
