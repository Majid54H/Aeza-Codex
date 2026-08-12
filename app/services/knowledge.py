"""Knowledge service — document ingestion and management."""

import uuid
from pathlib import Path
from urllib.parse import urlparse

from app.config import settings
from app.ingestion.excel_analyzer import analyze_excel
from app.ingestion.excel_chunks import build_excel_chunks
from app.ingestion import pipeline
from app.ingestion.loader import load_web_page
from app.rag import faiss
from app.storage.storage import get_storage

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".xlsx", ".xls"}


def _validate_file(filename: str | None, size: int) -> str:
    if not filename:
        raise ValueError("Filename is required")

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    if size > settings.max_upload_bytes:
        raise ValueError(f"File exceeds maximum size of {settings.max_upload_size_mb} MB")

    return suffix


async def ingest_document(content: bytes, filename: str) -> dict:
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


def _validate_url(url: str) -> str:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid http or https URL")
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{host}{path}{query}"


async def _url_already_indexed(url: str) -> bool:
    docs = await list_documents()
    return any(
        (doc.get("url") or "").rstrip("/") == url.rstrip("/")
        or (doc.get("filename") or "").rstrip("/") == url.rstrip("/")
        for doc in docs
        if doc.get("source_type") == "url"
    )


async def ingest_url(url: str) -> dict:
    """Fetch a single page, extract text, and index it in FAISS."""
    normalized = _validate_url(url)
    if await _url_already_indexed(normalized):
        raise ValueError("This URL has already been added")

    text = await load_web_page(normalized)
    document_id = str(uuid.uuid4())
    storage = get_storage()
    await storage.save_document(document_id, "page.txt", text.encode("utf-8"))

    extra = {
        "filename": normalized,
        "source_type": "url",
        "url": normalized,
        "file_type": "url",
    }
    chunks = await pipeline.run_text(
        document_id,
        text,
        filename=normalized,
        extra_metadata=extra,
    )

    return {
        "document_id": document_id,
        "filename": normalized,
        "chunks": len(chunks),
        "status": "indexed" if chunks else "empty",
    }


async def list_documents() -> list[dict]:
    storage = get_storage()
    return await storage.list_documents()


async def delete_document(document_id: str) -> dict:
    """Remove a source from storage and the FAISS index."""
    document_id = (document_id or "").strip()
    if not document_id:
        raise ValueError("Document id is required")

    storage = get_storage()
    docs = await storage.list_documents()
    match = next((d for d in docs if d.get("id") == document_id), None)
    if match is None:
        raise FileNotFoundError("Source not found")

    await storage.delete_document(document_id)
    storage.delete_catalog(document_id)
    storage.delete_products(document_id)
    faiss.remove_document(document_id)
    return {"status": "deleted", "document_id": document_id}


async def reindex_all() -> dict:
    """Rebuild embeddings + FAISS index for every stored document."""
    storage = get_storage()
    docs = await storage.list_documents()

    faiss.rebuild()
    storage.delete_all_catalogs()
    storage.delete_all_products()

    indexed = 0
    for doc in docs:
        document_id = doc["id"]
        filename = doc.get("filename") or ""
        try:
            content = await storage.load_document(document_id)
        except FileNotFoundError:
            continue
        extra = None
        if doc.get("source_type") == "url":
            extra = {
                "filename": doc.get("url") or filename,
                "source_type": "url",
                "url": doc.get("url") or filename,
                "file_type": "url",
            }
            text = content.decode("utf-8", errors="replace")
            await pipeline.run_text(document_id, text, filename=extra["filename"], extra_metadata=extra)
        else:
            await pipeline.run(document_id, content, filename=filename)
        indexed += 1

    return {"status": "reindex_complete", "documents": indexed}


async def rebuild_catalogs_from_documents() -> int:
    """Rebuild catalogs.json and products.json from stored Excel files without re-embedding."""
    storage = get_storage()
    docs = await storage.list_documents()
    rebuilt = 0

    for doc in docs:
        filename = doc.get("filename") or ""
        suffix = Path(filename).suffix.lower()
        if suffix not in {".xlsx", ".xls"}:
            continue

        try:
            content = await storage.load_document(doc["id"])
        except FileNotFoundError:
            continue

        analysis = analyze_excel(content, filename)
        _, catalog, products_payload, _ = build_excel_chunks(doc["id"], filename, analysis)
        if catalog.get("categories") or catalog.get("product_count"):
            storage.save_catalog(doc["id"], catalog)
        if products_payload.get("products"):
            storage.save_products(doc["id"], products_payload)
        if catalog.get("categories") or products_payload.get("products"):
            rebuilt += 1

    return rebuilt
