"""Chat API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import chat as chat_service

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    sources: list[dict] = []


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await chat_service.handle_message(
        message=request.message,
        session_id=request.session_id,
    )
    return ChatResponse(**result)
