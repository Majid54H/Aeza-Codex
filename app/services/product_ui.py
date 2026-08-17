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
    ("proce", "price"),
    ("prce", "price"),
    ("priec", "price"),
    ("pric", "price"),
    ("prise", "price"),
    ("prize", "price"),
    ("cheep", "cheap"),
    ("colours", "colors"),
    ("colour", "color"),
    ("colors", "color"),
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
    r"\brecommend\b",
    r"\bsuggest\b",
    r"\bdo you have\b",
    r"\blooking for\b",
    r"\bwant\b",
    r"\bneed\b",
    r"\bproducts?\b",
    r"\bitems?\b",
)

_COLOR_ATTR_PATTERNS = (
    r"\bhow many colors?\b",
    r"\bhow many color\b",
    r"\bwhat colors?\b",
    r"\bwhich colors?\b",
    r"\bcolors? (?:are |do you have |available)\b",
    r"\bavailable colors?\b",
)

_SIZE_ATTR_PATTERNS = (
    r"\bhow many sizes?\b",
    r"\bwhat sizes?\b",
    r"\bwhich sizes?\b",
    r"\bsizes? (?:are |do you have |available)\b",
    r"\bavailable sizes?\b",
)

_PRICE_PATTERNS = (
    r"\bprice\b",
    r"\bcost\b",
    r"\bhow much\b",
)

_CHEAP_PATTERNS = (
    r"\bless expensive\b",
    r"\bleast expensive\b",
    r"\bless price\b",
    r"\blower price\b",
    r"\blow price\b",
    r"\blowest\b",
    r"\bcheapest\b",
    r"\bcheap\b",
    r"\baffordable\b",
    r"\binexpensive\b",
    r"\bbudget\b",
    r"\bunder\b",
)

_EXPENSIVE_PATTERNS = (
    r"\bmost expensive\b",
    r"\bhighest price\b",
    r"\bhigh price\b",
    r"\bcostliest\b",
    r"\bexpensive\b",
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
    "how",
    "many",
    "color",
    "colors",
    "colour",
    "colours",
    "size",
    "sizes",
    "price",
    "prices",
    "cost",
    "less",
    "lowest",
    "lower",
    "cheap",
    "cheapest",
    "expensive",
    "highest",
    "high",
    "affordable",
    "inexpensive",
    "budget",
    "under",
}


def _normalize_query(message: str) -> str:
    text = (message or "").strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for wrong, right in _TYPO_REPLACEMENTS:
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text)
    return text


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t and t not in _STOPWORDS}


