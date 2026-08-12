"""Chat service — orchestrates RAG retrieval and LLM generation."""

import re
import uuid

from app.config import settings
from app.rag import embeddings, faiss
from app.rag.generator import NO_CONTEXT_REPLY, generate, generate_stream
from app.services.product_ui import try_product_ui_reply
from app.storage.storage import get_storage

_EMBED_ERROR_REPLY = (
    "Chat is temporarily unavailable because embeddings are not configured. "
    "Set OPENAI_API_KEY and try again."
)

_CATALOG_PATTERNS = (
    r"\ball categories\b",
    r"\ball .{0,24} categor",
    r"\blist categories\b",
    r"\blist .{0,24} categor",
    r"\bwhat categories\b",
    r"\bwhich categories\b",
    r"\bavailable categories\b",
    r"\bcategories (?:which are |that are )?available\b",
    r"\bcategor.{0,20} available\b",
    r"\bgive (?:me )?(?:all )?categories\b",
    r"\bgive (?:me )?(?:all )?.{0,24} categor",
    r"\bcategories do you\b",
    r"\bcategories (?:are|do)\b",
    r"\bsubcategories?\b",
    r"\bcatalog overview\b",
    r"\bproduct categories\b",
    r"\bproducts categories\b",
    r"\btypes of products\b",
    r"\bwhat (?:do you|products do you) (?:sell|carry|offer|have)\b",
)

_FULL_CATEGORY_LIST_PATTERNS = (
    r"\ball categories\b",
    r"\ball .{0,24} categor",
    r"\blist categories\b",
    r"\blist .{0,24} categor",
    r"\bwhat categories\b",
    r"\bwhich categories\b",
    r"\bavailable categories\b",
    r"\bcategories (?:which are |that are )?available\b",
    r"\bcategor.{0,20} available\b",
    r"\bgive (?:me )?(?:all )?categories\b",
    r"\bgive (?:me )?(?:all )?.{0,24} categor",
    r"\bproduct categories\b",
    r"\bproducts categories\b",
    r"\btypes of products\b",
    r"\bcatalog overview\b",
    r"\bwhat (?:do you|products do you) (?:sell|carry|offer|have)\b",
    r"\bshow (?:me )?(?:all )?.{0,24} categor",
    r"\btell (?:me )?(?:all )?.{0,24} categor",
)

_PRODUCT_COUNT_PATTERNS = (
    r"\bhow many products\b",
    r"\bnumber of products\b",
    r"\btotal products\b",
    r"\bproducts (?:are there|do you have|in total|in the catalog)\b",
    r"\bcount (?:of )?products\b",
    r"\bhow many items\b",
)

_CATEGORY_COUNT_PATTERNS = (
    r"\bhow many categories\b",
    r"\bnumber of categories\b",
    r"\btotal categories\b",
    r"\bcount (?:of )?categories\b",
)

_SUBCATEGORY_PATTERNS = (
    r"\bsubcategories?\b",
    r"\btypes under\b",
    r"\btypes in\b",
    r"\btypes of .+ in\b",
)

_TYPO_REPLACEMENTS = (
    ("gvie", "give"),
    ("gvei", "give"),
    ("categries", "categories"),
    ("categoreis", "categories"),
    ("categoy", "category"),
    ("availble", "available"),
    ("avaialble", "available"),
    ("avai lable", "available"),
)


def _normalize_query(message: str) -> str:
    text = (message or "").strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for wrong, right in _TYPO_REPLACEMENTS:
        text = text.replace(wrong, right)
    return text


def is_catalog_query(message: str) -> bool:
    text = _normalize_query(message)
    if not text:
        return False
    if any(re.search(pattern, text) for pattern in _CATALOG_PATTERNS):
        return True
    return _looks_like_category_list_query(text)


