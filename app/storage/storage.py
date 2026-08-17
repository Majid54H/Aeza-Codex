"""Persistent storage abstraction.

V1: LocalStorage under data/
Later: swap get_storage() to a cloud/object backend without changing callers.
"""

from __future__ import annotations

import json
import re
import hashlib
import secrets
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings

CHUNK_MAPPING_FILE = "chunk_mapping.json"
SETTINGS_FILE = "admin_settings.json"
ADMIN_CREDENTIALS_FILE = "admin_credentials.json"
FAISS_INDEX_FILE = "faiss.index"
SKIP_METADATA_FILES = {CHUNK_MAPPING_FILE, SETTINGS_FILE, ADMIN_CREDENTIALS_FILE}

DEFAULT_SETTINGS = {
    "chatbot_name": "",
    "welcome_message": "",
    "primary_color": "",
    "logo_url": "",
}


def merge_catalog_dicts(catalogs: list[dict]) -> dict | None:
    """Merge per-document catalog payloads into one taxonomy view."""
    merged_categories: dict[str, dict] = {}
    total_products = 0
    sources: list[dict] = []

    for catalog in catalogs:
        if not catalog:
            continue

        document_id = catalog.get("document_id") or ""
        sources.append(
            {
                "document_id": document_id,
                "filename": catalog.get("filename", ""),
                "product_count": catalog.get("product_count", 0),
            }
        )
        total_products += int(catalog.get("product_count") or 0)

        for cat in catalog.get("categories") or []:
            name = (cat.get("name") or "").strip()
            if not name:
                continue
            entry = merged_categories.setdefault(
                name,
                {
                    "name": name,
                    "subcategories": set(),
                    "product_count": 0,
                    "sample_products": [],
                },
            )
            for sub in cat.get("subcategories") or []:
                if sub:
                    entry["subcategories"].add(sub)
            entry["product_count"] += int(cat.get("product_count") or 0)
            cap = settings.excel_category_sample_products
            for sample in cat.get("sample_products") or []:
                if sample and sample not in entry["sample_products"] and len(entry["sample_products"]) < cap:
                    entry["sample_products"].append(sample)

    if not merged_categories:
        return None

    categories = []
    for name in sorted(merged_categories.keys(), key=str.lower):
        entry = merged_categories[name]
        categories.append(
            {
                "name": name,
                "subcategories": sorted(entry["subcategories"], key=str.lower),
                "product_count": entry["product_count"],
                "sample_products": entry["sample_products"],
            }
        )

    return {
        "categories": categories,
        "product_count": total_products,
        "sources": sources,
    }


def _sanitize_filename(filename: str) -> str:
    # Avoid directory traversal / invalid filenames on Windows.
    name = Path(filename).name
    name = name.replace("/", "_").replace("\\", "_")
    # Replace characters Windows doesn't allow in filenames.
    name = re.sub(r'[<>:"|?*\x00-\x1F]+', "_", name)
    # Collapse whitespace for cleaner paths.
    name = re.sub(r"\s+", "_", name).strip("._ ")
    return name or "document"