def _singular(word: str) -> str:
    w = (word or "").strip().lower()
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 2 and w.endswith("ses"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _forms(text: str) -> set[str]:
    raw = (text or "").strip().lower()
    if not raw:
        return set()
    forms = {raw, _singular(raw)}
    if not raw.endswith("s"):
        forms.add(raw + "s")
    return {f for f in forms if f}


def _text_has_label(query: str, label: str) -> bool:
    """True when label appears in query as whole words (not substrings of other words)."""
    q = (query or "").lower()
    label = (label or "").strip().lower()
    if not q or not label:
        return False

    for form in _forms(label):
        if re.search(rf"\b{re.escape(form)}\b", q):
            return True

    tokens = [
        t
        for t in re.findall(r"[a-z0-9]+", label)
        if t not in _STOPWORDS and (len(t) >= 3 or t.isdigit())
    ]
    if not tokens:
        for token in re.findall(r"[a-z0-9]+", label):
            if re.search(rf"\b{re.escape(token)}\b", q):
                return True
        return False

    def _token_in_query(token: str) -> bool:
        return any(re.search(rf"\b{re.escape(form)}\b", q) for form in _forms(token))

    if all(_token_in_query(t) for t in tokens):
        return True
    # "beige" should match catalog color "Beige canvas"
    return _token_in_query(tokens[0])


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


def _product_price_text(product: dict) -> str:
    """Prefer structured price, then Sale/Regular Price columns left in attributes."""
    direct = str(product.get("price") or "").strip()
    if direct:
        return direct
    attrs = product.get("attributes") or {}
    ranked: list[tuple[int, str]] = []
    for key, value in attrs.items():
        text = str(value or "").strip()
        if not text or _parse_price(text) is None:
            continue
        nk = str(key).lower()
        if "sale price" in nk:
            ranked.append((0, text))
        elif "regular price" in nk or nk.rstrip(")").endswith("price") or "mrp" in nk:
            ranked.append((1, text))
    if not ranked:
        return ""
    ranked.sort(key=lambda item: item[0])
    raw = ranked[0][1]
    if raw.upper().startswith("PKR") or not raw.replace(",", "").replace(".", "").isdigit():
        return raw
    return f"PKR {raw}"


def _is_compare_query(message: str) -> bool:
    text = _normalize_query(message)
    return any(re.search(p, text) for p in _COMPARE_PATTERNS)


def _is_taxonomy_skip(message: str) -> bool:
    text = _normalize_query(message)
    return any(re.search(p, text) for p in _TAXONOMY_SKIP_PATTERNS)


def _is_color_attr_query(message: str) -> bool:
    text = _normalize_query(message)
    if any(re.search(p, text) for p in _COLOR_ATTR_PATTERNS):
        return True
    return bool(re.search(r"\bhow many\b", text) and re.search(r"\bcolor\b", text))


def _is_size_attr_query(message: str) -> bool:
    text = _normalize_query(message)
    if any(re.search(p, text) for p in _SIZE_ATTR_PATTERNS):
        return True
    return bool(re.search(r"\bhow many\b", text) and re.search(r"\bsize\b", text))


def _is_price_query(message: str) -> bool:
    text = _normalize_query(message)
    if any(re.search(p, text) for p in _PRICE_PATTERNS):
        return True
    return _price_sort_direction(message) is not None


def _price_sort_direction(message: str) -> str | None:
    """Return 'asc' (cheapest), 'desc' (most expensive), or None."""
    text = _normalize_query(message)
    if re.search(r"\b(less|least) expensive\b", text):
        return "asc"
    if any(re.search(p, text) for p in _EXPENSIVE_PATTERNS):
        return "desc"
    if any(re.search(p, text) for p in _CHEAP_PATTERNS):
        return "asc"
    if re.search(r"\bless\b", text) and re.search(r"\bprice\b", text):
        return "asc"
    return None


def _sort_by_price(products: list[dict], direction: str) -> list[dict]:
    priced: list[tuple[float, dict]] = []
    for product in products:
        amount = _parse_price(_product_price_text(product))
        if amount is None:
            continue
        priced.append((amount, product))
    reverse = direction == "desc"
    priced.sort(key=lambda item: (item[0], (item[1].get("name") or "").lower()), reverse=reverse)
    return [item[1] for item in priced]


def _is_product_list_query(message: str) -> bool:
    text = _normalize_query(message)
    if re.search(r"\bhow many\b", text):
        return False
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

    if subcategory and _text_has_label(q, subcategory):
        score += 12.0
    if category and _text_has_label(q, category):
        score += 8.0
    if brand and _text_has_label(q, brand):
        score += 6.0
    if name and name in q:
        score += 15.0
    if color and _text_has_label(q, color):
        score += 10.0

    fields = (
        (name, 3.0),
        (subcategory, 4.0),
        (category, 2.5),
        (brand, 2.0),
        (color, 3.0),
    )
    for field_text, weight in fields:
        if not field_text:
            continue
        field_tokens = set(re.findall(r"[a-z0-9]+", field_text))
        overlap = q_tokens & field_tokens
        score += len(overlap) * weight
        for token in q_tokens:
            if len(token) >= 3 and token in field_text:
                score += weight * 0.5

    return score


def _mark_best_value(products: list[dict]) -> list[dict]:
    priced: list[tuple[int, float]] = []
    for i, product in enumerate(products):
        amount = _parse_price(_product_price_text(product))
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
        "price": _product_price_text(product),
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


def _focus_label(query: str, products: list[dict], filters: dict | None = None) -> str:
    filters = filters or {}
    parts: list[str] = []
    if filters.get("color"):
        parts.append(str(filters["color"]).title())
    subs = {p.get("subcategory") or "" for p in products if p.get("subcategory")}
    cats = {p.get("category") or "" for p in products if p.get("category")}
    if filters.get("subcategory"):
        parts.append(filters["subcategory"])
    elif len(subs) == 1:
        parts.append(next(iter(subs)))
    elif filters.get("category"):
        parts.append(filters["category"])
    elif len(cats) == 1:
        parts.append(next(iter(cats)))
    if parts:
        return " ".join(parts)
    tokens = sorted(_tokens(query))
    if tokens:
        return " ".join(tokens[:3]).title()
    return "product"


def _vocab(products: list[dict], key: str) -> list[str]:
    seen: dict[str, str] = {}
    for product in products:
        value = (product.get(key) or "").strip()
        if not value:
            continue
        seen.setdefault(value.lower(), value)
    return sorted(seen.values(), key=lambda v: (-len(v), v.lower()))


def _extract_filters(query: str, products: list[dict]) -> dict[str, str]:
    text = _normalize_query(query)
    filters: dict[str, str] = {}

    for key in ("color", "size", "brand"):
        for value in _vocab(products, key):
            if _text_has_label(text, value):
                filters[key] = value
                break

    for product in products:
        sub = (product.get("subcategory") or "").strip()
        if sub and _text_has_label(text, sub):
            current = filters.get("subcategory") or ""
            if len(sub) > len(current):
                filters["subcategory"] = sub

    for product in products:
        cat = (product.get("category") or "").strip()
        if cat and _text_has_label(text, cat):
            current = filters.get("category") or ""
            if len(cat) > len(current):
                filters["category"] = cat

    return filters


def _matches_filters(product: dict, filters: dict[str, str]) -> bool:
    if filters.get("subcategory"):
        if not _text_has_label(product.get("subcategory") or "", filters["subcategory"]):
            if (product.get("subcategory") or "").lower() != filters["subcategory"].lower():
                return False
    elif filters.get("category"):
        if not _text_has_label(product.get("category") or "", filters["category"]):
            if (product.get("category") or "").lower() != filters["category"].lower():
                return False
    for key in ("color", "size", "brand"):
        wanted = filters.get(key)
        if not wanted:
            continue
        actual = product.get(key) or ""
        if not _text_has_label(actual, wanted) and wanted.lower() not in actual.lower():
            return False
    return True


def _dedup(products: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for product in products:
        key = (
            (product.get("name") or "").strip().lower(),
            (product.get("color") or "").strip().lower(),
            (product.get("size") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(product)
    return unique


def _filter_catalog(query: str, products: list[dict] | None = None) -> tuple[list[dict], dict[str, str]]:
    catalog = products if products is not None else get_storage().load_all_products()
    filters = _extract_filters(query, catalog)
    if not filters:
        return catalog, filters
    matched = [p for p in catalog if _matches_filters(p, filters)]
    return matched, filters


def _no_match_reply(filters: dict[str, str]) -> dict[str, Any]:
    bits = [filters[k] for k in ("color", "size", "brand", "subcategory", "category") if filters.get(k)]
    label = " ".join(bits) if bits else "those products"
    return {
        "reply": f"I don't have {label} in the catalog.",
        "ui": None,
    }


def match_products(message: str, limit: int | None = None) -> list[dict]:
    products = get_storage().load_all_products()
    if not products:
        return []

    text = _normalize_query(message)
    scoped, filters = _filter_catalog(text, products)
    if filters and not scoped:
        return []

    pool = scoped if filters else products
    scored: list[tuple[float, dict]] = []
    for product in pool:
        score = _score_product(text, product)
        if filters or score > 0:
            scored.append((max(score, 0.1) if filters else score, product))

    if not scored:
        return []

    scored.sort(key=lambda item: (-item[0], (item[1].get("name") or "").lower()))
    if not filters:
        top_score = scored[0][0]
        if top_score < 2.5:
            return []

    ranked = _dedup([item[1] for item in scored])
    if limit is None:
        return ranked
    return ranked[:limit]


def _unique_values(products: list[dict], key: str) -> list[str]:
    seen: dict[str, str] = {}
    for product in products:
        value = (product.get(key) or "").strip()
        if value:
            seen.setdefault(value.lower(), value)
    return sorted(seen.values(), key=str.lower)


def _attribute_reply(message: str, attr_key: str, attr_label: str) -> dict[str, Any] | None:
    products = get_storage().load_all_products()
    if not products:
        return None
    scoped, filters = _filter_catalog(message, products)
    if filters.get("color") and attr_key == "color":
        scoped, filters = _filter_catalog(message, products)
    if not scoped:
        if filters:
            return _no_match_reply(filters)
        return None

    values = _unique_values(scoped, attr_key)
    focus = _focus_label(message, scoped, {k: v for k, v in filters.items() if k in {"category", "subcategory"}})
    if not values:
        return {
            "reply": f"I don't have {attr_label} details for {focus} in the catalog.",
            "ui": None,
        }
    noun = attr_label if len(values) != 1 else attr_label[:-1]
    verb = "are" if focus.lower().endswith("s") else "is"
    return {
        "reply": f"{focus} {verb} available in {len(values)} {noun}: " + ", ".join(values) + ".",
        "ui": None,
    }


def try_product_ui_reply(message: str) -> dict[str, Any] | None:
    """Return {reply, ui} for product list/compare, or None to fall through."""
    if _is_taxonomy_skip(message):
        return None

    if _is_color_attr_query(message):
        return _attribute_reply(message, "color", "colors")
    if _is_size_attr_query(message):
        return _attribute_reply(message, "size", "sizes")

    compare = _is_compare_query(message)
    price_sort = _price_sort_direction(message)
    price_intent = _is_price_query(message)
    list_intent = _is_product_list_query(message)
    if not compare and not list_intent and not price_intent:
        return None

    catalog = get_storage().load_all_products()
    if not catalog:
        return None

    filters = _extract_filters(message, catalog)
    matched = match_products(
        message,
        limit=None if (price_intent or price_sort) else (LIST_LIMIT if not compare else max(LIST_LIMIT, COMPARE_LIMIT)),
    )

    if filters and not matched:
        return _no_match_reply(filters)
    if not matched:
        return None

    if price_sort:
        sorted_products = _sort_by_price(matched, price_sort)
        focus = _focus_label(message, sorted_products or matched, filters)
        if not sorted_products:
            return {
                "reply": f"I don't have prices for {focus} in the catalog.",
                "ui": None,
            }
        products = _mark_best_value([_card_product(p) for p in sorted_products[:LIST_LIMIT]])
        label = "Lowest-priced" if price_sort == "asc" else "Highest-priced"
        priced = [p for p in products if p.get("price")]
        reply = f"{label} {focus}:"
        if priced:
            reply = f"{label} {focus}: " + "; ".join(f"{p['name']} ({p['price']})" for p in priced)
        return {
            "reply": reply,
            "ui": {
                "layout": "product_cards",
                "products": products,
                "tip": "Want a closer look? Ask me to compare any two products.",
            },
        }

    text = _normalize_query(message)
    if not compare and not price_intent and not any(re.search(p, text) for p in _LIST_PATTERNS):
        top = matched[0]
        if not filters:
            sub = (top.get("subcategory") or "").lower()
            cat = (top.get("category") or "").lower()
            name = (top.get("name") or "").lower()
            if not ((sub and _text_has_label(text, sub)) or (cat and _text_has_label(text, cat)) or (name and name in text)):
                if _score_product(text, top) < 6.0:
                    return None

    if compare:
        products = _mark_best_value([_card_product(p) for p in matched[:COMPARE_LIMIT]])
        if len(products) < 2:
            products = _mark_best_value([_card_product(p) for p in matched[:LIST_LIMIT]])
            focus = _focus_label(message, products, filters)
            return {
                "reply": f"Here are {focus} options from the catalog.",
                "ui": {
                    "layout": "product_cards",
                    "products": products,
                    "tip": "Not sure? Tell me your preferred color or size and I'll help you choose.",
                },
            }
        focus = _focus_label(message, products, filters)
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
    focus = _focus_label(message, products, filters)
    if price_intent:
        priced = [p for p in products if p.get("price")]
        if len(priced) == 1:
            reply = f"{priced[0]['name']} is {priced[0]['price']}."
        elif priced:
            reply = f"{focus} prices: " + "; ".join(f"{p['name']} ({p['price']})" for p in priced)
        else:
            reply = f"Here are {focus} options from the catalog."
        return {
            "reply": reply,
            "ui": {
                "layout": "product_cards",
                "products": products,
                "tip": "Want a closer look? Ask me to compare any two products.",
            },
        }

    return {
        "reply": f"Here are {focus} options from the catalog.",
        "ui": {
            "layout": "product_cards",
            "products": products,
            "tip": "Want a closer look? Ask me to compare any two products.",
        },
    }
