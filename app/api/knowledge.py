"""Knowledge base API routes."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.deps import require_admin
from app.services import knowledge as knowledge_service

router = APIRouter()


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    chunks: int
    status: str


async def _handle_upload(file: UploadFile) -> UploadResponse:
    content = await file.read()
    filename = file.filename or "document"
    try:
        result = await knowledge_service.ingest_document(content, filename)
        return UploadResponse(**result)
    except ValueError as exc:
        message = str(exc)
        if "exceeds maximum size" in message:
            raise HTTPException(status_code=413, detail=message) from exc
        if "Unsupported file type" in message:
            raise HTTPException(status_code=422, detail=message) from exc
        if "OPENAI_API_KEY" in message:
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    except RuntimeError as exc:
        message = str(exc)
        if "OPENAI_API_KEY" in message:
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(status_code=500, detail="Ingestion failed") from exc


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...), _: str = Depends(require_admin)):
    return await _handle_upload(file)


@router.post("/ingest", response_model=UploadResponse)
async def ingest(file: UploadFile = File(...), _: str = Depends(require_admin)):
    """Backward-compatible alias for /upload."""
    return await _handle_upload(file)


class UrlIngestRequest(BaseModel):
    url: str


@router.post("/url", response_model=UploadResponse)
async def ingest_url(payload: UrlIngestRequest, _: str = Depends(require_admin)):
    try:
        result = await knowledge_service.ingest_url(payload.url)
        return UploadResponse(**result)
    except ValueError as exc:
        message = str(exc)
        if "already been added" in message or "valid http" in message or "not allowed" in message:
            raise HTTPException(status_code=422, detail=message) from exc
        if "Timed out" in message:
            raise HTTPException(status_code=504, detail=message) from exc
        if "OPENAI_API_KEY" in message:
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    except RuntimeError as exc:
        message = str(exc)
        if "OPENAI_API_KEY" in message:
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(status_code=500, detail="Ingestion failed") from exc


@router.get("/documents")
async def list_documents():
    return await knowledge_service.list_documents()


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, _: str = Depends(require_admin)):
    try:
        return await knowledge_service.delete_document(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
