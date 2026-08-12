"""Chat service (Phase 1 stub).

In Phase 1 we only provide the FastAPI foundation.
RAG/FAISS/LLM behavior is intentionally not implemented yet.
"""

import uuid


async def handle_message(message: str, session_id: str | None = None) -> dict:
    # Keep the API contract stable while RAG is not implemented.
    session_id = session_id or str(uuid.uuid4())

    return {
        "reply": "[Phase 1] Chat is not implemented yet. Configure FAISS + LLM in a later phase.",
        "session_id": session_id,
        "sources": [],
    }
