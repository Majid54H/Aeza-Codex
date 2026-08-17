"""Chat API routes."""

import asyncio
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
    ui: dict | None = None


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
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def produce() -> None:
            try:
                async for event in chat_service.stream_message(
                    message=request.message,
                    session_id=request.session_id,
                ):
                    await queue.put(event)
            except Exception:
                await queue.put(
                    {
                        "type": "error",
                        "text": "Chat is temporarily unavailable. Please try again later.",
                    }
                )
            finally:
                await queue.put(None)

        producer = asyncio.create_task(produce())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            if not producer.done():
                producer.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
