"""Chat service — orchestrates RAG retrieval and LLM generation."""

import uuid

from app.config import settings
from app.rag import embeddings, faiss
from app.rag.generator import NO_CONTEXT_REPLY, generate


async def _retrieve_chunks(message: str) -> list[dict]:
    """Embed the question, search FAISS, and filter by relevance score."""
    query_vectors = await embeddings.embed([message])
    if not query_vectors:
        return []

    hits = faiss.search(query_vectors[0], top_k=settings.rag_top_k)
    min_score = settings.rag_min_score if settings.openai_api_key else 0.0
    return [c for c in hits if c.get("score", 0.0) >= min_score]


def _format_sources(chunks: list[dict]) -> list[dict]:
    return [
        {
            "text": c.get("text", ""),
            "score": c.get("score", 0.0),
            "document_id": c.get("document_id", ""),
            "filename": c.get("filename", ""),
        }
        for c in chunks
    ]


async def handle_message(message: str, session_id: str | None = None) -> dict:
    session_id = session_id or str(uuid.uuid4())

    chunks = await _retrieve_chunks(message)

    if not chunks:
        return {
            "reply": NO_CONTEXT_REPLY,
            "session_id": session_id,
            "sources": [],
        }

    reply = await generate(message, context=chunks)

    return {
        "reply": reply,
        "session_id": session_id,
        "sources": _format_sources(chunks),
    }
