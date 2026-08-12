"""Chat service — orchestrates LLM generation for user messages."""

import uuid

from app.rag.generator import generate


async def handle_message(message: str, session_id: str | None = None) -> dict:
    session_id = session_id or str(uuid.uuid4())

    reply = await generate(message)

    return {
        "reply": reply,
        "session_id": session_id,
        "sources": [],
    }
