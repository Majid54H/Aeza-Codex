"""Chat service — orchestrates RAG retrieval and LLM generation."""

import uuid

from app.rag import embeddings, faiss
from app.rag.generator import generate


async def handle_message(message: str, session_id: str | None = None) -> dict:
    session_id = session_id or str(uuid.uuid4())

    query_vectors = await embeddings.embed([message])
    chunks: list[dict] = []
    if query_vectors:
        chunks = faiss.search(query_vectors[0], top_k=5)

    reply = await generate(message, context=chunks)

    sources = [
        {
            "text": c.get("text", ""),
            "score": c.get("score", 0.0),
            "document_id": c.get("document_id", ""),
        }
        for c in chunks
    ]

    return {
        "reply": reply,
        "session_id": session_id,
        "sources": sources,
    }
