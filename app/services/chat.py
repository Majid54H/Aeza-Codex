"""Chat service — orchestrates RAG retrieval and LLM generation."""

import re
import uuid

from app.config import settings
from app.rag import embeddings, faiss
from app.rag.generator import NO_CONTEXT_REPLY, generate, generate_stream
from app.storage.storage import get_storage

_EMBED_ERROR_REPLY = (
    "Chat is temporarily unavailable because embeddings are not configured. "
    "Set OPENAI_API_KEY and try again."
)

_CATALOG_PATTERNS = (
    r"\ball categories\b",
    r"\blist categories\b",
    r"\bwhat categories\b",
    r"\bwhich categories\b",
    r"\bavailable categories\b",
    r"\bcategories (?:which are |that are )?available\b",
    r"\bgive (?:me )?(?:all )?categories\b",
    r"\bcategories do you\b",
    r"\bcategories (?:are|do)\b",
    r"\bsubcategories?\b",
    r"\bcatalog overview\b",
    r"\bproduct categories\b",
    r"\btypes of products\b",
    r"\bwhat (?:do you|products do you) (?:sell|carry|offer|have)\b",
)

_FULL_CATEGORY_LIST_PATTERNS = (
    r"\ball categories\b",
    r"\blist categories\b",
    r"\bwhat categories\b",
    r"\bwhich categories\b",
    r"\bavailable categories\b",
    r"\bcategories (?:which are |that are )?available\b",
    r"\bgive (?:me )?(?:all )?categories\b",
    r"\bproduct categories\b",
    r"\btypes of products\b",
    r"\bcatalog overview\b",
    r"\bwhat (?:do you|products do you) (?:sell|carry|offer|have)\b",
)

_SUBCATEGORY_PATTERNS = (
    r"\bsubcategories?\b",
    r"\btypes under\b",
    r"\btypes in\b",
    r"\btypes of .+ in\b",
)


def is_catalog_query(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    return any(re.search(pattern, text) for pattern in _CATALOG_PATTERNS)


def _is_full_category_list_query(message: str) -> bool:
    text = (message or "").strip().lower()
    return any(re.search(pattern, text) for pattern in _FULL_CATEGORY_LIST_PATTERNS)


def _is_subcategory_query(message: str) -> bool:
    text = (message or "").strip().lower()
    return any(re.search(pattern, text) for pattern in _SUBCATEGORY_PATTERNS)


def _find_category_in_query(message: str, catalog: dict) -> str | None:
    text = (message or "").lower()
    matches: list[tuple[str, int]] = []
    for cat in catalog.get("categories") or []:
        name = (cat.get("name") or "").strip()
        if not name:
            continue
        idx = text.find(name.lower())
        if idx >= 0:
            matches.append((name, idx))
    if not matches:
        return None
    matches.sort(key=lambda item: item[1])
    return matches[0][0]


def format_all_categories_reply(catalog: dict) -> str | None:
    names = sorted(
        (c.get("name") or "").strip()
        for c in catalog.get("categories") or []
        if (c.get("name") or "").strip()
    )
    if not names:
        return None
    return "Available categories: " + ", ".join(names) + "."


def format_subcategories_reply(catalog: dict, category: str) -> str | None:
    for cat in catalog.get("categories") or []:
        if (cat.get("name") or "").lower() == category.lower():
            subs = [s for s in (cat.get("subcategories") or []) if s]
            if not subs:
                return f"I don't have subcategory details for {category} in the catalog."
            return f"Subcategories under {category}: " + ", ".join(subs) + "."
    return None


def try_catalog_direct_reply(message: str) -> str | None:
    """Return a complete deterministic catalog answer when taxonomy JSON is available."""
    merged = get_storage().load_merged_catalog()
    if not merged:
        return None

    if _is_subcategory_query(message):
        category = _find_category_in_query(message, merged)
        if category:
            return format_subcategories_reply(merged, category)

    if _is_full_category_list_query(message):
        return format_all_categories_reply(merged)

    if is_catalog_query(message):
        return format_all_categories_reply(merged)

    return None


def build_catalog_context(catalog: dict) -> str:
    lines = ["Catalog data (complete taxonomy from uploaded spreadsheets):", ""]
    for cat in catalog.get("categories") or []:
        name = cat.get("name") or ""
        subs = cat.get("subcategories") or []
        count = cat.get("product_count", 0)
        lines.append(f"Category: {name} ({count} products)")
        if subs:
            lines.append("  Subcategories: " + ", ".join(subs))
        lines.append("")
    total = catalog.get("product_count", 0)
    lines.append(f"Total products across catalogs: {total}")
    return "\n".join(lines).strip()


def _catalog_context_chunk(catalog: dict) -> dict:
    return {
        "text": build_catalog_context(catalog),
        "chunk_type": "catalog_exact",
        "score": 1.0,
        "document_id": "",
        "filename": "catalogs.json",
    }


async def _retrieve_chunks(message: str) -> list[dict]:
    """Embed the question, search FAISS, and filter by relevance score."""
    catalog_intent = is_catalog_query(message)
    top_k = settings.rag_catalog_top_k if catalog_intent else settings.rag_top_k

    query_vectors = await embeddings.embed([message])
    if not query_vectors:
        return []

    hits = faiss.search(query_vectors[0], top_k=top_k)
    chunks = [c for c in hits if c.get("score", 0.0) >= settings.rag_min_score]

    if catalog_intent:
        merged = get_storage().load_merged_catalog()
        if merged:
            chunks = [_catalog_context_chunk(merged), *chunks]

    return chunks


def _format_sources(chunks: list[dict]) -> list[dict]:
    return [
        {
            "text": c.get("text", ""),
            "score": c.get("score", 0.0),
            "document_id": c.get("document_id", ""),
            "filename": c.get("filename", ""),
        }
        for c in chunks
        if c.get("chunk_type") != "catalog_exact"
    ]


async def handle_message(message: str, session_id: str | None = None) -> dict:
    session_id = session_id or str(uuid.uuid4())

    direct = try_catalog_direct_reply(message)
    if direct:
        return {
            "reply": direct,
            "session_id": session_id,
            "sources": [],
        }

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

    direct = try_catalog_direct_reply(message)
    if direct:
        yield {"type": "token", "text": direct}
        yield {"type": "done", "sources": []}
        return

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