def _looks_like_category_list_query(text: str) -> bool:
    has_category = bool(re.search(r"\bcategor", text))
    has_list_intent = bool(re.search(r"\b(all|available|list|what|which|give|show|tell)\b", text))
    has_catalog_context = bool(re.search(r"\b(product|products|catalog|inventory|items)\b", text))
    return has_category and has_list_intent and (has_catalog_context or "available" in text)


def _is_full_category_list_query(message: str) -> bool:
    text = _normalize_query(message)
    if any(re.search(pattern, text) for pattern in _FULL_CATEGORY_LIST_PATTERNS):
        return True
    return _looks_like_category_list_query(text)


def _is_subcategory_query(message: str) -> bool:
    text = _normalize_query(message)
    return any(re.search(pattern, text) for pattern in _SUBCATEGORY_PATTERNS)


def _is_product_count_query(message: str) -> bool:
    text = _normalize_query(message)
    if any(re.search(pattern, text) for pattern in _PRODUCT_COUNT_PATTERNS):
        return True
    return bool(re.search(r"\bhow many\b", text) and re.search(r"\bproducts?\b", text))


def _is_category_count_query(message: str) -> bool:
    text = _normalize_query(message)
    return any(re.search(pattern, text) for pattern in _CATEGORY_COUNT_PATTERNS)


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


def format_product_count_reply(catalog: dict) -> str | None:
    categories = catalog.get("categories") or []
    total = int(catalog.get("product_count") or 0)
    if total <= 0 and not categories:
        return None

    if total <= 0:
        total = sum(int(c.get("product_count") or 0) for c in categories)

    lines = [f"There are {total} products in the catalog."]
    for cat in sorted(categories, key=lambda c: (c.get("name") or "").lower()):
        name = (cat.get("name") or "").strip()
        if not name:
            continue
        count = int(cat.get("product_count") or 0)
        lines.append(f"- {name}: {count} products")
    return "\n".join(lines)


def format_category_count_reply(catalog: dict) -> str | None:
    names = sorted(
        (c.get("name") or "").strip()
        for c in catalog.get("categories") or []
        if (c.get("name") or "").strip()
    )
    if not names:
        return None
    return f"There are {len(names)} categories: " + ", ".join(names) + "."


def try_catalog_direct_reply(message: str) -> str | None:
    """Return a complete deterministic catalog answer when taxonomy JSON is available."""
    merged = get_storage().load_merged_catalog()
    if not merged:
        return None

    if _is_subcategory_query(message):
        category = _find_category_in_query(message, merged)
        if category:
            return format_subcategories_reply(merged, category)

    if _is_product_count_query(message):
        return format_product_count_reply(merged)

    if _is_category_count_query(message):
        return format_category_count_reply(merged)

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
            "ui": None,
        }

    product_ui = try_product_ui_reply(message)
    if product_ui:
        return {
            "reply": product_ui["reply"],
            "session_id": session_id,
            "sources": [],
            "ui": product_ui.get("ui"),
        }

    try:
        chunks = await _retrieve_chunks(message)
    except RuntimeError as exc:
        if "OPENAI_API_KEY" in str(exc):
            return {
                "reply": _EMBED_ERROR_REPLY,
                "session_id": session_id,
                "sources": [],
                "ui": None,
            }
        raise
    except Exception:
        return {
            "reply": "Chat is temporarily unavailable. Please try again later.",
            "session_id": session_id,
            "sources": [],
            "ui": None,
        }

    if not chunks:
        return {
            "reply": NO_CONTEXT_REPLY,
            "session_id": session_id,
            "sources": [],
            "ui": None,
        }

    reply = await generate(message, context=chunks)

    return {
        "reply": reply,
        "session_id": session_id,
        "sources": _format_sources(chunks),
        "ui": None,
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

    product_ui = try_product_ui_reply(message)
    if product_ui:
        yield {"type": "token", "text": product_ui["reply"]}
        yield {"type": "done", "sources": [], "ui": product_ui.get("ui")}
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