class StorageBackend(ABC):
    @abstractmethod
    async def save_document(self, document_id: str, filename: str, content: bytes) -> None:
        ...

    @abstractmethod
    async def load_document(self, document_id: str) -> bytes:
        ...

    @abstractmethod
    async def delete_document(self, document_id: str) -> None:
        ...

    @abstractmethod
    async def save_metadata(self, document_id: str, metadata: dict) -> None:
        ...

    @abstractmethod
    async def load_metadata(self, document_id: str) -> dict:
        ...

    @abstractmethod
    async def list_documents(self) -> list[dict]:
        ...

    @abstractmethod
    def save_faiss_index(self, data: bytes) -> None:
        ...

    @abstractmethod
    def load_faiss_index(self) -> bytes | None:
        ...

    @abstractmethod
    def delete_faiss_index(self) -> None:
        ...

    @abstractmethod
    def save_chunk_mapping(self, mapping: list[dict]) -> None:
        ...

    @abstractmethod
    def load_chunk_mapping(self) -> list[dict]:
        ...

    @abstractmethod
    def load_settings(self) -> dict:
        ...

    @abstractmethod
    def save_settings(self, data: dict) -> dict:
        ...

    @abstractmethod
    def save_catalog(self, document_id: str, catalog: dict) -> None:
        ...

    @abstractmethod
    def load_catalog(self, document_id: str) -> dict | None:
        ...

    @abstractmethod
    def delete_catalog(self, document_id: str) -> None:
        ...

    @abstractmethod
    def delete_all_catalogs(self) -> None:
        ...

    @abstractmethod
    def load_merged_catalog(self) -> dict | None:
        ...

    @abstractmethod
    async def load_admin_credentials(self) -> dict:
        ...

    @abstractmethod
    async def save_admin_credentials(self, creds: dict) -> None:
        ...

    @abstractmethod
    def save_products(self, document_id: str, products: dict) -> None:
        ...

    @abstractmethod
    def load_products(self, document_id: str) -> dict | None:
        ...

    @abstractmethod
    def delete_products(self, document_id: str) -> None:
        ...

    @abstractmethod
    def delete_all_products(self) -> None:
        ...

    @abstractmethod
    def load_all_products(self) -> list[dict]:
        ...


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: Path):
        self.documents_dir = base_dir / "documents"
        self.metadata_dir = base_dir / "metadata"
        self.indexes_dir = base_dir / "indexes"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)
        self.catalogs_dir = self.metadata_dir / "catalogs"
        self.catalogs_dir.mkdir(parents=True, exist_ok=True)
        self.products_dir = self.metadata_dir / "products"
        self.products_dir.mkdir(parents=True, exist_ok=True)
        self._admin_credentials_path = self.metadata_dir / ADMIN_CREDENTIALS_FILE
        self._admin_creds_cache: dict | None = None

    def _hash_password(self, password: str, salt: str, iterations: int) -> str:
        salt_bytes = (salt or "").encode("utf-8")
        pwd_bytes = (password or "").encode("utf-8")
        dk = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, iterations)
        return dk.hex()

    def _document_paths(self, document_id: str) -> list[Path]:
        prefix = f"{document_id}_"
        return sorted(
            self.documents_dir.glob(prefix + "*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    async def save_document(self, document_id: str, filename: str, content: bytes) -> None:
        safe_filename = _sanitize_filename(filename)
        path = self.documents_dir / f"{document_id}_{safe_filename}"
        path.write_bytes(content)

    async def load_document(self, document_id: str) -> bytes:
        candidates = self._document_paths(document_id)
        if not candidates:
            raise FileNotFoundError(f"Document not found: {document_id}")
        return candidates[0].read_bytes()

    async def delete_document(self, document_id: str) -> None:
        for path in self._document_paths(document_id):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        meta_path = self.metadata_dir / f"{document_id}.json"
        try:
            meta_path.unlink()
        except FileNotFoundError:
            pass
        self.delete_catalog(document_id)
        self.delete_products(document_id)

    async def save_metadata(self, document_id: str, metadata: dict) -> None:
        path = self.metadata_dir / f"{document_id}.json"
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    async def load_metadata(self, document_id: str) -> dict:
        path = self.metadata_dir / f"{document_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Metadata not found: {document_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    async def list_documents(self) -> list[dict]:
        docs = []
        for meta_file in self.metadata_dir.glob("*.json"):
            if meta_file.name in SKIP_METADATA_FILES:
                continue
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            docs.append({"id": meta_file.stem, **data})
        return docs

    def save_faiss_index(self, data: bytes) -> None:
        path = self.indexes_dir / FAISS_INDEX_FILE
        path.write_bytes(data)

    def load_faiss_index(self) -> bytes | None:
        path = self.indexes_dir / FAISS_INDEX_FILE
        if not path.exists():
            return None
        return path.read_bytes()

    def delete_faiss_index(self) -> None:
        path = self.indexes_dir / FAISS_INDEX_FILE
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def save_chunk_mapping(self, mapping: list[dict]) -> None:
        path = self.metadata_dir / CHUNK_MAPPING_FILE
        path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_chunk_mapping(self) -> list[dict]:
        path = self.metadata_dir / CHUNK_MAPPING_FILE
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8")) or []
        except (json.JSONDecodeError, OSError):
            return []

    def load_settings(self) -> dict:
        path = self.metadata_dir / SETTINGS_FILE
        if not path.exists():
            return dict(DEFAULT_SETTINGS)
        try:
            data = json.loads(path.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_SETTINGS)
        merged = dict(DEFAULT_SETTINGS)
        merged.update({k: data[k] for k in DEFAULT_SETTINGS if k in data})
        return merged

    def save_settings(self, data: dict) -> dict:
        merged = self.load_settings()
        for key in DEFAULT_SETTINGS:
            if key in data and data[key] is not None:
                merged[key] = data[key]
        path = self.metadata_dir / SETTINGS_FILE
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return merged

    def _catalog_path(self, document_id: str) -> Path:
        return self.catalogs_dir / f"{document_id}.json"

    def save_catalog(self, document_id: str, catalog: dict) -> None:
        path = self._catalog_path(document_id)
        path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_catalog(self, document_id: str) -> dict | None:
        path = self._catalog_path(document_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def delete_catalog(self, document_id: str) -> None:
        path = self._catalog_path(document_id)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def delete_all_catalogs(self) -> None:
        if not self.catalogs_dir.exists():
            return
        for path in self.catalogs_dir.glob("*.json"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def load_merged_catalog(self) -> dict | None:
        if not self.catalogs_dir.exists():
            return None

        catalogs: list[dict] = []
        for path in sorted(self.catalogs_dir.glob("*.json")):
            try:
                catalog = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if catalog:
                if not catalog.get("document_id"):
                    catalog = {**catalog, "document_id": path.stem}
                catalogs.append(catalog)

        return merge_catalog_dicts(catalogs)

    def _products_path(self, document_id: str) -> Path:
        return self.products_dir / f"{document_id}.json"

    def save_products(self, document_id: str, products: dict) -> None:
        path = self._products_path(document_id)
        path.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_products(self, document_id: str) -> dict | None:
        path = self._products_path(document_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def delete_products(self, document_id: str) -> None:
        path = self._products_path(document_id)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def delete_all_products(self) -> None:
        if not self.products_dir.exists():
            return
        for path in self.products_dir.glob("*.json"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def load_all_products(self) -> list[dict]:
        if not self.products_dir.exists():
            return []
        products: list[dict] = []
        for path in sorted(self.products_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for item in payload.get("products") or []:
                if isinstance(item, dict) and item.get("name"):
                    products.append(item)
        return products

    async def load_admin_credentials(self) -> dict:
        if self._admin_creds_cache:
            return self._admin_creds_cache

        path = self._admin_credentials_path
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if (
                    isinstance(data, dict)
                    and data.get("username")
                    and data.get("password_hash")
                    and data.get("salt")
                    and data.get("iterations")
                ):
                    self._admin_creds_cache = data
                    return data
            except (json.JSONDecodeError, OSError):
                pass

        if not settings.admin_password:
            raise RuntimeError("Admin password not configured. Set ADMIN_PASSWORD in the environment.")

        salt = secrets.token_hex(16)
        iterations = 200_000
        password_hash = self._hash_password(settings.admin_password, salt=salt, iterations=iterations)
        creds = {
            "username": settings.admin_username,
            "password_hash": password_hash,
            "salt": salt,
            "iterations": iterations,
            "source": "env",
        }

        try:
            path.write_text(json.dumps(creds, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

        self._admin_creds_cache = creds
        return creds

    async def save_admin_credentials(self, creds: dict) -> None:
        payload = dict(creds)
        payload["source"] = "user"
        self._admin_credentials_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._admin_creds_cache = payload


_storage_singleton: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Return the active storage backend (singleton)."""
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton

    backend = settings.resolved_storage_backend
    if backend == "blob":
        from app.storage.blob_storage import BlobStorage

        _storage_singleton = BlobStorage(settings.blob_prefix, token=settings.blob_token)
    else:
        _storage_singleton = LocalStorage(settings.effective_data_dir)
    return _storage_singleton
