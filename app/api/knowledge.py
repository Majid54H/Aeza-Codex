"""Knowledge base API routes."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.services import knowledge as knowledge_service

router = APIRouter()


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    chunks: int
    status: str


async def _handle_upload(file: UploadFile) -> UploadResponse:
    try:
        result = await knowledge_service.ingest_document(file)
        return UploadResponse(**result)
    except ValueError as exc:
        message = str(exc)
        if "exceeds maximum size" in message:
            raise HTTPException(status_code=413, detail=message) from exc
        if "Unsupported file type" in message:
            raise HTTPException(status_code=422, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)):
    return await _handle_upload(file)


@router.post("/ingest", response_model=UploadResponse)
async def ingest(file: UploadFile = File(...)):
    """Backward-compatible alias for /upload."""
    return await _handle_upload(file)


class UrlIngestRequest(BaseModel):
    url: str


@router.post("/url", response_model=UploadResponse)
async def ingest_url(payload: UrlIngestRequest):
    try:
        result = await knowledge_service.ingest_url(payload.url)
        return UploadResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/documents")
async def list_documents():
    return await knowledge_service.list_documents()
