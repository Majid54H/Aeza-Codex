"""Structured product card / compare UI payloads for chat."""

from __future__ import annotations

import re
from typing import Any

from app.storage.storage import get_storage

LIST_LIMIT = 6
COMPARE_LIMIT = 2

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

_COMPARE_PATTERNS = (
    r"\bcompare\b",
    r"\bvs\.?\b",
    r"\bversus\b",
    r"\bdifference\b",
    r"\bwhich (?:is|one is) better\b",
    r"\bside by side\b",
)

_LIST_PATTERNS = (
    r"\bshow\b",
    r"\bfind\b",
    r"\blist\b",
    r"\boptions?\b",
    r"\bavailable\b",
    r"\brecommend\b",
    r"\bsuggest\b",
    r"\bhave\b",
    r"\bdo you have\b",
    r"\blooking for\b",
    r"\bwant\b",
    r"\bneed\b",
    r"\bproducts?\b",
    r"\bitems?\b",
)

# Leave taxonomy/count questions to chat.py deterministic replies
_TAXONOMY_SKIP_PATTERNS = (
    r"\ball categories\b",
    r"\ball .{0,24} categor",
    r"\blist categories\b",
    r"\bwhat categories\b",
    r"\bwhich categories\b",
    r"\bavailable categories\b",
    r"\bcategories (?:which are |that are )?available\b",
    r"\bcategor.{0,20} available\b",
    r"\bgive (?:me )?(?:all )?categories\b",
    r"\bproduct categories\b",
    r"\bproducts categories\b",
    r"\bhow many products\b",
    r"\bnumber of products\b",
    r"\btotal products\b",
    r"\bhow many categories\b",
    r"\bsubcategories?\b",
    r"\bcatalog overview\b",
)

_STOPWORDS = {
    "a",
    "an",
    "the",
    "me",
    "my",
    "please",
    "show",
    "find",
    "list",
    "give",
    "all",
    "some",
    "any",
    "available",
    "options",
    "option",
    "products",
    "product",
    "items",
    "item",
    "do",
    "you",
    "have",
    "want",
    "need",
    "looking",
    "for",
    "under",
    "in",
    "of",
    "and",
    "or",
    "with",
    "from",
    "catalog",
    "compare",
    "versus",
    "vs",
    "which",
    "is",
    "better",
    "difference",
    "between",
    "two",
    "these",
    "those",
    "what",
    "are",
    "there",
}


def _normalize_query(message: str) -> str:
    text = (message or "").strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for wrong, right in _TYPO_REPLACEMENTS:
        text = text.replace(wrong, right)
    return text


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t and t not in _STOPWORDS}


def _parse_price(value: str) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value.replace(",", ""))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_compare_query(message: str) -> bool:
    text = _normalize_query(message)
    return any(re.search(p, text) for p in _COMPARE_PATTERNS)


def _is_taxonomy_skip(message: str) -> bool:
    text = _normalize_query(message)
    return any(re.search(p, text) for p in _TAXONOMY_SKIP_PATTERNS)


def _is_product_list_query(message: str) -> bool:
    text = _normalize_query(message)
    if any(re.search(p, text) for p in _LIST_PATTERNS):
        return True
    tokens = _tokens(text)
    return 1 <= len(tokens) <= 5


def _score_product(query: str, product: dict) -> float:
    q = query.lower()
    q_tokens = _tokens(q)
    if not q_tokens and not q.strip():
        return 0.0

    score = 0.0
    name = (product.get("name") or "").lower()
    category = (product.get("category") or "").lower()
    subcategory = (product.get("subcategory") or "").lower()
    brand = (product.get("brand") or "").lower()
    color = (product.get("color") or "").lower()

    if subcategory and subcategory in q:
        score += 12.0
    if category and category in q:
        score += 8.0
    if brand and brand in q:
        score += 6.0
    if name and name in q:
        score += 15.0

    fields = (
        (name, 3.0),
        (subcategory, 4.0),
        (category, 2.5),
        (brand, 2.0),
        (color, 1.5),
    )
    for field_text, weight in fields:
        if not field_text:
            continue
        field_tokens = _tokens(field_text)
        overlap = q_tokens & field_tokens
        score += len(overlap) * weight
        for token in q_tokens:
            if len(token) >= 3 and token in field_text:
                score += weight * 0.5

    return score


def _mark_best_value(products: list[dict]) -> list[dict]:
    priced: list[tuple[int, float]] = []
    for i, product in enumerate(products):
        amount = _parse_price(product.get("price") or "")
        if amount is not None:
            priced.append((i, amount))
    if len(priced) < 2:
        return products
    best_idx = min(priced, key=lambda item: item[1])[0]
    for i, product in enumerate(products):
        product["best_value"] = i == best_idx
    return products


