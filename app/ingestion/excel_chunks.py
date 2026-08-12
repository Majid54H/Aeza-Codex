"""Build hybrid FAISS chunks and catalog metadata from Excel analysis."""

from __future__ import annotations

from app.config import settings
from app.ingestion.chunker import chunk_records_with_metadata
from app.ingestion.excel_analyzer import ExcelAnalysis, ProductRecord


def _product_lines(product: ProductRecord) -> list[str]:
    lines = [f"Product: {product.name}"]
    if product.category:
        lines.append(f"Category: {product.category}")
    if product.subcategory:
        lines.append(f"Subcategory: {product.subcategory}")
    if product.brand:
        lines.append(f"Brand: {product.brand}")
    if product.price:
        lines.append(f"Price: {product.price}")
    for key, value in product.attributes.items():
        if value:
            lines.append(f"{key}: {value}")
    return lines


def _product_summary(product: ProductRecord) -> str:
    if product.category and product.subcategory and product.price:
        return (
            f"{product.name} is available in {product.category} "
            f"under {product.subcategory} for {product.price}."
        )
    if product.category and product.price:
        return f"{product.name} is available in {product.category} for {product.price}."
    if product.category and product.subcategory:
        return f"{product.name} is available in {product.category} under {product.subcategory}."
    if product.category:
        return f"{product.name} is available in {product.category}."
    if product.price:
        return f"{product.name} is available for {product.price}."
    return product.name


def build_product_chunk_text(product: ProductRecord) -> str:
    lines = _product_lines(product)
    lines.append("")
    lines.append(_product_summary(product))
    return "\n".join(lines)


def build_category_chunk_text(
    category: str,
    subcategories: list[str],
    product_count: int,
    sample_products: list[str],
) -> str:
    lines = [
        f"Category: {category}",
        f"Product count: {product_count}",
    ]
    if subcategories:
        lines.append("Subcategories: " + ", ".join(subcategories))
    if sample_products:
        lines.append("Sample products: " + ", ".join(sample_products))
    lines.append("")
    summary = f"The {category} category"
    if subcategories:
        summary += f" includes {len(subcategories)} subcategories"
    summary += f" with {product_count} products."
    if sample_products:
        summary += f" Examples: {', '.join(sample_products[:5])}."
    lines.append(summary)
    return "\n".join(lines)


def build_catalog_summary_text(categories: list[dict]) -> str:
    lines = ["Catalog Overview", "", "Available categories:"]
    for cat in sorted(categories, key=lambda c: c["name"].lower()):
        sub_count = len(cat.get("subcategories") or [])
        prod_count = cat.get("product_count", 0)
        sub_label = "subcategory" if sub_count == 1 else "subcategories"
        prod_label = "product" if prod_count == 1 else "products"
        lines.append(f"- {cat['name']} ({sub_count} {sub_label}, {prod_count} {prod_label})")
    lines.append("")
    lines.append(
        "This catalog lists all product categories and subcategories available in the uploaded spreadsheet."
    )
    return "\n".join(lines)


def build_catalog_dict(
    document_id: str,
    filename: str,
    analysis: ExcelAnalysis,
    sample_cap: int | None = None,
) -> dict:
    cap = sample_cap if sample_cap is not None else settings.excel_category_sample_products
    categories: list[dict] = []

    for cat_name in sorted(analysis.taxonomy.keys(), key=str.lower):
        subs = sorted(analysis.taxonomy[cat_name], key=str.lower)
        prods_in_cat = [p for p in analysis.products if p.category == cat_name]
        sample = [p.name for p in prods_in_cat[:cap]]
        categories.append(
            {
                "name": cat_name,
                "subcategories": subs,
                "product_count": len(prods_in_cat),
                "sample_products": sample,
            }
        )

    return {
        "document_id": document_id,
        "filename": filename,
        "categories": categories,
        "product_count": len(analysis.products),
    }


def build_excel_chunks(
    document_id: str,
    filename: str,
    analysis: ExcelAnalysis,
) -> tuple[list[dict], dict, dict]:
    """Return FAISS chunk dicts and catalog metadata for an Excel document."""
    sample_cap = settings.excel_category_sample_products
    catalog = build_catalog_dict(document_id, filename, analysis, sample_cap)
    chunks: list[dict] = []
    chunk_index = 0
    breakdown = {"product": 0, "category": 0, "catalog": 0, "generic": 0}

    for product in analysis.products:
        chunks.append(
            {
                "text": build_product_chunk_text(product),
                "chunk_type": "product",
                "chunk_index": chunk_index,
                "document_id": document_id,
            }
        )
        chunk_index += 1
        breakdown["product"] += 1

    products_by_category: dict[str, list[ProductRecord]] = {}
    for product in analysis.products:
        if product.category:
            products_by_category.setdefault(product.category, []).append(product)

    for cat_name in sorted(analysis.taxonomy.keys(), key=str.lower):
        subs = sorted(analysis.taxonomy[cat_name], key=str.lower)
        prods = products_by_category.get(cat_name, [])
        sample = [p.name for p in prods[:sample_cap]]
        chunks.append(
            {
                "text": build_category_chunk_text(cat_name, subs, len(prods), sample),
                "chunk_type": "category",
                "chunk_index": chunk_index,
                "document_id": document_id,
            }
        )
        chunk_index += 1
        breakdown["category"] += 1

    if catalog["categories"]:
        chunks.append(
            {
                "text": build_catalog_summary_text(catalog["categories"]),
                "chunk_type": "catalog",
                "chunk_index": chunk_index,
                "document_id": document_id,
            }
        )
        chunk_index += 1
        breakdown["catalog"] += 1

    if analysis.generic_records:
        for generic in chunk_records_with_metadata(analysis.generic_records, document_id):
            generic["chunk_type"] = "generic"
            generic["chunk_index"] = chunk_index
            chunks.append(generic)
            chunk_index += 1
            breakdown["generic"] += 1

    return chunks, catalog, breakdown
