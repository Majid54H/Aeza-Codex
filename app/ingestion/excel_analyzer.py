"""Excel analyzer — detect schema, normalize products and taxonomy."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.ingestion.loader import iter_excel_sheets, sheet_to_labeled_rows

CATEGORY_KEYS = {"category", "categories", "product_category", "main_category"}
SUBCATEGORY_KEYS = {"subcategory", "subcategories", "sub_category", "product_type", "type"}
SUBCATEGORY_LIST_KEYS = {"subcategories", "subcategory_list"}
NAME_KEYS = {"product", "product_name", "name", "title", "item", "item_name"}
BRAND_KEYS = {"brand", "manufacturer", "vendor"}
PRICE_KEYS = {"price", "sale_price", "cost", "mrp", "regular_price"}
STOCK_KEYS = {"stock", "quantity", "qty", "in_stock", "inventory"}
SIZE_KEYS = {"size", "sizes"}
COLOR_KEYS = {"color", "colour", "colors"}
DISCOUNT_KEYS = {"discount", "sale", "off", "percent_off", "pct_off", "%_off"}


def _norm_header(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)
    return text


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _split_subcategories(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,;|/]", raw)
    return [p.strip() for p in parts if p.strip()]


def _match_column(headers: list[str], aliases: set[str]) -> int | None:
    for i, h in enumerate(headers):
        if h in aliases:
            return i
    return None


def _clean_rows(rows: list[list]) -> list[list[str]]:
    cleaned: list[list[str]] = []
    for row in rows:
        values = [_cell_text(v) for v in row]
        while values and not values[-1]:
            values.pop()
        if not any(values):
            continue
        cleaned.append(values)
    return cleaned


@dataclass
class ProductRecord:
    name: str
    category: str = ""
    subcategory: str = ""
    brand: str = ""
    price: str = ""
    stock: str = ""
    color: str = ""
    size: str = ""
    discount: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    sheet: str = ""


@dataclass
class ExcelAnalysis:
    products: list[ProductRecord] = field(default_factory=list)
    taxonomy: dict[str, set[str]] = field(default_factory=dict)
    generic_records: list[str] = field(default_factory=list)
    filename: str = ""


def _detect_sheet_kind(headers: list[str]) -> str:
    has_category = _match_column(headers, CATEGORY_KEYS) is not None
    has_sub_list = _match_column(headers, SUBCATEGORY_LIST_KEYS | SUBCATEGORY_KEYS) is not None
    has_product_signal = any(
        _match_column(headers, keys) is not None
        for keys in (NAME_KEYS, PRICE_KEYS, STOCK_KEYS, BRAND_KEYS)
    )

    if has_category and has_sub_list and not has_product_signal:
        return "taxonomy"
    if has_category or has_product_signal:
        return "products"
    return "generic"


def _parse_taxonomy_sheet(
    headers: list[str],
    rows: list[list[str]],
    taxonomy: dict[str, set[str]],
) -> None:
    cat_idx = _match_column(headers, CATEGORY_KEYS)
    sub_idx = _match_column(headers, SUBCATEGORY_LIST_KEYS | SUBCATEGORY_KEYS)
    if cat_idx is None:
        return
    for row in rows:
        category = row[cat_idx] if cat_idx < len(row) else ""
        if not category:
            continue
        taxonomy.setdefault(category, set())
        if sub_idx is not None and sub_idx < len(row):
            for sub in _split_subcategories(row[sub_idx]):
                taxonomy[category].add(sub)


def _parse_product_sheet(
    sheet_name: str,
    headers: list[str],
    rows: list[list[str]],
    products: list[ProductRecord],
    taxonomy: dict[str, set[str]],
) -> None:
    cat_idx = _match_column(headers, CATEGORY_KEYS)
    sub_idx = _match_column(headers, SUBCATEGORY_KEYS)
    name_idx = _match_column(headers, NAME_KEYS)
    brand_idx = _match_column(headers, BRAND_KEYS)
    price_idx = _match_column(headers, PRICE_KEYS)
    stock_idx = _match_column(headers, STOCK_KEYS)
    color_idx = _match_column(headers, COLOR_KEYS)
    size_idx = _match_column(headers, SIZE_KEYS)
    discount_idx = _match_column(headers, DISCOUNT_KEYS)
    used = {
        i
        for i in (
            cat_idx,
            sub_idx,
            name_idx,
            brand_idx,
            price_idx,
            stock_idx,
            color_idx,
            size_idx,
            discount_idx,
        )
        if i is not None
    }

    for row in rows:
        category = row[cat_idx] if cat_idx is not None and cat_idx < len(row) else ""
        subcategory = row[sub_idx] if sub_idx is not None and sub_idx < len(row) else ""
        name = row[name_idx] if name_idx is not None and name_idx < len(row) else ""
        if not name and not category:
            name = next((v for v in row if v), "")
        if not name and not category:
            continue

        brand = row[brand_idx] if brand_idx is not None and brand_idx < len(row) else ""
        price = row[price_idx] if price_idx is not None and price_idx < len(row) else ""
        stock = row[stock_idx] if stock_idx is not None and stock_idx < len(row) else ""
        color = row[color_idx] if color_idx is not None and color_idx < len(row) else ""
        size = row[size_idx] if size_idx is not None and size_idx < len(row) else ""
        discount = row[discount_idx] if discount_idx is not None and discount_idx < len(row) else ""
        attrs: dict[str, str] = {}
        for i, h in enumerate(headers):
            if i in used or i >= len(row) or not row[i]:
                continue
            label = h.replace("_", " ").title()
            attrs[label] = row[i]

        if category:
            taxonomy.setdefault(category, set())
            if subcategory:
                taxonomy[category].add(subcategory)

        products.append(
            ProductRecord(
                name=name or f"{category} {subcategory}".strip(),
                category=category,
                subcategory=subcategory,
                brand=brand,
                price=price,
                stock=stock,
                color=color,
                size=size,
                discount=discount,
                attributes=attrs,
                sheet=sheet_name,
            )
        )


def analyze_excel(content: bytes, filename: str) -> ExcelAnalysis:
    """Parse Excel and return normalized products + taxonomy."""
    analysis = ExcelAnalysis(filename=filename)
    taxonomy: dict[str, set[str]] = {}

    for sheet_name, rows in iter_excel_sheets(content, filename):
        cleaned = _clean_rows(rows)
        if not cleaned:
            continue

        headers = [_norm_header(h) for h in cleaned[0]]
        data_rows = cleaned[1:]
        if not data_rows:
            analysis.generic_records.extend(sheet_to_labeled_rows(sheet_name, rows))
            continue

        kind = _detect_sheet_kind(headers)
        if kind == "taxonomy":
            _parse_taxonomy_sheet(headers, data_rows, taxonomy)
        elif kind == "products":
            _parse_product_sheet(sheet_name, headers, data_rows, analysis.products, taxonomy)
        else:
            analysis.generic_records.extend(sheet_to_labeled_rows(sheet_name, rows))

    for product in analysis.products:
        if product.category:
            taxonomy.setdefault(product.category, set())
            if product.subcategory:
                taxonomy[product.category].add(product.subcategory)

    analysis.taxonomy = taxonomy
    return analysis