def _card_product(product: dict) -> dict:
    return {
        "id": product.get("id") or "",
        "name": product.get("name") or "",
        "category": product.get("category") or "",
        "subcategory": product.get("subcategory") or "",
        "brand": product.get("brand") or "",
        "price": product.get("price") or "",
        "color": product.get("color") or "",
        "size": product.get("size") or "",
        "stock": product.get("stock") or "",
        "discount": product.get("discount") or "",
        "best_value": bool(product.get("best_value")),
        "attributes": product.get("attributes") or {},
    }


def _compare_features(products: list[dict]) -> list[dict]:
    rows_spec = (
        ("Color", "color"),
        ("Size", "size"),
        ("Price", "price"),
        ("Discount", "discount"),
        ("Stock", "stock"),
    )
    features: list[dict] = []
    for label, key in rows_spec:
        values = [str(p.get(key) or "") for p in products]
        if any(values):
            features.append({"label": label, "values": values})
    return features


def _focus_label(query: str, products: list[dict]) -> str:
    subs = {p.get("subcategory") or "" for p in products if p.get("subcategory")}
    cats = {p.get("category") or "" for p in products if p.get("category")}
    if len(subs) == 1:
        return next(iter(subs))
    if len(cats) == 1:
        return next(iter(cats))
    tokens = sorted(_tokens(query))
    if tokens:
        return " ".join(tokens[:3]).title()
    return "product"


def match_products(message: str, limit: int) -> list[dict]:
    products = get_storage().load_all_products()
    if not products:
        return []

    text = _normalize_query(message)
    scored: list[tuple[float, dict]] = []
    for product in products:
        score = _score_product(text, product)
        if score > 0:
            scored.append((score, product))

    if not scored:
        return []

    scored.sort(key=lambda item: (-item[0], (item[1].get("name") or "").lower()))
    top_score = scored[0][0]
    if top_score < 2.5:
        return []

    # If the query names a subcategory, keep products in that subcategory when possible
    matched_subs = {
        (p.get("subcategory") or "").lower()
        for _, p in scored
        if (p.get("subcategory") or "") and (p.get("subcategory") or "").lower() in text
    }
    if matched_subs:
        filtered = [(s, p) for s, p in scored if (p.get("subcategory") or "").lower() in matched_subs]
        if filtered:
            scored = filtered

    return [item[1] for item in scored[:limit]]


def try_product_ui_reply(message: str) -> dict[str, Any] | None:
    """Return {reply, ui} for product list/compare, or None to fall through."""
    if _is_taxonomy_skip(message):
        return None

    compare = _is_compare_query(message)
    list_intent = _is_product_list_query(message)
    if not compare and not list_intent:
        return None

    matched = match_products(message, limit=LIST_LIMIT if not compare else max(LIST_LIMIT, COMPARE_LIMIT))
    if not matched:
        return None

    text = _normalize_query(message)
    if not compare and not any(re.search(p, text) for p in _LIST_PATTERNS):
        top = matched[0]
        sub = (top.get("subcategory") or "").lower()
        cat = (top.get("category") or "").lower()
        name = (top.get("name") or "").lower()
        if not ((sub and sub in text) or (cat and cat in text) or (name and name in text)):
            if _score_product(text, top) < 6.0:
                return None

    if compare:
        products = _mark_best_value([_card_product(p) for p in matched[:COMPARE_LIMIT]])
        if len(products) < 2:
            products = _mark_best_value([_card_product(p) for p in matched[:LIST_LIMIT]])
            focus = _focus_label(message, products)
            return {
                "reply": f"Here are {focus} options from the catalog.",
                "ui": {
                    "layout": "product_cards",
                    "products": products,
                    "tip": "Not sure? Tell me your preferred color or size and I'll help you choose.",
                },
            }
        focus = _focus_label(message, products)
        return {
            "reply": f"Here are two {focus} options. Compare the details below.",
            "ui": {
                "layout": "product_compare",
                "products": products,
                "features": _compare_features(products),
                "tip": "Not sure? Tell me your preferred color or size and I'll help you choose the best one!",
            },
        }

    products = _mark_best_value([_card_product(p) for p in matched[:LIST_LIMIT]])
    focus = _focus_label(message, products)
    return {
        "reply": f"Here are {focus} options from the catalog.",
        "ui": {
            "layout": "product_cards",
            "products": products,
            "tip": "Want a closer look? Ask me to compare any two products.",
        },
    }
