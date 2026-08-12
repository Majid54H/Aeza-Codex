"""Chat service — orchestrates RAG pipeline for user messages."""

import uuid

from app.rag import faiss, generator


async def handle_message(message: str, session_id: str | None = None) -> dict:
    session_id = session_id or str(uuid.uuid4())

    chunks = faiss.search(message, top_k=5)
    reply = await generator.generate(message, context=chunks)

    sources = [
        {"text": c.get("text", ""), "score": c.get("score", 0.0)}
        for c in chunks
    ]

    return {
        "reply": reply,
        "session_id": session_id,
        "sources": sources,
    }
