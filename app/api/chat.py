"""Chat API routes."""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
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


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await chat_service.handle_message(
        message=request.message,
        session_id=request.session_id,
    )
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    async def events():
        try:
            async for event in chat_service.stream_message(
                message=request.message,
                session_id=request.session_id,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'text': 'Chat is temporarily unavailable. Please try again later.'})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
