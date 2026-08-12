"""Chat service — orchestrates RAG retrieval and LLM generation."""

import uuid

from app.config import settings
from app.rag import embeddings, faiss
from app.rag.generator import NO_CONTEXT_REPLY, generate, generate_stream

_EMBED_ERROR_REPLY = (
    "Chat is temporarily unavailable because embeddings are not configured. "
    "Set OPENAI_API_KEY and try again."
)


async def _retrieve_chunks(message: str) -> list[dict]:
    """Embed the question, search FAISS, and filter by relevance score."""
    query_vectors = await embeddings.embed([message])
    if not query_vectors:
        return []

    hits = faiss.search(query_vectors[0], top_k=settings.rag_top_k)
    return [c for c in hits if c.get("score", 0.0) >= settings.rag_min_score]


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

    try:
        chunks = await _retrieve_chunks(message)
    except RuntimeError as exc:
        if "OPENAI_API_KEY" in str(exc):
            return {
                "reply": _EMBED_ERROR_REPLY,
                "session_id": session_id,
                "sources": [],
            }
        raise
    except Exception:
        return {
            "reply": "Chat is temporarily unavailable. Please try again later.",
            "session_id": session_id,
            "sources": [],
        }

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


async def stream_message(message: str, session_id: str | None = None):
    """Yield SSE-ready dicts: meta, token, done (or error)."""
    session_id = session_id or str(uuid.uuid4())
    yield {"type": "meta", "session_id": session_id}

    try:
        chunks = await _retrieve_chunks(message)
    except RuntimeError as exc:
        if "OPENAI_API_KEY" in str(exc):
            yield {"type": "token", "text": _EMBED_ERROR_REPLY}
            yield {"type": "done"}
            return
        raise
    except Exception:
        yield {"type": "token", "text": "Chat is temporarily unavailable. Please try again later."}
        yield {"type": "done"}
        return

    if not chunks:
        yield {"type": "token", "text": NO_CONTEXT_REPLY}
        yield {"type": "done"}
        return

    async for piece in generate_stream(message, context=chunks):
        yield {"type": "token", "text": piece}
    yield {"type": "done", "sources": _format_sources(chunks)}
