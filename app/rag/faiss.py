"""FAISS vector index for semantic search (local filesystem only)."""

from __future__ import annotations

import json
from typing import Any

import faiss  # type: ignore
import numpy as np

from app.config import settings
from app.rag import embeddings

_index_path = settings.data_dir / "indexes" / "faiss.index"
_mapping_path = settings.data_dir / "indexes" / "faiss_mapping.json"

# In-memory state (reconstructed from disk on startup)
_index: Any | None = None
_mapping: list[dict[str, Any]] = []
_dim: int | None = None


def _normalize(v: np.ndarray) -> np.ndarray:
    """Normalize vectors for cosine similarity via inner product."""
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return v / norms


def reset() -> None:
    """Reset index + mapping (and remove persisted files)."""
    global _index, _mapping, _dim
    _index = None
    _mapping = []
    _dim = None

    if settings.environment == "development":
        for p in (_index_path, _mapping_path):
            try:
                p.unlink()
            except FileNotFoundError:
                pass


def add(document_id: str, chunks: list[dict], vectors: list[list[float]]) -> None:
    """Add chunk vectors to the FAISS index and persist to disk."""
    global _index, _dim, _mapping

    if not chunks or not vectors:
        return

    vecs = np.asarray(vectors, dtype=np.float32)
    if vecs.ndim != 2:
        raise ValueError("Vectors must be a 2D array")

    dim = int(vecs.shape[1])
    _dim = dim

    vecs = _normalize(vecs)

    if _index is None:
        _index = faiss.IndexFlatIP(dim)

    # Add vectors first; then store metadata in the same order.
    _index.add(vecs)

    for chunk in chunks:
        # Store only metadata needed by chat UI/generator.
        _mapping.append(
            {
                "document_id": document_id,
                "chunk_index": chunk.get("chunk_index"),
                "text": chunk.get("text", ""),
            }
        )

    _persist()


async def search(query: str, top_k: int = 5) -> list[dict]:
    """Semantic search: embed query, run FAISS similarity, return top chunks."""
    if _index is None or not _mapping:
        return []

    vecs = await embeddings.embed([query])
    if not vecs:
        return []

    q = np.asarray(vecs, dtype=np.float32)
    q = _normalize(q)

    scores, ids = _index.search(q, top_k)
    # ids shape: (1, top_k)
    results: list[dict] = []
    for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
        if idx < 0:
            continue
        meta = _mapping[idx] if idx < len(_mapping) else None
        if not meta:
            continue
        results.append({**meta, "score": float(score)})

    return results


def _persist() -> None:
    """Persist FAISS index + metadata mapping to disk (local dev only)."""
    if settings.environment != "development":
        return
    if _index is None:
        return

    _index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(_index, str(_index_path))
    with _mapping_path.open("w", encoding="utf-8") as f:
        json.dump(_mapping, f, ensure_ascii=False, indent=2)


def load() -> None:
    """Load FAISS index + mapping from disk on startup."""
    global _index, _mapping, _dim

    if not _index_path.exists() or not _mapping_path.exists():
        return

    _index = faiss.read_index(str(_index_path))
    _dim = int(_index.d)

    with _mapping_path.open("r", encoding="utf-8") as f:
        _mapping = json.load(f) or []

    # If the mapping and index diverged, prefer the index and clamp the mapping.
    if len(_mapping) > _index.ntotal:
        _mapping = _mapping[: _index.ntotal]
