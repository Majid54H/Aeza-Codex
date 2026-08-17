"""Vercel Blob storage backend for serverless deployments."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from typing import Any

from vercel.blob import BlobClient

from app.config import settings
from app.storage.storage import (
    ADMIN_CREDENTIALS_FILE,
    CHUNK_MAPPING_FILE,
    DEFAULT_SETTINGS,
    FAISS_INDEX_FILE,
    SETTINGS_FILE,
    SKIP_METADATA_FILES,
    StorageBackend,
    _sanitize_filename,
    merge_catalog_dicts,
)


class BlobStorage(StorageBackend):
    def __init__(self, prefix: str = "aeza-codex", token: str | None = None):
        self._prefix = (prefix or "aeza-codex").strip("/").strip()
        self._token = (token or settings.blob_token or os.environ.get("BLOB_READ_WRITE_TOKEN") or "").strip()
        if not self._token:
            raise RuntimeError(
                "BLOB_READ_WRITE_TOKEN is not configured. "
                "Connect a Vercel Blob store to this project, or set BLOB_READ_WRITE_TOKEN."
            )
        self._client = BlobClient(token=self._token)
        self._admin_creds_cache: dict | None = None

    def _path(self, *parts: str) -> str:
        cleaned = [self._prefix] if self._prefix else []
        for part in parts:
            text = (part or "").replace("\\", "/").strip("/")
            if text:
                cleaned.append(text)
        return "/".join(cleaned)

    def _put_bytes(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._client.put(
            path,
            data,
            access="private",
            content_type=content_type,
            overwrite=True,
        )

    def _get_bytes(self, path: str) -> bytes | None:
        try:
            return self._client.get(path)
        except Exception:
            return None

    def _put_json(self, path: str, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self._put_bytes(path, payload, content_type="application/json")

    def _get_json(self, path: str) -> Any | None:
        raw = self._get_bytes(path)
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _delete(self, path: str) -> None:
        try:
            self._client.delete(path)
        except Exception:
            pass

    def _list_paths(self, prefix: str) -> list[str]:
        paths: list[str] = []
        cursor: str | None = None
        while True:
            result = self._client.list_objects(prefix=prefix, cursor=cursor)
            for blob in result.blobs or []:
                if blob.pathname:
                    paths.append(blob.pathname)
            if not result.has_more:
                break
            cursor = result.cursor
        return paths

    def _hash_password(self, password: str, salt: str, iterations: int) -> str:
        salt_bytes = (salt or "").encode("utf-8")
        pwd_bytes = (password or "").encode("utf-8")
        dk = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, iterations)
        return dk.hex()

    def _document_prefix(self, document_id: str) -> str:
        return self._path("documents", f"{document_id}_")

    async def save_document(self, document_id: str, filename: str, content: bytes) -> None:
        safe_filename = _sanitize_filename(filename)
        path = self._path("documents", f"{document_id}_{safe_filename}")
        self._put_bytes(path, content)

    async def load_document(self, document_id: str) -> bytes:
        prefix = self._document_prefix(document_id)
        matches = [p for p in self._list_paths(prefix) if p.startswith(prefix)]
        if not matches:
            raise FileNotFoundError(f"Document not found: {document_id}")
        matches.sort(reverse=True)
        raw = self._get_bytes(matches[0])
        if raw is None:
            raise FileNotFoundError(f"Document not found: {document_id}")
        return raw

    async def delete_document(self, document_id: str) -> None:
        prefix = self._document_prefix(document_id)
        for path in self._list_paths(prefix):
            if path.startswith(prefix):
                self._delete(path)
        self._delete(self._path("metadata", f"{document_id}.json"))
        self.delete_catalog(document_id)
        self.delete_products(document_id)

    async def save_metadata(self, document_id: str, metadata: dict) -> None:
        self._put_json(self._path("metadata", f"{document_id}.json"), metadata)

    async def load_metadata(self, document_id: str) -> dict:
        data = self._get_json(self._path("metadata", f"{document_id}.json"))
        if not isinstance(data, dict):
            raise FileNotFoundError(f"Metadata not found: {document_id}")
        return data

    async def list_documents(self) -> list[dict]:
        prefix = self._path("metadata") + "/"
        docs: list[dict] = []
        for path in self._list_paths(prefix):
            name = path.rsplit("/", 1)[-1]
            if not name.endswith(".json") or name in SKIP_METADATA_FILES:
                continue
            data = self._get_json(path)
            if isinstance(data, dict):
                docs.append({"id": name[:-5], **data})
        return docs

    def save_faiss_index(self, data: bytes) -> None:
        self._put_bytes(self._path("indexes", FAISS_INDEX_FILE), data)

    def load_faiss_index(self) -> bytes | None:
        return self._get_bytes(self._path("indexes", FAISS_INDEX_FILE))

    def delete_faiss_index(self) -> None:
        self._delete(self._path("indexes", FAISS_INDEX_FILE))

    def save_chunk_mapping(self, mapping: list[dict]) -> None:
        self._put_json(self._path("metadata", CHUNK_MAPPING_FILE), mapping)

    def load_chunk_mapping(self) -> list[dict]:
        data = self._get_json(self._path("metadata", CHUNK_MAPPING_FILE))
        if isinstance(data, list):
            return data
        return []

    def load_settings(self) -> dict:
        data = self._get_json(self._path("metadata", SETTINGS_FILE))
        if not isinstance(data, dict):
            return dict(DEFAULT_SETTINGS)
        merged = dict(DEFAULT_SETTINGS)
        merged.update({k: data[k] for k in DEFAULT_SETTINGS if k in data})
        return merged

    def save_settings(self, data: dict) -> dict:
        merged = self.load_settings()
        for key in DEFAULT_SETTINGS:
            if key in data and data[key] is not None:
                merged[key] = data[key]
        self._put_json(self._path("metadata", SETTINGS_FILE), merged)
        return merged

    def _catalog_path(self, document_id: str) -> str:
        return self._path("metadata", "catalogs", f"{document_id}.json")

    def save_catalog(self, document_id: str, catalog: dict) -> None:
        self._put_json(self._catalog_path(document_id), catalog)

    def load_catalog(self, document_id: str) -> dict | None:
        data = self._get_json(self._catalog_path(document_id))
        return data if isinstance(data, dict) else None

    def delete_catalog(self, document_id: str) -> None:
        self._delete(self._catalog_path(document_id))

    def delete_all_catalogs(self) -> None:
        prefix = self._path("metadata", "catalogs") + "/"
        for path in self._list_paths(prefix):
            if path.endswith(".json"):
                self._delete(path)

    def load_merged_catalog(self) -> dict | None:
        prefix = self._path("metadata", "catalogs") + "/"
        catalogs: list[dict] = []
        for path in sorted(self._list_paths(prefix)):
            if not path.endswith(".json"):
                continue
            catalog = self._get_json(path)
            if isinstance(catalog, dict) and catalog:
                if not catalog.get("document_id"):
                    catalog = {**catalog, "document_id": path.rsplit("/", 1)[-1][:-5]}
                catalogs.append(catalog)
        return merge_catalog_dicts(catalogs)

    def _products_path(self, document_id: str) -> str:
        return self._path("metadata", "products", f"{document_id}.json")

    def save_products(self, document_id: str, products: dict) -> None:
        self._put_json(self._products_path(document_id), products)

    def load_products(self, document_id: str) -> dict | None:
        data = self._get_json(self._products_path(document_id))
        return data if isinstance(data, dict) else None

    def delete_products(self, document_id: str) -> None:
        self._delete(self._products_path(document_id))

    def delete_all_products(self) -> None:
        prefix = self._path("metadata", "products") + "/"
        for path in self._list_paths(prefix):
            if path.endswith(".json"):
                self._delete(path)

    def load_all_products(self) -> list[dict]:
        prefix = self._path("metadata", "products") + "/"
        products: list[dict] = []
        for path in sorted(self._list_paths(prefix)):
            if not path.endswith(".json"):
                continue
            payload = self._get_json(path)
            if not isinstance(payload, dict):
                continue
            for item in payload.get("products") or []:
                if isinstance(item, dict) and item.get("name"):
                    products.append(item)
        return products

    async def load_admin_credentials(self) -> dict:
        if self._admin_creds_cache:
            return self._admin_creds_cache

        path = self._path("metadata", ADMIN_CREDENTIALS_FILE)
        data = self._get_json(path)
        if (
            isinstance(data, dict)
            and data.get("username")
            and data.get("password_hash")
            and data.get("salt")
            and data.get("iterations")
        ):
            self._admin_creds_cache = data
            return data

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
            self._put_json(path, creds)
        except Exception:
            pass

        self._admin_creds_cache = creds
        return creds

    async def save_admin_credentials(self, creds: dict) -> None:
        payload = dict(creds)
        payload["source"] = "user"
        self._put_json(self._path("metadata", ADMIN_CREDENTIALS_FILE), payload)
        self._admin_creds_cache = payload
