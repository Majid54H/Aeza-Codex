"""FAISS vector index for semantic search."""

from pathlib import Path

from app.config import settings

_index_path = settings.data_dir / "indexes" / "faiss.index"
_chunks: list[dict] = []


def add(document_id: str, chunks: list[dict], vectors: list[list[float]]) -> None:
    """Add chunk vectors to the in-memory index."""
    for chunk, vector in zip(chunks, vectors):
        _chunks.append({**chunk, "vector": vector, "document_id": document_id})
    _persist()


def search(query: str, top_k: int = 5) -> list[dict]:
    """Search for similar chunks (placeholder cosine similarity)."""
    if not _chunks:
        return []

    # In production, embed query and compare against stored vectors
    return _chunks[:top_k]


def _persist() -> None:
    """Persist index metadata to disk (local dev only)."""
    if settings.environment != "development":
        return
    _index_path.parent.mkdir(parents=True, exist_ok=True)
    # FAISS binary index persistence would go here


def load() -> None:
    """Load index from disk on startup."""
    if _index_path.exists():
        pass  # Load FAISS index from file
