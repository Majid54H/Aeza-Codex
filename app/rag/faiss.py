"""FAISS vector index for semantic search.

Persistence goes through app.storage — no direct filesystem paths here.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import faiss  # type: ignore
import numpy as np

from app.storage.storage import get_storage

logger = logging.getLogger(__name__)

# In-memory state (reconstructed from storage on demand)
_index: Any | None = None
_mapping: list[dict[str, Any]] = []
_dim: int | None = None
_loaded_fingerprint: int | None = None
_last_stale_check: float = 0.0
_STALE_CHECK_SECONDS = 20.0


def _normalize(v: np.ndarray) -> np.ndarray:
    """Normalize vectors for cosine similarity via inner product."""
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return v / norms


def _storage():
    return get_storage()


def _persisted_mapping_len() -> int:
    mapping = _storage().load_chunk_mapping()
    return len(mapping) if isinstance(mapping, list) else 0


def _ensure_loaded() -> None:
    """Hydrate RAM from storage when empty or stale (Vercel multi-instance)."""
    global _last_stale_check

    now = time.monotonic()
    if _index is not None and _index.ntotal > 0 and _loaded_fingerprint is not None:
        if now - _last_stale_check < _STALE_CHECK_SECONDS:
            return
        _last_stale_check = now
        if _persisted_mapping_len() == _loaded_fingerprint:
            return
        load()
        return

    if _loaded_fingerprint == 0 and _index is None:
        if now - _last_stale_check < _STALE_CHECK_SECONDS:
            return
        _last_stale_check = now
        if _persisted_mapping_len() == 0:
            return
        load()
        return

    load()
    _last_stale_check = time.monotonic()


def ensure_loaded() -> None:
    """Public wrapper so chat can hydrate the index in parallel with embeddings."""
    _ensure_loaded()


def create_index(dim: int) -> None:
    """Create a new FAISS index with the given embedding dimension."""
    global _index, _dim
    _index = faiss.IndexFlatIP(dim)
    _dim = dim


def reset() -> None:
    """Clear in-memory index, mapping, and persisted index."""
    global _index, _mapping, _dim, _loaded_fingerprint
    _index = None
    _mapping = []
    _dim = None
    _loaded_fingerprint = 0

    storage = _storage()
    storage.delete_faiss_index()
    storage.save_chunk_mapping([])


def add(
    document_id: str,
    chunks: list[dict],
    vectors: list[list[float]],
    filename: str = "",
) -> None:
    """Add chunk vectors to the FAISS index and persist."""
    global _index, _dim, _mapping

    if not chunks or not vectors:
        return

    vecs = np.asarray(vectors, dtype=np.float32)
    if vecs.ndim != 2:
        raise ValueError("Vectors must be a 2D array")

    dim = int(vecs.shape[1])
    _ensure_loaded()
    if _index is None:
        create_index(dim)
    elif _dim != dim:
        raise ValueError(f"Embedding dimension mismatch: expected {_dim}, got {dim}")

    vecs = _normalize(vecs)
    _index.add(vecs)

    for chunk in chunks:
        entry = {
            "document_id": document_id,
            "chunk_index": chunk.get("chunk_index"),
            "text": chunk.get("text", ""),
            "filename": filename,
        }
        if chunk.get("chunk_type"):
            entry["chunk_type"] = chunk["chunk_type"]
        _mapping.append(entry)

    save()


def save() -> None:
    """Persist FAISS index (as bytes) and chunk mapping via storage."""
    global _loaded_fingerprint, _last_stale_check
    if _index is None:
        return

    storage = _storage()
    serialized = faiss.serialize_index(_index)
    storage.save_faiss_index(np.asarray(serialized).tobytes())
    storage.save_chunk_mapping(_mapping)
    _loaded_fingerprint = len(_mapping)
    _last_stale_check = time.monotonic()


def load() -> None:
    """Load FAISS index and chunk mapping from storage. Safe if missing."""
    global _index, _mapping, _dim, _loaded_fingerprint

    storage = _storage()
    mapping = storage.load_chunk_mapping()
    _mapping = mapping if isinstance(mapping, list) else []

    raw = storage.load_faiss_index()
    if not raw:
        _index = None
        _dim = None
        _loaded_fingerprint = len(_mapping)
        if _mapping:
            logger.warning(
                "Chunk mapping has %s entries but FAISS index is missing from storage",
                len(_mapping),
            )
        return

    try:
        arr = np.frombuffer(raw, dtype=np.uint8).copy()
        _index = faiss.deserialize_index(arr)
        _dim = int(_index.d)
    except Exception:
        logger.exception("Failed to deserialize FAISS index (%s bytes)", len(raw))
        _index = None
        _dim = None
        _loaded_fingerprint = len(_mapping)
        return

    if len(_mapping) > _index.ntotal:
        logger.warning(
            "Truncating chunk mapping from %s to %s to match FAISS ntotal",
            len(_mapping),
            _index.ntotal,
        )
        _mapping = _mapping[: _index.ntotal]
    _loaded_fingerprint = len(_mapping)


def search(vector: list[float], top_k: int = 5, *, hydrate: bool = True) -> list[dict]:
    """Search by embedding vector and return matching chunk metadata + scores."""
    if hydrate:
        _ensure_loaded()
    if _index is None or not _mapping or _index.ntotal == 0:
        return []

    q = np.asarray([vector], dtype=np.float32)
    q = _normalize(q)

    k = min(top_k, _index.ntotal)
    scores, ids = _index.search(q, k)

    results: list[dict] = []
    for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
        if idx < 0:
            continue
        if idx >= len(_mapping):
            continue
        results.append({**_mapping[idx], "score": float(score)})

    return results


def remove_document(document_id: str) -> None:
    """Drop all vectors for a document and persist the remaining index."""
    global _index, _mapping, _dim

    _ensure_loaded()
    keep_idx = [i for i, item in enumerate(_mapping) if item.get("document_id") != document_id]
    if len(keep_idx) == len(_mapping):
        return

    if not keep_idx or _index is None:
        reset()
        return

    vectors = np.vstack([_index.reconstruct(i) for i in keep_idx]).astype(np.float32)
    new_mapping = [_mapping[i] for i in keep_idx]
    create_index(int(vectors.shape[1]))
    _index.add(vectors)
    _mapping = new_mapping
    save()


def rebuild() -> None:
    """Clear the index for a full rebuild (used by reindex)."""
    reset()


def stats(*, hydrate: bool = False) -> dict[str, int]:
    """Index size. Set hydrate=True to load from storage first."""
    if hydrate:
        try:
            _ensure_loaded()
        except Exception:
            logger.exception("Could not load FAISS stats from storage")
    return {
        "vectors": int(_index.ntotal) if _index is not None else 0,
        "chunks": len(_mapping),
    }
