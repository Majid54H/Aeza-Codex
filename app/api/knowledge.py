"""Knowledge base API routes."""

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from app.services import knowledge as knowledge_service

router = APIRouter()


class IngestResponse(BaseModel):
    document_id: str
    chunks: int
    status: str


@router.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    result = await knowledge_service.ingest_document(file)
    return IngestResponse(**result)


@router.get("/documents")
async def list_documents():
    return await knowledge_service.list_documents()
